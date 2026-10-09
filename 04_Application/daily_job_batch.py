import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from career_evidence_catalog_builder import (
    load_saved_career_evidence_catalog,
)

from gmail_client import (
    build_gmail_service,
    extract_message_content,
)

from job_analysis_reasoner import (
    MODEL_NAME,
    REASONING_EFFORT,
    REQUEST_TIMEOUT_SECONDS,
    analyse_job,
)

from job_analysis_schema import JobAnalysisResult

from job_page_retriever import (
    retrieve_jobstreet_page,
)

from job_registry import (
    DEFAULT_DB_PATH,
    STATE_ANALYSIS_FAILED,
    STATE_APPLIED,
    STATE_APPLY_PENDING,
    STATE_COVER_LETTER_GENERATED,
    STATE_DISCOVERED,
    STATE_RETRIEVAL_FAILED,
    STATE_RETRIEVED,
    STATE_REVIEW_PENDING,
    STATE_SKIPPED,
    count_eligible_jobs_for_analysis,
    get_eligible_jobs_for_analysis,
    get_job,
    get_job_sources,
    get_system_metadata,
    init_db,
    register_job_candidate,
    set_system_metadata,
    update_analysis_failure,
    update_analysis_success,
    update_retrieval_failure,
    update_retrieval_success,
)

from run_live_jobstreet_benchmark import (
    get_confirmed_jobstreet_url,
)

from url_extractor import (
    classify_structured_link,
    deduplicate_job_links,
)

# Set stdout encoding for Windows compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "05_Evaluation"
    / "Daily_Batch"
)

GMAIL_PAGE_SIZE = 50
MAX_AUTOMATIC_LOOKBACK_DAYS = 30
MAX_ANALYSES_PER_RUN = 25


def format_duration_human(total_seconds: float) -> str:
    secs = int(round(total_seconds))
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    seconds = secs % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    elif minutes > 0:
        return f"{minutes}m {seconds:02d}s"
    else:
        return f"{seconds}s"


