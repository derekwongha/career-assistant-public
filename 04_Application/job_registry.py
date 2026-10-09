import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "05_Evaluation"
    / "job_registry.sqlite"
)

# Approved Minimum Lifecycle States
STATE_DISCOVERED = "DISCOVERED"
STATE_RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
STATE_RETRIEVED = "RETRIEVED"
STATE_ANALYSIS_FAILED = "ANALYSIS_FAILED"
STATE_REVIEW_PENDING = "REVIEW_PENDING"
STATE_SKIPPED = "SKIPPED"
STATE_APPLY_PENDING = "APPLY_PENDING"
STATE_COVER_LETTER_GENERATED = "COVER_LETTER_GENERATED"
STATE_APPLIED = "APPLIED"

VALID_STATES = {
    STATE_DISCOVERED,
    STATE_RETRIEVAL_FAILED,
    STATE_RETRIEVED,
    STATE_ANALYSIS_FAILED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_APPLIED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or DEFAULT_DB_PATH
    if target_path != Path(":memory:"):
        target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                source_reference TEXT NOT NULL,
                confirmed_url TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT NOT NULL,
                cleaned_text TEXT,
                analysis_result_json TEXT,
                recommended_priority TEXT,
                recommended_action TEXT,
                human_decision TEXT,
                cover_letter_path TEXT,
                excel_app_id TEXT,
                last_error TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                seen_at TEXT NOT NULL,
                email_subject TEXT NOT NULL,
                email_date TEXT NOT NULL,
                email_sender TEXT,
                anchor_text TEXT NOT NULL,
                tracking_url TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                UNIQUE(job_id, email_subject, tracking_url)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    return conn


def get_system_metadata(conn: sqlite3.Connection, key: str) -> Optional[str]:
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_metadata WHERE key = ?", (key,))
    row = cursor.fetchone()
    if row is None:
        return None
    return row[0] if isinstance(row, tuple) else row["value"]


def set_system_metadata(
    conn: sqlite3.Connection,
    key: str,
    value: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    now = timestamp_iso or _now_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO system_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;
            """,
            (key, value, now),
        )


def get_eligible_jobs_for_analysis(
    conn: sqlite3.Connection, limit: Optional[int] = None
) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    query = """
        SELECT job_id, source_reference, confirmed_url, first_seen, last_seen,
               status, cleaned_text, analysis_result_json, recommended_priority,
               recommended_action, human_decision, cover_letter_path, last_error
        FROM jobs
        WHERE (
            status IN ('DISCOVERED', 'RETRIEVED', 'ANALYSIS_FAILED')
            OR (
                status = 'RETRIEVAL_FAILED'
                AND (
                    last_error IS NULL
                    OR (
                        last_error NOT LIKE '%404%'
                        AND last_error NOT LIKE '%410%'
                        AND last_error NOT LIKE '%Permanent%'
                    )
                )
            )
        )
        AND (human_decision IS NULL OR human_decision = '' OR human_decision = 'Undecided')
        ORDER BY first_seen ASC, job_id ASC
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    cursor.execute(query)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def count_eligible_jobs_for_analysis(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM jobs
        WHERE (
            status IN ('DISCOVERED', 'RETRIEVED', 'ANALYSIS_FAILED')
            OR (
                status = 'RETRIEVAL_FAILED'
                AND (
                    last_error IS NULL
                    OR (
                        last_error NOT LIKE '%404%'
                        AND last_error NOT LIKE '%410%'
                        AND last_error NOT LIKE '%Permanent%'
                    )
                )
            )
        )
        AND (human_decision IS NULL OR human_decision = '' OR human_decision = 'Undecided')
        """
    )
    row = cursor.fetchone()
    return row[0] if row else 0


def get_job(conn: sqlite3.Connection, job_id: str) -> Optional[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def get_job_sources(
    conn: sqlite3.Connection, job_id: str
) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM job_sources WHERE job_id = ? ORDER BY id ASC", (job_id,)
    )
    return [dict(row) for row in cursor.fetchall()]


def register_job_candidate(
    conn: sqlite3.Connection,
    job_id: str,
    confirmed_url: str,
    candidate: dict[str, Any],
    timestamp_iso: Optional[str] = None,
) -> dict[str, Any]:
    """
    Registers a candidate link occurrence for a canonical job ID.
    If the job record does not exist yet, creates it in DISCOVERED state.
    If it exists, updates last_seen.
    Always inserts the source occurrence into job_sources idempotently.
    """
    now = timestamp_iso or _now_iso()
    source_reference = f"JOBSTREET-{job_id}"

    with conn:
        existing = get_job(conn, job_id)
        if existing is None:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, source_reference, confirmed_url, first_seen, last_seen, status
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    job_id,
                    source_reference,
                    confirmed_url,
                    now,
                    now,
                    STATE_DISCOVERED,
                ),
            )
        else:
            conn.execute(
                "UPDATE jobs SET last_seen = ? WHERE job_id = ?;",
                (now, job_id),
            )

        conn.execute(
            """
            INSERT OR IGNORE INTO job_sources (
                job_id, seen_at, email_subject, email_date, email_sender, anchor_text, tracking_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                job_id,
                now,
                candidate.get("email_subject", ""),
                candidate.get("email_date", ""),
                candidate.get("email_from", candidate.get("email_sender", "")),
                candidate.get("anchor_text", ""),
                candidate.get("tracking_url", ""),
            ),
        )

    return get_job(conn, job_id)  # type: ignore


def update_retrieval_success(
    conn: sqlite3.Connection,
    job_id: str,
    cleaned_text: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    now = timestamp_iso or _now_iso()
    with conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, cleaned_text = ?, last_seen = ?, last_error = NULL
            WHERE job_id = ?;
            """,
            (STATE_RETRIEVED, cleaned_text, now, job_id),
        )


def update_retrieval_failure(
    conn: sqlite3.Connection,
    job_id: str,
    error_msg: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    now = timestamp_iso or _now_iso()
    with conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, last_error = ?, last_seen = ?
            WHERE job_id = ?;
            """,
            (STATE_RETRIEVAL_FAILED, error_msg, now, job_id),
        )


def update_analysis_success(
    conn: sqlite3.Connection,
    job_id: str,
    analysis_result_json: str,
    recommended_priority: str,
    recommended_action: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    now = timestamp_iso or _now_iso()
    with conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, analysis_result_json = ?, recommended_priority = ?, recommended_action = ?, last_seen = ?, last_error = NULL
            WHERE job_id = ?;
            """,
            (
                STATE_REVIEW_PENDING,
                analysis_result_json,
                recommended_priority,
                recommended_action,
                now,
                job_id,
            ),
        )


def update_analysis_failure(
    conn: sqlite3.Connection,
    job_id: str,
    error_msg: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    now = timestamp_iso or _now_iso()
    with conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, last_error = ?, last_seen = ?
            WHERE job_id = ?;
            """,
            (STATE_ANALYSIS_FAILED, error_msg, now, job_id),
        )


def update_human_decision(
    conn: sqlite3.Connection,
    job_id: str,
    human_decision: str,
    new_status: Optional[str] = None,
    timestamp_iso: Optional[str] = None,
) -> None:
    now = timestamp_iso or _now_iso()
    target_status = new_status or (
        STATE_SKIPPED if human_decision == "Skip" else STATE_APPLY_PENDING
    )
    if target_status not in VALID_STATES:
        raise ValueError(f"Invalid status: {target_status}")

    with conn:
        conn.execute(
            """
            UPDATE jobs
            SET human_decision = ?, status = ?, last_seen = ?
            WHERE job_id = ?;
            """,
            (human_decision, target_status, now, job_id),
        )


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    if status not in VALID_STATES:
        raise ValueError(f"Invalid status: {status}")
    now = timestamp_iso or _now_iso()
    with conn:
        conn.execute(
            "UPDATE jobs SET status = ?, last_seen = ? WHERE job_id = ?;",
            (status, now, job_id),
        )


# ==============================================================================
# STEP 4: CENTRALLY ENFORCED STATE TRANSITIONS & DASHBOARD QUERY API
# ==============================================================================

ALLOWED_TRANSITIONS = {
    (STATE_REVIEW_PENDING, STATE_SKIPPED),
    (STATE_REVIEW_PENDING, STATE_APPLY_PENDING),
    (STATE_APPLY_PENDING, STATE_COVER_LETTER_GENERATED),
    (STATE_APPLY_PENDING, STATE_APPLIED),
    (STATE_COVER_LETTER_GENERATED, STATE_APPLIED),
}


def transition_to_applied(
    conn: sqlite3.Connection,
    job_id: str,
    excel_app_id: str,
    timestamp_iso: Optional[str] = None,
) -> None:
    """
    Transitions a job in APPLY_PENDING or COVER_LETTER_GENERATED status to APPLIED.
    Enforces that excel_app_id IS NULL initially.
    Verifies that exactly 1 row was updated (cursor.rowcount == 1).
    Raises ValueError / RuntimeError if transition fails or rowcount != 1.
    """
    cur = conn.cursor()
    cur.execute("SELECT status, excel_app_id FROM jobs WHERE job_id = ?", (job_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Job ID '{job_id}' not found in registry.")

    current_status = row[0] if isinstance(row, tuple) else row["status"]
    current_excel_id = row[1] if isinstance(row, tuple) else row["excel_app_id"]

    if current_status not in (STATE_APPLY_PENDING, STATE_COVER_LETTER_GENERATED):
        raise ValueError(
            f"Invalid transition to APPLIED from status '{current_status}'. "
            f"Allowed source states are: APPLY_PENDING, COVER_LETTER_GENERATED."
        )

    if current_excel_id is not None:
        raise ValueError(
            f"Job ID '{job_id}' already linked to excel_app_id '{current_excel_id}'. Double submission rejected."
        )

    now = timestamp_iso or _now_iso()

    with conn:
        res = conn.execute(
            """
            UPDATE jobs
            SET status = ?, excel_app_id = ?, last_seen = ?
            WHERE job_id = ? AND status IN (?, ?) AND excel_app_id IS NULL;
            """,
            (
                STATE_APPLIED,
                excel_app_id,
                now,
                job_id,
                STATE_APPLY_PENDING,
                STATE_COVER_LETTER_GENERATED,
            ),
        )
        if res.rowcount != 1:
            raise RuntimeError(
                f"Failed to transition job '{job_id}' to APPLIED. Rowcount was {res.rowcount}, expected 1."
            )


def transition_job_state(
    conn: sqlite3.Connection,
    job_id: str,
    target_status: str,
    human_decision: Optional[str] = None,
    cover_letter_path: Optional[str] = None,
    timestamp_iso: Optional[str] = None,
) -> None:
    """
    Centrally enforces allowed state transitions.
    Raises ValueError if transition is invalid or job_id does not exist.
    """
    cur = conn.cursor()
    cur.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Job ID '{job_id}' not found in registry.")

    current_status = row[0] if isinstance(row, tuple) else row["status"]

    if (current_status, target_status) not in ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Invalid state transition: '{current_status}' -> '{target_status}'."
        )

    now = timestamp_iso or _now_iso()

    with conn:
        if cover_letter_path:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, human_decision = COALESCE(?, human_decision), cover_letter_path = ?, last_seen = ?
                WHERE job_id = ?;
                """,
                (target_status, human_decision, cover_letter_path, now, job_id),
            )
        else:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, human_decision = COALESCE(?, human_decision), last_seen = ?
                WHERE job_id = ?;
                """,
                (target_status, human_decision, now, job_id),
            )


def bulk_transition_job_states(
    conn: sqlite3.Connection,
    job_ids: list[str],
    target_status: str,
    human_decision: str,
    timestamp_iso: Optional[str] = None,
) -> int:
    """
    Bulk state transition for multiple jobs.
    Must be an atomic transaction.
    If ANY requested job ID is missing or not in REVIEW_PENDING, rejects safely without partial mutation.
    """
    if not job_ids:
        return 0

    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(job_ids))
    cur.execute(
        f"SELECT job_id, status FROM jobs WHERE job_id IN ({placeholders});",
        tuple(job_ids),
    )
    rows = cur.fetchall()
    found_statuses = {
        (r[0] if isinstance(r, tuple) else r["job_id"]): (
            r[1] if isinstance(r, tuple) else r["status"]
        )
        for r in rows
    }

    ineligible = []
    for jid in job_ids:
        if jid not in found_statuses:
            ineligible.append(f"'{jid}' (not found)")
        elif found_statuses[jid] != STATE_REVIEW_PENDING:
            ineligible.append(
                f"'{jid}' (current status: {found_statuses[jid]})"
            )

    if ineligible:
        raise ValueError(
            f"Bulk transition rejected: {len(ineligible)} job(s) are ineligible for bulk decision. "
            f"Bulk decisions are permitted only for jobs currently in REVIEW_PENDING. "
            f"Details: {', '.join(ineligible)}"
        )

    if (STATE_REVIEW_PENDING, target_status) not in ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Invalid target status for bulk decision: '{target_status}'"
        )

    now = timestamp_iso or _now_iso()

    with conn:
        conn.executemany(
            """
            UPDATE jobs
            SET status = ?, human_decision = ?, last_seen = ?
            WHERE job_id = ?;
            """,
            [(target_status, human_decision, now, jid) for jid in job_ids],
        )

    return len(job_ids)


