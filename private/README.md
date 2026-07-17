# Private Local Files

Use this directory for personal files that should not be committed to git.

## Application inputs

The application loads these filenames:

- `list_of_companies.md` (required) for target companies, websites, connection flags, optional connection names, and industries of interest.
- `preferences.md` (required) for liked and disliked role characteristics, including location preferences.
- `mcgill_class_list.md` (required) for program and coursework information.
- `connections.md` (optional) for connection notes.
- `Resume - Gabrielle Dar.pdf` (optional) for local resume-presence detection.
- `resume_summary.md` (optional and recommended) for resume-aware Gemini scoring. The scorer also accepts `resume.md` or `resume.txt`.
- `attachments/` (optional) subdirectory containing additional supporting documents (e.g., transcripts, cover letters, portfolios) that are parsed and sent as multimodal inputs during AI scoring.

The PDF is not parsed or sent to an AI provider by default. Resume/attachment text and media are included in Gemini prompts only when scoring is run; text, PDF, and image attachments are base64-encoded and sent as inline data parts for multimodal analysis.

## Required formats

- `list_of_companies.md` uses a 3 or 4-column Markdown table: company name, official career or jobs-page URL, `yes`/`no` connection status, and optional connection contact names. List items outside the table are treated as industries.
- `preferences.md` uses `## Things I like` and `## Things I don't like` sections with list items.
- `mcgill_class_list.md` uses a `## Program` section and course sections whose list items follow `COURSE CODE: Course title`.

Everything in this directory is ignored by git except this README, `.gitkeep`, and subfolder READMEs.
