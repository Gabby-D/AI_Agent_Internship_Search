# AI Agent Internship Search

A Python-based tool to help users find internships that match their private preferences and profile.

## Goal

Build a simple, useful local internship search workflow that can:

- Track companies and internship opportunities you care about
- Collect postings from company career pages and job boards
- Filter, score, and review promising roles
- Send a weekly email summary of new opportunities

## Quick Start

### 1. Install the standard Python package

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

The project uses standard `pyproject.toml` and setuptools packaging. `uv sync` remains supported as an optional faster installer. See `INSTALL.md` for standard `pip`, `uv`, testing, package-building, and Windows-app instructions.

### 2. Add private inputs

Create local files under `private/` (not committed to git):

- `list_of_companies.md` — required seed companies to monitor
- `preferences.md` — required likes, dislikes, and location preferences
- `course_list.md` — required coursework and program info
- `connections.md` — optional connection notes
- `location_preferences.txt` — optional private location aliases, one per line
- `resume.pdf` — optional presence-only resume reference; this standalone PDF is not parsed
- `resume_summary.md` — optional resume text used only for explicitly enabled resume-aware Gemini scoring; `resume.md` and `resume.txt` are also accepted
- `attachments/` — optional supporting files managed from the Review UI; see the privacy note below before using Gemini scoring

See `private/README.md` for supported formats, attachment limits, and resume-handling behavior.

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
| `AI_PROVIDER_MODEL` | Gemini model name (default: `gemini-2.5-flash`) |
| `AI_RESUME_SCORING_ENABLED` | Set `true` to include the first supported private resume-summary file in Gemini prompts; files under `private/attachments/` are handled separately |
| `EMAIL_FROM`, `EMAIL_TO`, `EMAIL_SMTP_PASSWORD` | SMTP settings for weekly email delivery |
| `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT` | SMTP server settings (defaults: `smtp.gmail.com` and `587`) |
| `EMAIL_SMTP_USER` | SMTP username (defaults to `EMAIL_FROM`) |
| `EMAIL_SMTP_USE_TLS` | Set `false` to disable TLS (enabled by default) |
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

### One-click Windows app

Build the local windowed app once:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[app]"
powershell -ExecutionPolicy Bypass -File config/build_windows_app.ps1 -Clean
```

Then double-click `app/Internship Search.exe`. It starts the local dashboard and opens the browser without showing a terminal. The executable contains program code only; it continues reading personal inputs and generated results from the ignored `private/` and `data/` folders beside the project. Keep the executable in the project's `app/` folder so it can locate those folders.

If the dashboard is already running and healthy, opening the app simply reopens it in the browser. Startup errors are written locally to `data/app_launcher.log`.

## Core Workflow

The main repeatable pipeline:

1. Build source registry from seed companies
2. Collect posting candidates
3. Detect new, seen, changed, and missing postings
4. Filter for likely target-cycle internship relevance and the private location policy
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

## Location Policy

The pipeline keeps roles that match the user's preference of location or are clearly fully remote or online. Specific location preferences are stored only in the ignored `private/location_preferences.txt` file. Other and unknown locations are excluded during filtering and omitted from scoring, weekly email, and the review dashboard.

An empty dashboard can therefore mean that no current roles match the location policy.

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
uv run internship-search discover-companies --update-registry
uv run internship-search score-postings --resume-aware
uv run internship-search weekly-email-summary --send
uv run internship-search run-scheduled-collection --include-job-boards --send-email
uv run internship-search run-scheduled-collection --include-job-boards --skip-email
uv run internship-search review-ui --no-open-browser --port 8766
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

Job-board search uses public search-provider `site:` queries for Greenhouse, Lever, Workday, LinkedIn, and Indeed listing URLs. In the default `auto` configuration, it tries DuckDuckGo first and can fall back to Google Custom Search when configured.

```powershell
uv run internship-search search-job-boards
uv run internship-search collect --include-job-boards
```

### LinkedIn and Indeed

LinkedIn and Indeed are searched through public listing URLs surfaced by search-provider `site:` queries, not through logged-in site scraping or official APIs.

Supported limits:

- Only publicly indexed listing URLs are returned; logged-in-only postings are out of scope.
- Job-board search runs multiple LinkedIn and Indeed query variants each collection run.
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

The dashboard has five tabs:

- **Postings** groups roles as To review, Applied, Not interested, or Archived. Each row shows the job, company, location, connection indicator, career-posting link, review-status control, and an expandable summary with highlights and personal notes.
- **Companies** edits the monitored-company list, official career URLs, connection flags, and industries. Saving updates `private/list_of_companies.md` and rebuilds the local source registry.
- **Preferences** edits likes and dislikes in `private/preferences.md`.
- **Reference Files** edits the course list, connection notes, and resume summary, and manages local supporting attachments. Uploads accept PDF, Word, text, and image files up to 5 MB each; only text, PDF, and image attachments are currently included in Gemini scoring requests.
- **Activity Log** displays dated local changes in reverse chronological order with filter controls and cost transparency badges.

The dashboard displays the active location policy and refreshes its data every 30 seconds when a text field is not focused. New companies are included in future posting searches after the next scheduled collection, or immediately after running `uv run internship-search run-scheduled-collection --include-job-boards`.

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

The summary uses `data/email_sent_history.json` to avoid repeating internships already sent successfully. Recipient selection is: explicit `--recipient`, then `EMAIL_TO` from the ignored `.env` file. Sending fails safely when no recipient is configured.

## Scheduled Automation

Register weekly company discovery, daily collection, and Monday weekly-email tasks:

```powershell
powershell -ExecutionPolicy Bypass -File config/register_scheduled_tasks.ps1
```

This registers:

- **Recommended-company discovery** on Monday at 8:30 AM
- **Daily collection** at 9:00 AM with `--include-job-boards`
- **Weekly email send** on Monday at 10:00 AM

If the computer is off at the scheduled time, each task runs the next time the computer becomes available.

Wrapper scripts:

```powershell
powershell -ExecutionPolicy Bypass -File config/run_scheduled_collection.ps1
powershell -ExecutionPolicy Bypass -File config/run_company_discovery.ps1
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
3. **Scheduled tasks** — Task Scheduler shows all three tasks as **Ready** with recent last-run times after the computer is on.
4. **Collection logs** — `data/scheduled_collection_runs.jsonl` gains a new line after each collection run. `status: partial` is normal when some company pages fail but scoring and the email draft still complete.
5. **Wrapper logs** — `data/scheduled_run_output/` contains timestamped `.log` files from the PowerShell wrappers.
6. **Job board search (optional)** — `uv run internship-search search-job-boards` reports `Provider: duckduckgo_job_board` and writes `data/job_board_postings.jsonl`.
7. **Company discovery** — Monday's discovery log writes `company_discovery_*.log`, while refreshed suggestions appear in `data/discovered_companies.json` and the Companies tab.