def get_all_jobs_for_dashboard(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """
    Returns all jobs formatted for dashboard consumption.
    Reads existing persisted analysis_result_json without any LLM calls.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT job_id, source_reference, confirmed_url, first_seen, last_seen,
               status, cleaned_text, analysis_result_json, recommended_priority,
               recommended_action, human_decision, cover_letter_path, last_error
        FROM jobs
        ORDER BY
            CASE recommended_priority
                WHEN 'High' THEN 1
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 3
                ELSE 4
            END,
            job_id ASC;
        """
    )
    rows = cur.fetchall()
    results = []

    for row in rows:
        r = dict(row) if isinstance(row, sqlite3.Row) else {
            "job_id": row[0],
            "source_reference": row[1],
            "confirmed_url": row[2],
            "first_seen": row[3],
            "last_seen": row[4],
            "status": row[5],
            "cleaned_text": row[6],
            "analysis_result_json": row[7],
            "recommended_priority": row[8],
            "recommended_action": row[9],
            "human_decision": row[10],
            "cover_letter_path": row[11],
            "last_error": row[12],
        }

        parsed_analysis = None
        if r["analysis_result_json"]:
            try:
                parsed_analysis = json.loads(r["analysis_result_json"])
            except Exception:
                parsed_analysis = None

        r["analysis"] = parsed_analysis
        results.append(r)

    return results