def compute_stage_3b_timing_stats(
    job_durations: list[float],
    total_elapsed_seconds: float,
    remaining_backlog: int,
    max_analyses: int = MAX_ANALYSES_PER_RUN,
) -> dict[str, Any]:
    jobs_processed = len(job_durations)
    estimated_additional_runs = (
        math.ceil(remaining_backlog / max_analyses) if max_analyses > 0 else 0
    )

    if jobs_processed == 0:
        return {
            "jobs_processed": 0,
            "elapsed_seconds": 0.0,
            "formatted_elapsed": "0s",
            "average_seconds_per_job": None,
            "fastest_seconds": None,
            "slowest_seconds": None,
            "median_seconds": None,
            "remaining_backlog": remaining_backlog,
            "estimated_additional_runs": estimated_additional_runs,
        }

    durations_sorted = sorted(job_durations)
    avg_sec = round(sum(job_durations) / jobs_processed, 1)
    fastest_sec = round(durations_sorted[0], 1)
    slowest_sec = round(durations_sorted[-1], 1)

    n = jobs_processed
    if n % 2 == 1:
        median_sec = round(durations_sorted[n // 2], 1)
    else:
        median_sec = round(
            (durations_sorted[n // 2 - 1] + durations_sorted[n // 2]) / 2.0, 1
        )

    return {
        "jobs_processed": jobs_processed,
        "elapsed_seconds": round(total_elapsed_seconds, 1),
        "formatted_elapsed": format_duration_human(total_elapsed_seconds),
        "average_seconds_per_job": avg_sec,
        "fastest_seconds": fastest_sec,
        "slowest_seconds": slowest_sec,
        "median_seconds": median_sec,
        "remaining_backlog": remaining_backlog,
        "estimated_additional_runs": estimated_additional_runs,
    }
METADATA_KEY_LAST_ACQUISITION = "last_successful_acquisition_date"


# ---------------------------------------------------------------------------
# SGT Date & Gmail Query Helpers
# ---------------------------------------------------------------------------

def parse_date_str(d_str: str) -> datetime.date:
    clean = d_str.replace("/", "-")
    parts = list(map(int, clean.split("-")))
    return datetime(parts[0], parts[1], parts[2]).date()


def format_date_str(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def compute_sgt_epochs(date_str: str) -> tuple[int, int]:
    """
    Computes start and end Unix epoch seconds for a given SGT date_str ('YYYY/MM/DD' or 'YYYY-MM-DD').
    SGT is UTC+8.
    Start: date_str 00:00:00 SGT
    End: (date_str + 1 day) 00:00:00 SGT
    """
    clean_date = date_str.replace("-", "/")
    year, month, day = map(int, clean_date.split("/"))

    sgt_tz = timezone(timedelta(hours=8))
    dt_start = datetime(year, month, day, 0, 0, 0, tzinfo=sgt_tz)
    dt_end = dt_start + timedelta(days=1)

    return int(dt_start.timestamp()), int(dt_end.timestamp())


def get_current_sgt_date_str() -> str:
    """
    Returns current date string YYYY-MM-DD in Asia/Singapore timezone (UTC+8).
    """
    sgt_tz = timezone(timedelta(hours=8))
    return datetime.now(sgt_tz).strftime("%Y-%m-%d")


def compute_acquisition_date_range(
    current_sgt_date_str: str,
    last_successful_date_str: Optional[str],
) -> tuple[str, str, int, Optional[str]]:
    """
    Computes (start_date_str, end_date_str, scan_days, warning).
    All date strings returned in YYYY-MM-DD format.
    """
    current_date = parse_date_str(current_sgt_date_str)
    curr_formatted = format_date_str(current_date)

    if not last_successful_date_str:
        return curr_formatted, curr_formatted, 1, None

    last_date = parse_date_str(last_successful_date_str)

    if last_date >= current_date:
        # Same day rerun or future date
        return curr_formatted, curr_formatted, 1, None

    gap_days = (current_date - last_date).days
    start_candidate = last_date + timedelta(days=1)

    if gap_days <= MAX_AUTOMATIC_LOOKBACK_DAYS:
        scan_days = (current_date - start_candidate).days + 1
        return format_date_str(start_candidate), curr_formatted, scan_days, None
    else:
        # Gap > 30 days
        capped_start = current_date - timedelta(days=MAX_AUTOMATIC_LOOKBACK_DAYS - 1)
        omitted_end = capped_start - timedelta(days=1)
        warning = (
            f"Last successful acquisition was {gap_days} days ago.\n"
            f"Automatic catch-up is limited to {MAX_AUTOMATIC_LOOKBACK_DAYS} days ({format_date_str(capped_start)} to {curr_formatted}).\n"
            f"To acquire older omitted dates (e.g. {format_date_str(start_candidate)} to {format_date_str(omitted_end)}), run:\n"
            f"  python 04_Application/daily_job_batch.py --start-date {format_date_str(start_candidate)} --end-date {format_date_str(omitted_end)}"
        )
        return format_date_str(capped_start), curr_formatted, MAX_AUTOMATIC_LOOKBACK_DAYS, warning


def collect_candidates_for_range(
    service,
    start_date_str: str,
    end_date_str: str,
) -> tuple[list[dict[str, Any]], int, int, str]:
    """
    Collect all JobStreet job candidate links from Gmail messages
    matching SGT date range [start_date_str, end_date_str] inclusive using exact epoch boundaries.
    """
    start_epoch, _ = compute_sgt_epochs(start_date_str)
    _, end_epoch = compute_sgt_epochs(end_date_str)
    query = f"after:{start_epoch} before:{end_epoch}"

    candidates = []
    page_token = None
    pages_fetched = 0
    messages_fetched = 0

    while True:
        list_kwargs = {
            "userId": "me",
            "maxResults": GMAIL_PAGE_SIZE,
            "q": query,
        }
        if page_token:
            list_kwargs["pageToken"] = page_token

        response = (
            service.users()
            .messages()
            .list(**list_kwargs)
            .execute()
        )

        pages_fetched += 1
        messages = response.get("messages", [])
        messages_fetched += len(messages)

        for message in messages:
            message_data = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=message["id"],
                    format="full",
                )
                .execute()
            )

            extracted = extract_message_content(message_data)

            job_links = []
            for link in extracted["html_links"]:
                link_type = classify_structured_link(
                    text=link["text"],
                    url=link["href"],
                )
                if link_type != "jobstreet_job_candidate":
                    continue
                job_links.append(
                    {
                        "text": link["text"],
                        "href": link["href"],
                        "type": link_type,
                    }
                )

            job_links = deduplicate_job_links(job_links)

            for link in job_links:
                candidates.append(
                    {
                        "email_subject": extracted["subject"],
                        "email_from": extracted["from"],
                        "email_date": extracted["date"],
                        "anchor_text": link["text"],
                        "tracking_url": link["href"],
                    }
                )

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return candidates, pages_fetched, messages_fetched, query


# ---------------------------------------------------------------------------
# Stage 3A - acquisition, resolution, and SQLite registry indexing
# ---------------------------------------------------------------------------

def run_stage_3a(
    batch_date_str: Optional[str] = None,
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Gmail acquisition -> URL resolution -> global job-ID deduplication -> SQLite indexing.
    No GPT-OSS calls made.
    Returns a dict suitable for printing and for passing into run_stage_3b().
    """
    print()
    print("Stage 3A: Acquisition and Deduplication")
    print("========================================")
    print()

    conn = init_db(db_path)
    today_sgt = get_current_sgt_date_str()
    last_acq = get_system_metadata(conn, METADATA_KEY_LAST_ACQUISITION)

    if start_date_str and end_date_str:
        s_date = start_date_str.replace("/", "-")
        e_date = end_date_str.replace("/", "-")
        scan_days = (parse_date_str(e_date) - parse_date_str(s_date)).days + 1
        start_date_str, end_date_str = s_date, e_date
        warning = None
    elif batch_date_str:
        start_date_str = batch_date_str.replace("/", "-")
        end_date_str = start_date_str
        scan_days = 1
        warning = None
    else:
        start_date_str, end_date_str, scan_days, warning = compute_acquisition_date_range(
            today_sgt, last_acq
        )

    print(f"Today SGT:                   {today_sgt}")
    print(f"Last successful acquisition: {last_acq or 'None'}")
    print(f"Acquisition window:          {start_date_str} to {end_date_str}")
    print(f"Days scanned:                {scan_days}")
    if warning:
        print(f"[WARNING] {warning}")
    print()

    service = build_gmail_service()

    print("Collecting Gmail candidates...")
    print()

    candidates, pages_fetched, messages_fetched, query = collect_candidates_for_range(
        service, start_date_str, end_date_str
    )

    print(f"Gmail query string: {query}")
    print(f"Gmail API pages fetched: {pages_fetched}")
    print(f"Messages processed: {messages_fetched}")
    print(f"Raw JobStreet candidate links: {len(candidates)}")
    print()
    print("Resolving tracking URLs and updating SQLite job registry...")
    print()

    unique_jobs_map: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    intra_batch_duplicates = 0
    new_unique_jobs_registered = 0
    previously_known_unique_jobs = 0

    for candidate in candidates:
        tracking_url = candidate["tracking_url"]
        confirmed = get_confirmed_jobstreet_url(tracking_url)

        if confirmed is None:
            unresolved.append(
                {
                    "tracking_url": tracking_url,
                    "anchor_text": candidate["anchor_text"],
                    "email_subject": candidate["email_subject"],
                    "reason": (
                        "Resolution failed or not a canonical JobStreet job URL"
                    ),
                }
            )
            continue

        job_id, confirmed_url = confirmed

        if job_id in unique_jobs_map:
            intra_batch_duplicates += 1
            unique_jobs_map[job_id]["source_candidates"].append(candidate)
            register_job_candidate(
                conn, job_id=job_id, confirmed_url=confirmed_url, candidate=candidate
            )
            continue

        existing_rec = get_job(conn, job_id)
        if existing_rec is None:
            new_unique_jobs_registered += 1
        else:
            previously_known_unique_jobs += 1

        job_record = register_job_candidate(
            conn, job_id=job_id, confirmed_url=confirmed_url, candidate=candidate
        )

        print(
            f"  [{len(unique_jobs_map) + 1}] JOBSTREET-{job_id} ({job_record['status']})"
        )
        print(f"      URL: {confirmed_url}")
        print(f"      From: {candidate['anchor_text']}")

        unique_jobs_map[job_id] = {
            "job_id": job_id,
            "confirmed_url": confirmed_url,
            "source_candidates": [candidate],
            "registry_status": job_record["status"],
        }

    unique_jobs = list(unique_jobs_map.values())

    print()
    print("STAGE 3A SUMMARY")
    print("----------------")
    print(f"Gmail messages processed:         {messages_fetched}")
    print(f"Raw candidate links:              {len(candidates)}")
    print(f"Unresolved / not a job URL:       {len(unresolved)}")
    print(f"Intra-batch duplicate occurrences:{intra_batch_duplicates}")
    print(f"Unique canonical job IDs:         {len(unique_jobs)}")
    print(f"Previously known unique jobs:     {previously_known_unique_jobs}")
    print(f"New unique jobs registered:       {new_unique_jobs_registered}")

    # Reconciliation check
    expected = len(candidates) - len(unresolved) - intra_batch_duplicates
    if (
        expected == len(unique_jobs)
        and len(unique_jobs) == (new_unique_jobs_registered + previously_known_unique_jobs)
    ):
        print(
            f"Count reconciliation: OK "
            f"({len(candidates)} - {len(unresolved)} - "
            f"{intra_batch_duplicates} = {len(unique_jobs)} = "
            f"{new_unique_jobs_registered} + {previously_known_unique_jobs})"
        )
    else:
        print(
            f"Count reconciliation: MISMATCH "
            f"(expected {expected}, got {len(unique_jobs)})"
        )

    # Persist last_successful_acquisition_date upon successful Stage 3A completion
    set_system_metadata(conn, METADATA_KEY_LAST_ACQUISITION, end_date_str)

    conn.close()

    return {
        "batch_date": end_date_str,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "scan_days": scan_days,
        "gmail_query": query,
        "pages_fetched": pages_fetched,
        "messages_fetched": messages_fetched,
        "raw_candidates": len(candidates),
        "unresolved": unresolved,
        "unresolved_count": len(unresolved),
        "duplicates_removed": intra_batch_duplicates,
        "intra_batch_duplicates": intra_batch_duplicates,
        "unique_jobs": unique_jobs,
        "unique_jobs_count": len(unique_jobs),
        "known_historical_jobs": previously_known_unique_jobs,
        "previously_known_unique_jobs": previously_known_unique_jobs,
        "new_jobs_registered": new_unique_jobs_registered,
        "new_unique_jobs_registered": new_unique_jobs_registered,
    }


# ---------------------------------------------------------------------------
# Stage 3B - bounded LLM analysis and report
# ---------------------------------------------------------------------------

def run_stage_3b(
    acquisition: dict[str, Any],
    max_analyses: int = MAX_ANALYSES_PER_RUN,
    db_path: Optional[Path] = None,
) -> None:
    """
    Queries SQLite for eligible jobs needing analysis (ordered by first_seen ASC, job_id ASC),
    and performs Playwright retrieval + GPT-OSS analysis for up to max_analyses jobs.
    Persists remaining backlog for subsequent runs.
    """
    batch_date_str = acquisition.get("end_date", acquisition.get("batch_date"))

    conn = init_db(db_path)
    eligible_backlog_total = count_eligible_jobs_for_analysis(conn)
    eligible_jobs = get_eligible_jobs_for_analysis(conn, limit=max_analyses)

    print()
    print("Stage 3B: Analysis & State-Machine Processing")
    print("=============================================")
    print()
    print(f"Model: {MODEL_NAME}")
    print(f"Reasoning effort: {REASONING_EFFORT}")
    print(f"Request timeout: {REQUEST_TIMEOUT_SECONDS}s")
    print(f"Eligible analysis backlog before run: {eligible_backlog_total}")
    print(f"Analysis limit this run:              {max_analyses}")
    print(f"Jobs to analyse this run:             {len(eligible_jobs)}")
    print()

    stage_3b_start_time = time.perf_counter()
    job_durations: list[float] = []

    if not eligible_jobs:
        print("No analysis required.")
        remaining_backlog = count_eligible_jobs_for_analysis(conn)
        conn.close()

        timing_stats = compute_stage_3b_timing_stats(
            job_durations=[],
            total_elapsed_seconds=0.0,
            remaining_backlog=remaining_backlog,
            max_analyses=max_analyses,
        )

        print()
        print("STAGE 3B RUNTIME SUMMARY")
        print("------------------------")
        print("Jobs processed this run:          0")
        print("No Stage 3B timing statistics available.")
        print(f"Remaining analysis backlog:       {timing_stats['remaining_backlog']}")
        print(f"Estimated additional runs @{max_analyses}:    {timing_stats['estimated_additional_runs']}")

        _write_report(
            batch_date_str=batch_date_str,
            acquisition=acquisition,
            successful=[],
            retrieval_failures=[],
            analysis_failures=[],
            accounting={
                "eligible_backlog_before": eligible_backlog_total,
                "max_analyses_limit": max_analyses,
                "analysed_this_run": 0,
                "remaining_backlog": remaining_backlog,
                "retrieval_failures": 0,
                "analysis_failures": 0,
            },
            timing_stats=timing_stats,
        )
        return

    catalog = load_saved_career_evidence_catalog()
    if len(catalog.evidence_items) != 154:
        raise AssertionError(
            "Expected frozen 154-item career evidence catalog."
        )

    successful: list[dict[str, Any]] = []
    retrieval_failures: list[dict[str, Any]] = []
    analysis_failures: list[dict[str, Any]] = []

    retryable_jobs_encountered = 0
    new_jobs_requiring_processing = 0
    new_analyses_completed = 0

    for i, job_rec in enumerate(eligible_jobs, start=1):
        job_id = job_rec["job_id"]
        confirmed_url = job_rec["confirmed_url"]
        source_reference = f"JOBSTREET-{job_id}"
        status = job_rec["status"]

        print(f"[{i}/{len(eligible_jobs)}] {source_reference} (Current Status: {status})")
        print(f"  URL: {confirmed_url}")

        job_start_time = time.perf_counter()
        cleaned_text = job_rec.get("cleaned_text")

        if not cleaned_text or status in (STATE_DISCOVERED, STATE_RETRIEVAL_FAILED):
            if status == STATE_RETRIEVAL_FAILED:
                retryable_jobs_encountered += 1
                print("  RETRY: Retrying Playwright retrieval after previous failure...")
            else:
                new_jobs_requiring_processing += 1

            print("  Retrieving JobStreet page via Playwright...")
            try:
                page_result = retrieve_jobstreet_page(confirmed_url)
            except Exception as exc:
                err_msg = f"Playwright Exception: {exc}"
                update_retrieval_failure(conn, job_id, err_msg)
                retrieval_failures.append(
                    {
                        "job_id": job_id,
                        "confirmed_url": confirmed_url,
                        "stage": "retrieval",
                        "error": err_msg,
                    }
                )
                job_elapsed = time.perf_counter() - job_start_time
                job_durations.append(job_elapsed)
                print(f"  RETRIEVAL ERROR: {err_msg} (Completed in {job_elapsed:.1f}s)")
                print()
                continue

            if not page_result["success"] or not page_result.get("cleaned_text", "").strip():
                err_msg = page_result.get("error", "Empty cleaned text or retrieval failed")
                update_retrieval_failure(conn, job_id, err_msg)
                retrieval_failures.append(
                    {
                        "job_id": job_id,
                        "confirmed_url": confirmed_url,
                        "stage": "retrieval",
                        "error": err_msg,
                    }
                )
                job_elapsed = time.perf_counter() - job_start_time
                job_durations.append(job_elapsed)
                print(f"  RETRIEVAL FAILED: {err_msg} (Completed in {job_elapsed:.1f}s)")
                print()
                continue

            cleaned_text = page_result["cleaned_text"]
            update_retrieval_success(conn, job_id, cleaned_text)
            print(f"  Retrieved & Persisted: {len(cleaned_text)} chars")
        else:
            print(f"  REUSE TEXT: Using persisted cleaned_text ({len(cleaned_text)} chars)")

        if status == STATE_ANALYSIS_FAILED:
            retryable_jobs_encountered += 1
            print("  RETRY: Retrying GPT-OSS analysis from persisted text after previous failure...")

        print("  Running GPT-OSS grounded analysis call...")
        try:
            analysis = analyse_job(
                job_text=cleaned_text,
                source_reference=source_reference,
                job_url=confirmed_url,
                catalog=catalog,
            )
        except Exception as exc:
            err_msg = f"Analysis Exception: {exc}"
            update_analysis_failure(conn, job_id, err_msg)
            analysis_failures.append(
                {
                    "job_id": job_id,
                    "confirmed_url": confirmed_url,
                    "stage": "analysis",
                    "error": err_msg,
                }
            )
            job_elapsed = time.perf_counter() - job_start_time
            job_durations.append(job_elapsed)
            print(f"  ANALYSIS ERROR: {err_msg} (Completed in {job_elapsed:.1f}s)")
            print()
            continue

        analysis_json = analysis.model_dump_json()
        update_analysis_success(
            conn,
            job_id=job_id,
            analysis_result_json=analysis_json,
            recommended_priority=analysis.priority,
            recommended_action=analysis.action,
        )
        new_analyses_completed += 1

        successful.append(
            {
                "job_id": job_id,
                "confirmed_url": confirmed_url,
                "analysis": analysis,
                "resurfaced": False,
            }
        )

        job_elapsed = time.perf_counter() - job_start_time
        job_durations.append(job_elapsed)
        print(
            f"  DONE: {analysis.job.role} @ {analysis.job.company} - "
            f"{analysis.priority} / {analysis.action} (Completed in {job_elapsed:.1f}s)"
        )
        print()

    stage_3b_end_time = time.perf_counter()
    total_elapsed_seconds = stage_3b_end_time - stage_3b_start_time

    remaining_backlog = count_eligible_jobs_for_analysis(conn)
    conn.close()

    timing_stats = compute_stage_3b_timing_stats(
        job_durations=job_durations,
        total_elapsed_seconds=total_elapsed_seconds,
        remaining_backlog=remaining_backlog,
        max_analyses=max_analyses,
    )

    print()
    print("STAGE 3B RUNTIME SUMMARY")
    print("------------------------")
    if timing_stats["jobs_processed"] > 0:
        print(f"Jobs processed this run:          {timing_stats['jobs_processed']}")
        print(f"Total elapsed time:               {timing_stats['formatted_elapsed']}")
        print(f"Average time per processed job:   {timing_stats['average_seconds_per_job']:.1f}s")
        print(f"Fastest processed job:            {timing_stats['fastest_seconds']:.1f}s")
        print(f"Slowest processed job:            {timing_stats['slowest_seconds']:.1f}s")
        print(f"Median processed job time:        {timing_stats['median_seconds']:.1f}s")
        print(f"Remaining analysis backlog:       {timing_stats['remaining_backlog']}")
        print(f"Estimated additional runs @{max_analyses}:    {timing_stats['estimated_additional_runs']}")
    else:
        print("Jobs processed this run:          0")
        print("No Stage 3B timing statistics available.")
        print(f"Remaining analysis backlog:       {timing_stats['remaining_backlog']}")
        print(f"Estimated additional runs @{max_analyses}:    {timing_stats['estimated_additional_runs']}")

    _write_report(
        batch_date_str=batch_date_str,
        acquisition=acquisition,
        successful=successful,
        retrieval_failures=retrieval_failures,
        analysis_failures=analysis_failures,
        accounting={
            "eligible_backlog_before": eligible_backlog_total,
            "max_analyses_limit": max_analyses,
            "analysed_this_run": new_analyses_completed,
            "remaining_backlog": remaining_backlog,
            "retrieval_failures": len(retrieval_failures),
            "analysis_failures": len(analysis_failures),
        },
        timing_stats=timing_stats,
    )


# ---------------------------------------------------------------------------
# Consolidated Daily Report Writer
# ---------------------------------------------------------------------------

def _write_report(
    batch_date_str: str,
    acquisition: dict[str, Any],
    successful: list[dict[str, Any]],
    retrieval_failures: list[dict[str, Any]],
    analysis_failures: list[dict[str, Any]],
    accounting: dict[str, int],
    timing_stats: Optional[dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
) -> None:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    date_tag = batch_date_str.replace("/", "-")
    report_path = target_dir / f"daily_report_{date_tag}.txt"
    json_path = target_dir / f"daily_report_{date_tag}.json"

    lines: list[str] = []

    def h(text: str) -> None:
        lines.append(text)

    h("Daily Job Analysis Report")
    h("=========================")
    h(f"Batch date (SGT): {batch_date_str}")
    h(f"Model: {MODEL_NAME}")
    h(f"Reasoning effort: {REASONING_EFFORT}")
    h("")
    h("ACQUISITION & REGISTRY SUMMARY")
    h("------------------------------")
    h(f"Acquisition window: {acquisition.get('start_date', batch_date_str)} to {acquisition.get('end_date', batch_date_str)}")
    h(f"Days scanned: {acquisition.get('scan_days', 1)}")
    h(f"Gmail query string: {acquisition['gmail_query']}")
    h(f"Messages processed: {acquisition['messages_fetched']}")
    h(f"Raw candidate links: {acquisition['raw_candidates']}")
    h(f"Unresolved candidate links: {len(acquisition['unresolved'])}")
    h(f"Intra-batch duplicate occurrences: {acquisition.get('intra_batch_duplicates', acquisition.get('duplicates_removed', 0))}")
    h(f"Unique canonical job IDs in batch: {len(acquisition['unique_jobs'])}")
    h(f"Previously known unique jobs: {acquisition.get('previously_known_unique_jobs', acquisition.get('known_historical_jobs', 0))}")
    h(f"New unique jobs registered: {acquisition.get('new_unique_jobs_registered', acquisition.get('new_jobs_registered', 0))}")
    h("")
    h("ANALYSIS WORKLOAD & BACKLOG SUMMARY")
    h("-----------------------------------")
    h(f"Eligible analysis backlog before run: {accounting.get('eligible_backlog_before', 0)}")
    h(f"Analysis limit this run:              {accounting.get('max_analyses_limit', 10)}")
    h(f"New GPT-OSS analyses completed:       {accounting.get('analysed_this_run', 0)}")
    h(f"Remaining analysis backlog:           {accounting.get('remaining_backlog', 0)}")
    h(f"Retrieval failures:                   {accounting.get('retrieval_failures', 0)}")
    h(f"Analysis failures:                    {accounting.get('analysis_failures', 0)}")
    h("")

    if timing_stats:
        h("STAGE 3B RUNTIME SUMMARY")
        h("------------------------")
        if timing_stats.get("jobs_processed", 0) > 0:
            h(f"Jobs processed this run:          {timing_stats['jobs_processed']}")
            h(f"Total elapsed time:               {timing_stats['formatted_elapsed']}")
            h(f"Average time per processed job:   {timing_stats['average_seconds_per_job']:.1f}s")
            h(f"Fastest processed job:            {timing_stats['fastest_seconds']:.1f}s")
            h(f"Slowest processed job:            {timing_stats['slowest_seconds']:.1f}s")
            h(f"Median processed job time:        {timing_stats['median_seconds']:.1f}s")
            h(f"Remaining analysis backlog:       {timing_stats['remaining_backlog']}")
            h(f"Estimated additional runs:        {timing_stats['estimated_additional_runs']}")
        else:
            h("Jobs processed this run:          0")
            h("No Stage 3B timing statistics available.")
            h(f"Remaining analysis backlog:       {timing_stats.get('remaining_backlog', 0)}")
            h(f"Estimated additional runs:        {timing_stats.get('estimated_additional_runs', 0)}")
        h("")

    if successful:
        h("RESULTS FOR HUMAN REVIEW")
        h("========================")
        h("")
        for item in successful:
            a: JobAnalysisResult = item["analysis"]
            tag = " [RESURFACED]" if item.get("resurfaced") else ""
            h(f"Job: JOBSTREET-{item['job_id']}{tag}")
            h(f"URL: {item['confirmed_url']}")
            h(f"Company: {a.job.company}")
            h(f"Role: {a.job.role}")
            h(f"Location: {a.job.location}")
            h(f"Work mode: {a.job.work_mode}")
            h(f"Employment type: {a.job.employment_type}")
            h(f"Salary: {a.job.salary}")
            h("")
            h(f"PRIORITY: {a.priority}  |  ACTION: {a.action}")
            h(f"Summary: {a.summary}")
            h(f"Tracker note: {a.tracker_note}")
            h("")
            h("Key Matches:")
            if a.key_matches:
                for match in a.key_matches:
                    h(f"  - {match}")
            else:
                h("  - None stated")
            h("")
            h("Key Gaps:")
            if a.key_gaps:
                for gap in a.key_gaps:
                    h(f"  - {gap}")
            else:
                h("  - None identified")
            h("")
            h("-" * 60)
            h("")

    if retrieval_failures:
        h("RETRIEVAL FAILURES")
        h("==================")
        h("")
        for f in retrieval_failures:
            h(f"JOBSTREET-{f['job_id']}: {f['error']}")
            h(f"  URL: {f['confirmed_url']}")
            h("")

    if analysis_failures:
        h("ANALYSIS FAILURES")
        h("=================")
        h("")
        for f in analysis_failures:
            h(f"JOBSTREET-{f['job_id']}: {f['error']}")
            h(f"  URL: {f['confirmed_url']}")
            h("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    json_data = {
        "batch_date": batch_date_str,
        "acquisition": {
            "start_date": acquisition.get("start_date", batch_date_str),
            "end_date": acquisition.get("end_date", batch_date_str),
            "scan_days": acquisition.get("scan_days", 1),
            "gmail_query": acquisition["gmail_query"],
            "messages_fetched": acquisition["messages_fetched"],
            "raw_candidates": acquisition["raw_candidates"],
            "unresolved_count": len(acquisition["unresolved"]),
            "duplicates_removed": acquisition.get("intra_batch_duplicates", acquisition.get("duplicates_removed", 0)),
            "intra_batch_duplicates": acquisition.get("intra_batch_duplicates", acquisition.get("duplicates_removed", 0)),
            "unique_jobs_count": len(acquisition["unique_jobs"]),
            "known_historical_jobs": acquisition.get("previously_known_unique_jobs", acquisition.get("known_historical_jobs", 0)),
            "previously_known_unique_jobs": acquisition.get("previously_known_unique_jobs", acquisition.get("known_historical_jobs", 0)),
            "new_jobs_registered": acquisition.get("new_unique_jobs_registered", acquisition.get("new_jobs_registered", 0)),
            "new_unique_jobs_registered": acquisition.get("new_unique_jobs_registered", acquisition.get("new_jobs_registered", 0)),
        },
        "accounting": accounting,
        "stage_3b_runtime": timing_stats,
        "results": {
            "total_successful": len(successful),
            "retrieval_failures_count": len(retrieval_failures),
            "analysis_failures_count": len(analysis_failures),
        },
    }

    json_path.write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("DAILY REPORT WRITTEN")
    print("====================")
    print(f"Text: {report_path}")
    print(f"JSON: {json_path}")
    print()
    print(f"Total jobs for human review: {len(successful)}")
    print(f"New analyses completed:        {accounting.get('analysed_this_run', 0)}")
    print(f"Remaining backlog:             {accounting.get('remaining_backlog', 0)}")
    print(f"Retrieval failures:            {len(retrieval_failures)}")
    print(f"Analysis failures:             {len(analysis_failures)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Daily JobStreet batch with missed-day catch-up and bounded LLM analysis. "
            "Default: Stage 3A only. Use --analyse to run Stage 3B."
        )
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Single batch date as YYYY/MM/DD or YYYY-MM-DD (default: automatic catch-up range)",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Explicit start date YYYY-MM-DD for historical catch-up range",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Explicit end date YYYY-MM-DD for historical catch-up range",
    )
    parser.add_argument(
        "--max-analyses",
        type=int,
        default=MAX_ANALYSES_PER_RUN,
        help=f"Maximum LLM analyses to perform in this run (default: {MAX_ANALYSES_PER_RUN})",
    )
    parser.add_argument(
        "--analyse",
        action="store_true",
        help="Run Stage 3B: perform bounded LLM analysis up to --max-analyses limit.",
    )
    args = parser.parse_args()

    acquisition = run_stage_3a(
        batch_date_str=args.date,
        start_date_str=args.start_date,
        end_date_str=args.end_date,
    )

    if not args.analyse:
        print()
        print("Stage 3A complete. Job candidates indexed in SQLite registry.")
        print("Run with --analyse to proceed to Stage 3B (GPT-OSS analysis).")
        return

    run_stage_3b(acquisition, max_analyses=args.max_analyses)


if __name__ == "__main__":
    main()
