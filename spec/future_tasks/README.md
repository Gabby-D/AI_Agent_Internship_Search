# Future Tasks

Use this folder for planned work that is not ready to implement yet.

## Future Roadmap

The core implementation and local integration-readiness tasks are complete. The remaining work focuses on live operational validation and release readiness:

1. Run the full workflow against live sources and evaluate its results.
2. Register and validate the recurring collection and weekly email tasks.
3. Complete final testing and version-control review.

The current company list remains seed input. Discovery, internet search, and job-board providers can continue expanding the registry over time.

## Task Index

### High Priority

1. `035-review-ui-redesign.md` - Redesign the local review dashboard with tabbed navigation and a modern, minimal visual style.

### Medium Priority

1. None currently listed.

### Lower Priority

1. None currently listed.

## Suggested Order

1. `035-review-ui-redesign.md`

## Notes

Future tasks should move into `spec/current_tasks/` when they are ready to implement.

## Code Style Instructions

- Keep future implementation plans minimal and practical.
- Prefer clear data models, explicit inputs and outputs, and testable modules.
- Design tools as modular pieces that can be used separately, tested separately, and composed into larger workflows.
- Keep AI, browser automation, email, scheduling, storage, UI, and deterministic filtering loosely coupled.
- Avoid building a complex agent framework until the simple collector, filter, and report flow works reliably.
- Keep AI usage focused on judgment-heavy work, such as fit scoring, summarization, and company discovery.
- Keep deterministic code responsible for loading files, collecting postings, deduplicating results, and writing outputs.
- Protect private data by default. Do not commit real profile files, resume contents, credentials, or generated personal reports.
- Use `uv` for Python version management, dependency management, and command execution.

## Mode Guidance

- Start future tasks in Plan mode when they involve AI behavior, email automation, scheduled jobs, browser automation, external APIs, or UI decisions.
- Move to Agent mode after the implementation approach, data flow, and acceptance criteria are clear.
- Use Agent mode directly only for small documentation updates, focused tests, or implementation steps that are already specified by a current task.
