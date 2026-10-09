"""
Step 4 — Dashboard Web Server & REST API.

Uses Python stdlib http.server (Zero external pip dependencies required).
Serves static SPA files from 04_Application/static/.
Exposes REST endpoints for reading jobs, executing single/bulk decisions,
and managing cover letters.
"""
import json
import os
import sqlite3
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from job_registry import (
    DEFAULT_DB_PATH,
    STATE_APPLIED,
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_SKIPPED,
    bulk_transition_job_states,
    get_all_jobs_for_dashboard,
    transition_job_state,
    transition_to_applied,
)
from cover_letter_generator import generate_cover_letter
from excel_tracker_writer import (
    DEFAULT_EXCEL_PATH,
    restore_excel_backup,
    write_application_to_excel,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    db_path: Path = DEFAULT_DB_PATH
    excel_path: Path = DEFAULT_EXCEL_PATH

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, data: Any, status_code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status_code: int = 400) -> None:
        self._send_json({"success": False, "error": message}, status_code=status_code)

    def _parse_post_json(self) -> dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw_body = self.rfile.read(content_len).decode("utf-8")
        return json.loads(raw_body)

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/jobs":
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                jobs = get_all_jobs_for_dashboard(conn)
                conn.close()
                self._send_json({"success": True, "jobs": jobs})
            except Exception as exc:
                self._send_error_json(f"Database error: {exc}", 500)
            return

        if path == "/api/cover-letter/read":
            query_params = parse_qs(parsed_url.query)
            job_id_list = query_params.get("job_id")
            if not job_id_list:
                self._send_error_json("Missing job_id query parameter.")
                return
            job_id = job_id_list[0]

            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT job_id, status, cover_letter_path FROM jobs WHERE job_id = ?",
                    (job_id,),
                )
                row = cur.fetchone()
                conn.close()

                if not row:
                    self._send_error_json(f"Job ID '{job_id}' not found.", 444)
                    return

                cover_path_str = row["cover_letter_path"]
                if not cover_path_str or not os.path.exists(cover_path_str):
                    self._send_error_json(
                        f"Cover letter file for job '{job_id}' does not exist.",
                        404,
                    )
                    return

                # Validate file belongs to requested job_id
                file_name = os.path.basename(cover_path_str)
                if not file_name.startswith(job_id):
                    self._send_error_json(
                        f"Security validation failed: File '{file_name}' does not match job_id '{job_id}'."
                    )
                    return

                with open(cover_path_str, "r", encoding="utf-8") as f:
                    content = f.read()

                self._send_json(
                    {
                        "success": True,
                        "job_id": job_id,
                        "cover_letter_path": cover_path_str,
                        "content": content,
                    }
                )
            except Exception as exc:
                self._send_error_json(f"Failed to read cover letter: {exc}", 500)
            return

        # Serve static HTML/JS/CSS files
        if path == "/" or path == "":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/jobs/decide":
            try:
                payload = self._parse_post_json()
                job_id = payload.get("job_id")
                decision = payload.get("decision")  # 'Apply' or 'Skip'

                if not job_id or not decision:
                    self._send_error_json("Missing job_id or decision in request.")
                    return

                target_status = STATE_APPLY_PENDING if decision == "Apply" else STATE_SKIPPED

                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                transition_job_state(
                    conn,
                    job_id=job_id,
                    target_status=target_status,
                    human_decision=decision,
                )
                conn.close()

                self._send_json(
                    {
                        "success": True,
                        "job_id": job_id,
                        "decision": decision,
                        "new_status": target_status,
                    }
                )
            except ValueError as exc:
                self._send_error_json(str(exc), 400)
            except Exception as exc:
                self._send_error_json(f"Decide error: {exc}", 500)
            return

        if path == "/api/jobs/bulk-decide":
            try:
                payload = self._parse_post_json()
                job_ids = payload.get("job_ids", [])
                decision = payload.get("decision")  # 'Apply' or 'Skip'

                if not job_ids or not isinstance(job_ids, list) or not decision:
                    self._send_error_json("Missing job_ids array or decision in request.")
                    return

                target_status = STATE_APPLY_PENDING if decision == "Apply" else STATE_SKIPPED

                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                count = bulk_transition_job_states(
                    conn,
                    job_ids=job_ids,
                    target_status=target_status,
                    human_decision=decision,
                )
                conn.close()

                self._send_json(
                    {
                        "success": True,
                        "count": count,
                        "decision": decision,
                        "new_status": target_status,
                    }
                )
            except ValueError as exc:
                self._send_error_json(str(exc), 400)
            except Exception as exc:
                self._send_error_json(f"Bulk decide error: {exc}", 500)
            return

        if path == "/api/cover-letter/generate":
            try:
                payload = self._parse_post_json()
                job_id = payload.get("job_id")
                if not job_id:
                    self._send_error_json("Missing job_id in request.")
                    return

                text, file_path = generate_cover_letter(
                    job_id=job_id,
                    db_path=self.db_path,
                )
                self._send_json(
                    {
                        "success": True,
                        "job_id": job_id,
                        "cover_letter_path": file_path,
                        "content": text,
                    }
                )
            except ValueError as exc:
                self._send_error_json(str(exc), 400)
            except Exception as exc:
                self._send_error_json(f"Generation error: {exc}", 500)
            return

        if path == "/api/cover-letter/save":
            try:
                payload = self._parse_post_json()
                job_id = payload.get("job_id")
                content = payload.get("content")

                if not job_id or content is None:
                    self._send_error_json("Missing job_id or content in request.")
                    return

                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT job_id, status, cover_letter_path FROM jobs WHERE job_id = ?",
                    (job_id,),
                )
                row = cur.fetchone()

                if not row:
                    conn.close()
                    self._send_error_json(f"Job ID '{job_id}' not found.", 404)
                    return

                current_status = row["status"]
                cover_path_str = row["cover_letter_path"]

                if current_status != STATE_COVER_LETTER_GENERATED:
                    conn.close()
                    self._send_error_json(
                        f"Save Edits is permitted only for jobs in '{STATE_COVER_LETTER_GENERATED}' status."
                    )
                    return

                if not cover_path_str or not os.path.exists(cover_path_str):
                    conn.close()
                    self._send_error_json(
                        f"Cover letter file for job '{job_id}' not found on disk."
                    )
                    return

                # Validate file belongs to requested job_id
                file_name = os.path.basename(cover_path_str)
                if not file_name.startswith(job_id):
                    conn.close()
                    self._send_error_json(
                        f"Security validation failed: File '{file_name}' does not match job_id '{job_id}'."
                    )
                    return

                # Overwrite file directly without any LLM calls or state changes
                with open(cover_path_str, "w", encoding="utf-8") as f:
                    f.write(content)

                conn.close()
                self._send_json(
                    {
                        "success": True,
                        "job_id": job_id,
                        "cover_letter_path": cover_path_str,
                        "message": "Saved edits successfully.",
                    }
                )
            except Exception as exc:
                self._send_error_json(f"Save edits error: {exc}", 500)
            return

        if path == "/api/jobs/apply":
            body = self._parse_post_json()
            job_id = body.get("job_id")
            application_url = body.get("application_url")
            custom_notes = body.get("notes")
            custom_work_type = body.get("work_type")

            if not job_id:
                self._send_error_json("Missing job_id parameter", 400)
                return

            try:
                # 1. Fetch job record from SQLite
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cur.fetchone()
                if not row:
                    conn.close()
                    self._send_error_json(f"Job ID '{job_id}' not found in database.", 404)
                    return

                job_dict = dict(row)
                conn.close()

                # 2. Write application into Excel tracker
                excel_res = write_application_to_excel(
                    excel_path=self.excel_path,
                    job_data=job_dict,
                    application_url=application_url,
                    custom_notes=custom_notes,
                    custom_work_type=custom_work_type,
                )

                app_id = excel_res["excel_app_id"]
                backup_path = Path(excel_res["backup_path"])

                # 3. Commit SQLite state transition
                try:
                    conn2 = sqlite3.connect(self.db_path)
                    transition_to_applied(conn2, job_id, app_id)
                    conn2.close()
                except Exception as db_exc:
                    # SQLite commit failed! Restore Excel backup!
                    restore_excel_backup(self.excel_path, backup_path)
                    self._send_error_json(
                        f"SQLite update failed: {db_exc}. Excel changes rolled back.", 500
                    )
                    return

                # Clean up backup file after successful commit
                if backup_path.exists():
                    try:
                        os.remove(backup_path)
                    except Exception:
                        pass

                self._send_json(
                    {
                        "success": True,
                        "job_id": job_id,
                        "status": STATE_APPLIED,
                        "excel_app_id": app_id,
                        "message": f"Successfully marked job {job_id} as APPLIED in slot {app_id}.",
                    }
                )
            except Exception as exc:
                self._send_error_json(f"Mark Applied error: {exc}", 500)
            return

        self._send_error_json(f"Endpoint not found: {path}", 404)


def create_server(
    port: int = 8080, db_path: Optional[Path] = None, excel_path: Optional[Path] = None
) -> HTTPServer:
    DashboardRequestHandler.db_path = db_path or DEFAULT_DB_PATH
    DashboardRequestHandler.excel_path = excel_path or DEFAULT_EXCEL_PATH
    server = HTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    return server


if __name__ == "__main__":
    server = create_server(8080)
    print("=" * 70)
    print("CAREER ASSISTANT — HUMAN REVIEW DASHBOARD SERVER")
    print("Server running at: http://127.0.0.1:8080")
    print("=" * 70)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()
