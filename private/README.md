# Private Local Files

Use this directory for personal files that should not be committed to git.

## Application inputs

The application loads these filenames:

- `list_of_companies.md` (required) for target companies, websites, connection flags, and industries of interest.
- `preferences.md` (required) for liked and disliked role characteristics, including location preferences.
- `mcgill_class_list.md` (required) for program and coursework information.
- `connections.md` (optional) for connection notes.
- `Resume - Gabrielle Dar.pdf` (optional) for local resume-presence detection.
- `resume_summary.md` (optional and recommended) for resume-aware Gemini scoring. The scorer also accepts `resume.md` or `resume.txt`.

The PDF is not parsed or sent to an AI provider. Resume text is included in a
Gemini prompt only when explicitly enabled with `--resume-aware` or
`AI_RESUME_SCORING_ENABLED=true`; the first non-empty supported summary file is
limited to 4,000 characters.

## Required formats

- `list_of_companies.md` uses a three-column Markdown table: company name, official career or jobs-page URL, and `yes`/`no` connection status. List items outside the table are treated as industries.
- `preferences.md` uses `## Things I like` and `## Things I don't like` sections with list items.
- `mcgill_class_list.md` uses a `## Program` section and course sections whose list items follow `COURSE CODE: Course title`.

Everything in this directory is ignored by git except this README and `.gitkeep`.
