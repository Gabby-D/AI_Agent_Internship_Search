# Reference File Attachments

## Goal

Allow the Reference Files tab to retain user-written text and locally uploaded supporting files.

## Requirements

- Keep the existing editable text areas for course information, connection notes, and resume summary.
- Add an upload control that accepts user-selected local files and clearly lists retained attachments.
- Support adding, viewing file metadata, downloading, replacing, and deleting attachments from the local UI.
- Preserve filenames safely, prevent path traversal, set sensible size limits, and reject unsupported or unsafe file types.
- Store attachments only in a Git-ignored private directory with no upload to external services.
- Do not automatically parse, transmit, score from, or include attachment contents in AI prompts. Any future processing must require explicit opt-in.

## Acceptance checks

- Text edits and uploaded files persist across UI restarts.
- Uploaded attachments are visible and removable in the Reference Files tab.
- Files cannot escape the configured private attachment directory.
- Tracked files do not contain attachment contents.