### Troubleshooting failed runs

| Symptom | What to check |
|---------|----------------|
| Weekly email not received | Run `weekly-email-summary --send` manually and read the `Send status:` line. Gmail app passwords need `EMAIL_SMTP_HOST=smtp.gmail.com` and port `587` (defaults apply when unset). |
| Task Scheduler shows non-zero last result | Open the newest file in `data/scheduled_run_output/`. Collection runs with source warnings may still finish with `Status: partial` and exit code `0` when scoring and email steps succeed. |
| `email_sent_history.json` unchanged after send | Send did not succeed. Fix SMTP credentials and retry; history updates only after delivery succeeds. |
| No new postings in email | All current postings may already appear in `email_sent_history.json`. Run a fresh `run-scheduled-collection` first. |
| Job board search returns 0 postings | DuckDuckGo coverage depends on public search indexes. Try a custom `search-job-boards --query` using the user's desired internship cycle. Non-internship roles are filtered out. |
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
- `collection_errors.jsonl` — collection failures from the latest run
- `job_board_postings.jsonl` — public job-board search results
- `filtered_postings.jsonl` / `excluded_postings.jsonl` — filter results
- `monitored_no_openings.jsonl` — seed companies without a specific matching opening
- `scored_postings.jsonl` — fit scores and explanations
- `latest_report.md` — readable review report
- `weekly_email_summary.md` — email draft
- `posting_history.json` — tracked posting status across runs
- `posting_reviews.json` — review UI status changes
- `posting_notes.json` — private notes saved from the review UI
- `company_dismissals.json` — dismissed company suggestions
- `activity_log.jsonl` — local dashboard and workflow activity

See `data/README.md` for the full list.

## Development

Install development tools and run tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

Equivalent `uv` commands are `uv sync --extra dev` and `uv run pytest`.

Print CLI version:

```powershell
uv run internship-search --version
```

## Current Status

Implemented and working locally:

- Private input loading, source registry, collection, filtering, and reporting
- Gemini fit scoring with local fallback and optional resume-aware scoring
- Posting history with duplicate and closed-role detection
- Deterministic filtering based on the user's private preference of location, plus remote/online roles
- Job-board search with DuckDuckGo queries for Greenhouse, Lever, Workday, LinkedIn, and Indeed
- Weekly email draft and SMTP delivery
- Windows Task Scheduler automation with missed-run catch-up
- Local review UI with status-based lists, supporting file attachments, company recommendation dismissals, activity-log filtering, and cost transparency

All currently planned milestones are complete. The full automated suite passed locally on July 17, 2026 (214 tests).

## Privacy

Do not commit:

- `.env`
- Real files in `private/`
- Generated files in `data/`

Set `EMAIL_TO` in `.env` before sending. No personal recipient is stored in tracked code.

The project keeps `private/` and generated `data/` files out of git by default. Gemini scoring is an explicit external-data boundary: when Gemini is selected, supported files in `private/attachments/` are sent with each scoring request even if resume-aware summary scoring is disabled. Text (`.txt`, `.md`), PDF, and image (`.png`, `.jpg`, `.jpeg`, `.gif`) attachments are sent; uploaded Word files are stored locally but are not currently included in scoring. Review attachment contents before running Gemini scoring, or use `AI_PROVIDER=local` to keep scoring local.
