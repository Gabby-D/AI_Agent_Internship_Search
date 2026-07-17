# Future Tasks

Use this folder for planned work that is not ready to implement yet.

## Future Roadmap

The core implementation, operational validation, release-readiness work, and currently planned review-workflow improvements are complete. No future implementation task is currently scheduled.

The current company list remains seed input. Discovery, internet search, and job-board providers can continue expanding the registry over time.

## Task Index

### High Priority

1. None currently listed.

### Medium Priority

1. None currently listed.

### Lower Priority

1. None currently listed.

## Suggested Order

1. None.

## Notes

Future tasks should move into `spec/current_tasks/` when they are ready to implement.

## Definition of Done for Every Future Task

Before a future task is considered complete:

1. Review and update every affected README so the documentation remains accurate, clear, and helpful. Check the root README plus the READMEs under `data/`, `private/`, and `spec/` when their documented behavior or task status changes.
2. Protect personal information before staging or pushing. Keep credentials, profile details, resumes, personal notes, generated reports, and other private data out of git; confirm ignore rules with `git check-ignore` and review the staged diff for sensitive values.
3. Verify that weekly email delivery still works and remains scheduled. Run the email tests and `config/verify_automation.ps1`, then confirm the `AI Agent Internship Weekly Email` task is registered, enabled, and has a future run time. Do not send a live test email unless the task specifically calls for one.
4. Run the relevant tests, commit the completed work, and push the branch to the configured git remote.

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
