# Task: Create Local Results Review

## Goal

Create a simple local report that makes collected and filtered postings easy to review before email automation exists.

## Requirements

- Generate a Markdown summary in `data/`.
- Group roles by company.
- Show title, location, posting URL, collected date, and relevance reason.
- Highlight companies where the user has a known connection.
- Include a short section for questions or missing information.

## Suggested CLI

```powershell
uv run internship-search report
```

## Output

- A local report file, such as `data/latest_report.md`.

## Acceptance Criteria

- The report can be generated from the filtered results file.
- The report is readable without opening raw JSON or CSV.
- The report does not include secrets or private resume text.
