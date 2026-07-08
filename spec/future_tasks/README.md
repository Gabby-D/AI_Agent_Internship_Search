# Future Tasks

Use this folder for planned work that is not ready to implement yet.

## Future Roadmap

These tasks extend the first local collector into a more capable AI-assisted internship search system.

The current company list should be treated as seed input only. A later discovery step should expand the search to similar companies and companies in related industries.

## Task Index

1. `001-ai-fit-scoring.md` - Score postings against profile, preferences, resume, coursework, and connections.
2. `002-new-posting-detection.md` - Track which postings are new, changed, repeated, or no longer available.
3. `003-weekly-email-summary.md` - Send a weekly summary of relevant new roles.
4. `004-scheduled-collection.md` - Run collection automatically on a schedule.
5. `005-company-discovery.md` - Find similar companies and career sources to expand the search.
6. `006-local-review-ui.md` - Build a simple local interface for reviewing postings and updating preferences.
7. `007-internet-search-provider.md` - Add a modular internet search layer for finding websites, careers pages, and similar companies from Python.

## Notes

Future tasks should move into `spec/current_tasks/` when the previous collector and filtering milestones are working.

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
