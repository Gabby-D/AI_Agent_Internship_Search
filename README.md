# AI Agent Internship Search

A Python-based tool to help find open Summer 2027 internships that match your interests, availability, resume, skills, coursework, projects, and experience.

## Goal

Build a simple, useful local internship search workflow that can:

- Track companies and internship opportunities you care about
- Collect postings from company career pages and job boards
- Filter, score, and review promising roles
- Send a weekly email summary of new opportunities

## Quick Start

### 1. Install dependencies

```powershell
uv sync
```

### 2. Add private inputs

Create local files under `private/` (not committed to git):

- `list_of_companies.md` — seed companies to monitor
- `preferences.md` — likes and dislikes
- `mcgill_class_list.md` — coursework and program info
- `connections.md` — optional connection notes

See `private/README.md` for the suggested file layout.

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in local credentials:

```powershell
copy .env.example .env
```

Common variables:

| Variable | Purpose |
|----------|---------|
| `AI_PROVIDER_API_KEY` | Gemini API key for fit scoring |
| `AI_PROVIDER` | `auto`, `gemini`, or `local` |
| `AI_RESUME_SCORING_ENABLED` | Set `true` to include `private/resume_summary.md` in AI prompts |
| `EMAIL_FROM`, `EMAIL_TO`, `EMAIL_SMTP_PASSWORD` | SMTP settings for weekly email delivery |
| `TAVILY_API_KEY` | Optional Tavily-only internet search (`INTERNET_SEARCH_PROVIDER=tavily`) |
| `GOOGLE_CUSTOM_SEARCH_API_KEY`, `GOOGLE_CSE_ID` | Optional Google Custom Search fallback when DuckDuckGo fails or returns no results |
| `INTERNET_SEARCH_PROVIDER` | `auto`, `duckduckgo_html`, `google_custom_search`, or `tavily` |

### 4. Run the full workflow

```powershell
uv run internship-search run-scheduled-collection --include-job-boards
```

This rebuilds the source registry, collects postings, updates history, filters, reports, scores, and generates the weekly email draft.

### 5. Review results

```powershell
uv run internship-search review-ui
```

Then open **http://127.0.0.1:8765**. The command auto-opens your browser. **Keep that terminal open** — closing it stops the site.

## Core Workflow

The main repeatable pipeline:

1. Build source registry from seed companies
2. Collect posting candidates
3. Detect new, seen, changed, and missing postings
4. Filter for likely Summer 2027 internship relevance
5. Generate a Markdown review report
6. Score filtered postings with Gemini or local rules
7. Generate a weekly email summary draft

Run it manually:

```powershell
uv run internship-search build-source-registry
uv run internship-search collect --include-job-boards
uv run internship-search detect-new-postings
uv run internship-search filter-postings
uv run internship-search report
uv run internship-search score-postings
uv run internship-search weekly-email-summary
```

Or run everything at once:

```powershell
uv run internship-search run-scheduled-collection --include-job-boards
```

## CLI Commands

| Command | Purpose |
|---------|---------|
| `show-inputs` | Print a safe summary of parsed private inputs |
| `build-source-registry` | Build `data/source_registry.json` from seed companies |
| `discover-companies` | Suggest similar companies for review |
| `internet-search` | Search for company careers pages |
| `search-job-boards` | Search external job boards for internships |
| `collect` | Collect posting candidates into `data/postings.jsonl` |
| `detect-new-postings` | Update posting history and change logs |
| `filter-postings` | Write included and excluded posting files |
| `report` | Generate `data/latest_report.md` |
| `score-postings` | Score filtered postings |
| `weekly-email-summary` | Generate local weekly email draft |
| `run-scheduled-collection` | Run the full workflow and append a run log |
| `review-ui` | Start the local review dashboard |

Useful flags:

```powershell
uv run internship-search collect --include-job-boards
uv run internship-search collect --enrich-from-search data/internet_search_results.jsonl
uv run internship-search score-postings --resume-aware
uv run internship-search weekly-email-summary --send
uv run internship-search run-scheduled-collection --include-job-boards --send-email
```

