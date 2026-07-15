# Current Tasks

Use this folder for tasks that are actively being designed or implemented.

## Current Milestone

Validate the completed local workflow with live sources, then confirm that recurring collection and weekly email delivery are production-ready.

## Task Order

No active current tasks. The first local collection, filtering, and review milestone is complete.

## Current Focus

Start with `spec/future_tasks/032-live-workflow-validation.md` and move it into this folder when work begins. Scheduler production validation and release readiness follow as tasks 033 and 034.

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
