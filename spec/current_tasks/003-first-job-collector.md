# Task: Implement First Job Collector

## Goal

Collect current internship postings from the company source registry.

## Scope

Start with the seed companies from the initial source registry. Do not treat that list as the final search universe. Later tasks should expand the registry with similar companies.

Use a simple collector that can fetch postings from company job pages or known job-board-backed pages. Do not build a full browser automation system yet unless a company site requires it.

## Requirements

- Fetch job postings from the company sources.
- Extract at least title, company, location, posting URL, and date collected.
- Keep raw or lightly processed results in `data/`.
- Avoid storing credentials or private inputs in generated outputs.
- Make collector runs repeatable from the CLI.

## Suggested CLI

```powershell
uv run internship-search collect
```

## Output

- A local results file, such as `data/postings.jsonl` or `data/postings.csv`.

## Acceptance Criteria

- The collector can run against at least one company source.
- The results file includes structured posting records.
- A second run does not create obvious duplicate records for the same posting URL.
- Tests cover the parsing or normalization logic where practical.
