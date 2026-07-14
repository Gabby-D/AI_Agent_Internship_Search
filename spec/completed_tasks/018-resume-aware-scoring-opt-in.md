# Completed Task: Resume-Aware Scoring Opt-In

## Completed Outcome

Added optional resume-aware Gemini scoring behind an explicit opt-in flag, while keeping the default non-resume scoring path unchanged.

## Implemented Files

- `src/internship_search/resume_scoring.py`
- `src/internship_search/ai_scoring.py`
- `src/internship_search/fit_scoring.py`
- `src/internship_search/cli.py`
- `src/internship_search/scheduled_collection.py`
- `.env.example`
- `tests/test_resume_scoring.py`
- `tests/test_scheduled_collection.py`

## Behavior

- Default scoring still sends only program, courses, industries, preferences, and connection status.
- Resume text is sent only when one of these is true:
  - `AI_RESUME_SCORING_ENABLED=true` in `.env`
  - `--resume-aware` on `score-postings` or `run-scheduled-collection`
- Resume content is loaded from the first available private text file:
  - `private/resume_summary.md` (preferred)
  - `private/resume.md`
  - `private/resume.txt`
- Resume summaries are truncated to 4000 characters before sending.
- PDF resumes are not parsed automatically.
- Gemini prompts ask for explanations that reference resume-relevant skills when resume context is included.
- Scored output shape is unchanged.

## Privacy Notes

- Resume text leaves your machine only when resume-aware mode is enabled and a text summary file exists.
- Keep `private/resume_summary.md` short and review it before enabling opt-in.
- `.env.example` documents the opt-in setting.

## Environment Variables

- `AI_RESUME_SCORING_ENABLED` - `false` by default.

## CLI

Enable resume-aware scoring for one run:

```powershell
uv run internship-search score-postings --resume-aware
```

Enable it in the scheduled workflow:

```powershell
uv run internship-search run-scheduled-collection --resume-aware
```

## Verification

```powershell
uv run pytest
```

Result: `116 passed`.

## Next Step

Continue with `019-job-board-search.md` or `021-scheduler-and-run-hardening.md`.
