# Private Local Files

Use this directory for personal files that should not be committed to git.

## Application inputs

The application loads these filenames:

- `list_of_companies.md` (required) for target companies, websites, connection flags, optional connection names, and industries of interest.
- `preferences.md` (required) for liked and disliked role characteristics, including location preferences.
- `location_preferences.txt` (optional) for private location aliases, one per line. Fully remote roles remain eligible without this file.
- `course_list.md` (required) for program and coursework information.
- `connections.md` (optional) for connection notes.
- `resume.pdf` (optional) for presence-only detection by the private-input loader.
- `resume_summary.md` (optional and recommended) for resume-aware Gemini scoring. The scorer also accepts `resume.md` or `resume.txt`.
- `attachments/` (optional) for supporting documents managed by the Review UI. Uploads accept PDF, Word (`.doc`, `.docx`), text (`.txt`, `.md`), and image files (`.png`, `.jpg`, `.jpeg`, `.gif`) up to 5 MB each.

The standalone legacy resume PDF is only checked for existence and is not parsed or sent. Resume-summary text is sent to Gemini only when resume-aware scoring is enabled. In contrast, supported files under `attachments/` are sent whenever Gemini scoring runs, regardless of the resume-aware setting: text files become prompt text, while PDFs and images are sent as inline data. Word uploads remain local and are not currently included in scoring. Use `AI_PROVIDER=local` if attachments must remain on the machine during scoring.

## Required formats

- `list_of_companies.md` uses a 3 or 4-column Markdown table: company name, official career or jobs-page URL, `yes`/`no` connection status, and optional connection contact names. List items outside the table are treated as industries.
- `preferences.md` uses `## Things I like` and `## Things I don't like` sections with list items.
- `course_list.md` uses a `## Program` section and course sections whose list items follow `COURSE CODE: Course title`.

Everything in this directory is ignored by git except this README and `.gitkeep`. Confirm with `git check-ignore private/<filename>` before staging changes.

The packaged Windows app does not embed this directory. `app/Internship Search.exe` reads these files locally at runtime.

Standard wheel and source-distribution builds also exclude this directory through the package layout and `MANIFEST.in`.
