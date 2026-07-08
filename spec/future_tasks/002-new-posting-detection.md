# Future Task: New Posting Detection

## Goal

Detect which internship postings are new since the last collection run.

## Requirements

- Store stable posting identifiers, preferably canonical posting URLs.
- Track first seen date and last seen date.
- Mark postings as new, seen before, changed, or no longer available.
- Avoid duplicate rows when a company reposts the same role through the same URL.

## Output

- Updated posting history in `data/`.
- A list of newly discovered postings for reporting and email summaries.
