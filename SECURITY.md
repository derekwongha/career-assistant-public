# Security and privacy

This document describes the protections that exist in this repository's code
and configuration. It does not describe anything that is not implemented.

## What is never committed

`.gitignore` blocks:

| Pattern | Why |
|---|---|
| `credentials.json`, `token.json` (any folder) | Your Google OAuth client secret and refresh token |
| `.env`, `.env.*` (except `.env.example`) | Local configuration |
| `*.sqlite`, `*.sqlite-journal`, `*.db` | The job registry database (real job data and decisions) |
| `05_Evaluation/` | Daily reports, generated cover letters, benchmark outputs |
| `cover_letters/`, `data/` | Generated letters and your tracker location |
| `*.xlsx`, `*.xlsm`, `*.xls` | Application tracker workbooks |
| `04_Application/career_evidence_catalog.json` | Your personal evidence catalog at its default path |
| `examples/demo/output/` | Regenerated synthetic demo data |
| `*.log`, `logs/`, caches | Logs and tool caches |

`.gitignore` only prevents accidental staging. Before every commit, still check
`git status` and `git diff --staged`.

## Gmail access is read-only

`04_Application/gmail_client.py` requests a single OAuth scope:

```
https://www.googleapis.com/auth/gmail.readonly
```

With this scope the application cannot send, delete, label, archive or modify
email. `gmail_oauth_recovery_test.py` asserts the scope list is exactly this
one value. You create and keep your own OAuth client in your own Google Cloud
project; none is shipped with this repository.

Note: the daily batch queries Gmail by date range, so it reads every message in
that range (read-only) and extracts JobStreet job links from them. A dedicated
job-search Gmail account is recommended.

## Network activity

The code makes these outbound requests:

| Destination | Purpose | Code |
|---|---|---|
| `127.0.0.1:1234` (LM Studio) | Local model inference for job analysis, extraction and cover letters | `job_analysis_reasoner.py`, `job_extractor.py`, `cover_letter_generator.py` |
| Gmail API (`googleapis.com`) | Read job-alert emails | `gmail_client.py`, `daily_job_batch.py` |
| JobStreet tracking links | Resolve alert links to job pages (HTTP GET) | `job_link_resolver.py` |
| JobStreet job pages | Read the visible job description in a Chromium window (Playwright) | `job_page_retriever.py` |
| Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`) | Loaded by your browser for the dashboard's typeface | `04_Application/static/index.html` |

Job text and career evidence are sent only to the local LM Studio server. No
cloud LLM API is called.

The browser automation opens a page and reads its text. It does not sign in,
click Apply, save jobs or submit forms.

## Local dashboard

- The dashboard server binds to `127.0.0.1` only (`dashboard_server.create_server`).
- There is no authentication: anyone with access to your machine's loopback
  interface can use it while it runs.
- Reading a cover letter checks that the stored file name starts with the
  requested job ID before opening it.

## Human-in-the-loop controls

- Model output is a recommendation only. Job state changes (Skip, Pursue,
  Mark Applied) happen only when you act in the dashboard.
- `REVIEW_PENDING → APPLIED` is rejected; a job must be pursued first.
- Applications are always submitted by you, outside this tool.
- Before writing the tracker, the Excel writer makes a backup copy and restores
  it if the database update fails afterwards.

## Reporting a problem

If you find a security or privacy issue, please open a GitHub issue without
including any personal data, credentials or real email content.
