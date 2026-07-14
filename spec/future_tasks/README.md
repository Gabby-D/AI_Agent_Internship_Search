# Future Tasks

Use this folder for planned work that is not ready to implement yet.

## Future Roadmap

The first 24 implementation tasks are complete. The remaining work focuses on expanding sources and improving posting quality:

1. Expand and fix company sources so seed employers actually return internships.
2. Improve posting metadata and job-board coverage.
3. Polish remaining operational behavior where needed.

The current company list should still be treated as seed input. Discovery, internet search, and job-board providers should continue expanding the registry over time.

## Task Index

### High Priority

1. `025-bakar-alumni-company-expansion.md` - Add Bakar alumni companies to the seed company list.

### Medium Priority

1. None currently listed.

### Lower Priority

1. None currently listed.

## Suggested Order

1. `025-bakar-alumni-company-expansion.md`

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