## Internet Search

`internet-search` and job-board search use DuckDuckGo by default. When `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_CSE_ID` are set, `auto` mode tries DuckDuckGo first and falls back to [Google Custom Search](https://developers.google.com/custom-search/v1/overview) if DuckDuckGo fails or returns no results.

Google setup:

1. Enable the Custom Search API in Google Cloud and create an API key.
2. Create a Programmable Search Engine at [programmablesearchengine.google.com](https://programmablesearchengine.google.com/) with **Search the entire web** enabled.
3. Add both values to `.env`.

```powershell
uv run internship-search internet-search --company BlackRock
```

This project does not scrape google.com directly. Google is accessed only through the official Custom Search API.

## Job Board Search

External job boards are searched during collection when `--include-job-boards` is used.

Job-board search uses **DuckDuckGo `site:` queries** against public listing URLs on Greenhouse, Lever, Workday, LinkedIn, and Indeed. No extra API credentials are required.

```powershell
uv run internship-search search-job-boards
uv run internship-search collect --include-job-boards
```

### LinkedIn and Indeed

LinkedIn and Indeed are searched through public listing URLs surfaced by DuckDuckGo `site:` queries, not through logged-in site scraping or official APIs.

Supported limits:

- Only publicly indexed listing URLs are returned; logged-in-only postings are out of scope.
- DuckDuckGo runs multiple LinkedIn and Indeed query variants each collection run.
- When the same role appears on a company career page and on LinkedIn/Indeed, collection keeps the career-page URL.
- Run summaries and collection logs record provider limitations when LinkedIn or Indeed coverage is partial.

## Review UI

The review dashboard is a **local website** that only works while the server command is running.

Start it:

```powershell
uv run internship-search review-ui
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File config/run_review_ui.ps1
```

Then open **http://127.0.0.1:8765**. The command should auto-open your browser. **Keep the terminal open**; closing it stops the site.

If the page does not load:

1. Confirm the terminal still shows `Review UI running at http://127.0.0.1:8765`.
2. Try another port: `uv run internship-search review-ui --port 8766`.
3. Make sure `review-ui` is running — collection commands alone do not start the website.

The UI shows separate lists:

- To review
- Interested
- Applied
- Needs follow-up
- Ignored

Each row shows job title, company, location, link, and review status. Status changes are saved to `data/posting_reviews.json`.

Restart the UI after code changes:

1. Press `Ctrl+C` in the terminal
2. Run `uv run internship-search review-ui` again
3. Refresh the browser

## Weekly Email

Generate a local draft:

```powershell
uv run internship-search weekly-email-summary
```

Send by SMTP when email credentials are configured:

```powershell
uv run internship-search weekly-email-summary --send
```

The summary uses `data/email_sent_history.json` to avoid repeating internships already sent successfully.

## Scheduled Automation

Register daily collection and Monday weekly-email tasks:

```powershell
powershell -ExecutionPolicy Bypass -File config/register_scheduled_tasks.ps1
```

This registers:

- **Daily collection** at 9:00 AM with `--include-job-boards`
- **Weekly email send** on Monday at 10:00 AM

If the computer is off at the scheduled time, each task runs the next time the computer becomes available.

Wrapper scripts:

```powershell
powershell -ExecutionPolicy Bypass -File config/run_scheduled_collection.ps1
powershell -ExecutionPolicy Bypass -File config/run_weekly_email.ps1
```

Check automation output:

- Console logs: `data/scheduled_run_output/`
- Structured run logs: `data/scheduled_collection_runs.jsonl`

Quick verification script:

```powershell
powershell -ExecutionPolicy Bypass -File config/verify_automation.ps1
```

### Operational checklist

After setup, confirm automation is working:

1. **Email credentials** — `.env` has `EMAIL_FROM`, `EMAIL_TO`, and `EMAIL_SMTP_PASSWORD` set.
2. **Live email test** — `uv run internship-search weekly-email-summary --send` reports `Email sent to ...` and updates `data/email_sent_history.json` only after a successful send.
3. **Scheduled tasks** — Task Scheduler shows both tasks as **Ready** with recent last-run times after the computer is on.
4. **Collection logs** — `data/scheduled_collection_runs.jsonl` gains a new line after each collection run. `status: partial` is normal when some company pages fail but scoring and the email draft still complete.
5. **Wrapper logs** — `data/scheduled_run_output/` contains timestamped `.log` files from the PowerShell wrappers.
6. **Job board search (optional)** — `uv run internship-search search-job-boards` reports `Provider: duckduckgo_job_board` and writes `data/job_board_postings.jsonl`.

### Troubleshooting failed runs

| Symptom | What to check |
|---------|----------------|
| Weekly email not received | Run `weekly-email-summary --send` manually and read the `Send status:` line. Gmail app passwords need `EMAIL_SMTP_HOST=smtp.gmail.com` and port `587` (defaults apply when unset). |
| Task Scheduler shows non-zero last result | Open the newest file in `data/scheduled_run_output/`. Collection runs with source warnings may still finish with `Status: partial` and exit code `0` when scoring and email steps succeed. |
| `email_sent_history.json` unchanged after send | Send did not succeed. Fix SMTP credentials and retry; history updates only after delivery succeeds. |
| No new postings in email | All current postings may already appear in `email_sent_history.json`. Run a fresh `run-scheduled-collection` first. |
| Job board search returns 0 postings | DuckDuckGo coverage depends on public search indexes. Try `search-job-boards --query "summer 2027 internship"`. Non-internship roles are filtered out. |
| Review UI link does not load | Run `uv run internship-search review-ui` in a separate terminal and keep it open. The site is not running during collection commands. |
| Collection task never runs | Re-register tasks: `config/register_scheduled_tasks.ps1`. Tasks use `StartWhenAvailable` to catch up after the computer was off. |

Wrapper exit codes:

- `0` — required steps completed (including useful `partial` runs with source warnings)
- non-zero — a required step such as scoring or email failed; inspect the matching wrapper log and `scheduled_collection_runs.jsonl`

## Project Structure

| Path | Purpose |
|------|---------|
| `private/` | Local-only personal inputs (ignored by git) |
| `data/` | Generated outputs such as postings, scores, and reports |
| `config/` | Example scripts for scheduling and local automation |
| `src/internship_search/` | Main Python package |
| `tests/` | Automated tests |
| `spec/` | Task planning and completed work notes |

Key docs:

- `CODEMAP.md` — codebase layout and where to add new functionality
- `spec/completed_tasks/` — finished task history
- `spec/future_tasks/` — planned improvements

## Generated Data Files

Common outputs in `data/`:

- `postings.jsonl` — collected posting candidates
- `filtered_postings.jsonl` / `excluded_postings.jsonl` — filter results
- `scored_postings.jsonl` — fit scores and explanations
- `latest_report.md` — readable review report
- `weekly_email_summary.md` — email draft
- `posting_history.json` — tracked posting status across runs
- `posting_reviews.json` — review UI status changes

See `data/README.md` for the full list.

## Development

Run tests:

```powershell
uv run pytest
```

Print CLI version:

```powershell
uv run internship-search --version
```

## Current Status

Implemented and working locally:

- Private input loading, source registry, collection, filtering, and reporting
- Gemini fit scoring with local fallback and optional resume-aware scoring
- Posting history with duplicate and closed-role detection
- Job-board search with DuckDuckGo queries for Greenhouse, Lever, Workday, LinkedIn, and Indeed
- Weekly email draft and SMTP delivery
- Windows Task Scheduler automation with missed-run catch-up
- Local review UI with status-based lists

Remaining improvements are tracked in `spec/future_tasks/`.

## Privacy

Do not commit:

- `.env`
- Real files in `private/`
- Generated files in `data/`

The project is designed to keep personal data local by default.
