# Current Tasks

Use this folder for tasks that are actively being designed or implemented.

## Current Milestone

Recover blocked or unsupported company career sources, starting with RTX.

## Task Order

1. [`046-general-career-source-recovery.md`](046-general-career-source-recovery.md)

Completed work is recorded under `spec/completed_tasks/`.

## Current Focus

Use RTX's public recruiting-platform interface without depending on its
Cloudflare-blocked search-result HTML. Preserve complete pagination and visible
diagnostics, then apply the same evidence-led process to the next affected
company.

## Code Style Instructions

- Keep the implementation simple, readable, and Pythonic.
- Prefer small modules and functions with clear responsibilities.
- Design project tools as modular components that can run independently and be combined later.
- Keep collectors, parsers, filters, scoring, reporting, storage, and external integrations separated behind clear inputs and outputs.
- Avoid over-engineering, broad abstractions, or premature frameworks.
- Use structured parsing for Markdown, TOML, JSON, or CSV when practical instead of fragile string manipulation.
- Keep private data out of git and avoid writing resume text, credentials, or personal notes into tracked files.
- Store generated outputs under `data/`, which is ignored by git.
- Add focused tests for parsing, filtering, deduplication, and reporting behavior.
- Use `uv` for dependency management, running commands, and tests.

## Mode Guidance

- Use Agent mode for narrow implementation tasks with clear requirements, such as parsing private inputs, adding CLI commands, writing tests, or generating local reports.
- Use Plan mode before tasks with design tradeoffs, external integrations, scheduling decisions, browser automation, AI provider choices, email delivery, or UI architecture.
- If a current task becomes unclear or expands beyond its acceptance criteria, pause and switch to Plan mode before continuing implementation.
