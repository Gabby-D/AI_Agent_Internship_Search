"""Serve a simple local web UI for reviewing internship postings."""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from internship_search.private_inputs import (
    PrivateInputError,
    read_editable_text,
    replace_companies,
    replace_preferences,
    write_editable_text,
)
from internship_search.source_registry import load_seed_source_registry, write_source_registry
from internship_search.review_state import (
    append_activity_log,
    load_review_dashboard,
    parse_review_filters,
    preferences_from_payload,
    set_posting_note,
    set_posting_review,
)


def sanitize_attachment_filename(filename: str) -> str:
    import re
    # Extract only the base name (no folders/paths)
    base = Path(filename).name
    # Keep only safe characters: letters, numbers, dots, underscores, dashes
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "", base)
    # Ensure it's not empty or just dots
    if not sanitized or sanitized in (".", ".."):
        raise ValueError("Invalid filename")
    return sanitized


@dataclass(frozen=True)
class ReviewUIServer:
    host: str
    port: int
    data_dir: Path
    private_dir: Path


class ManualSearchController:
    """Run one complete collection workflow in the background at a time."""

    def __init__(
        self,
        data_dir: Path,
        private_dir: Path,
        runner: Callable[..., object] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.private_dir = private_dir
        self._runner = runner
        self._lock = threading.Lock()
        self._state: dict[str, object] = {
            "state": "idle",
            "message": "Ready to search all monitored companies.",
            "started_at": "",
            "finished_at": "",
        }

    def status(self) -> dict[str, object]:
        with self._lock:
            return dict(self._state)

    def start(self) -> tuple[bool, dict[str, object]]:
        with self._lock:
            if self._state["state"] == "running":
                return False, dict(self._state)
            self._state = {
                "state": "running",
                "message": "Searching every monitored company. This can take several minutes.",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": "",
            }
        threading.Thread(target=self._run, name="manual-internship-search", daemon=True).start()
        return True, self.status()

    def _run(self) -> None:
        try:
            runner = self._runner
            if runner is None:
                from internship_search.scheduled_collection import run_scheduled_collection

                runner = run_scheduled_collection
            result = runner(
                private_dir=self.private_dir,
                data_dir=self.data_dir,
                generate_email=False,
                send_email=False,
            )
            state = {
                "success": "succeeded",
                "partial": "partial",
            }.get(result.status, "failed")
            summary_label = "Search failed" if state == "failed" else "Search complete"
            message = (
                f"{summary_label}: {result.included_postings} matching internships found "
                f"from {result.postings_collected} job candidates."
            )
            if result.source_errors:
                message += (
                    f" {result.source_errors} source issue"
                    f"{'s' if result.source_errors != 1 else ''} were recorded for review."
                )
            completed = {
                "state": state,
                "message": message,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "postings_collected": result.postings_collected,
                "included_postings": result.included_postings,
                "source_errors": result.source_errors,
            }
        except Exception as error:  # noqa: BLE001 - surface background failures in the UI.
            completed = {
                "state": "failed",
                "message": f"Search failed: {error}",
                "started_at": str(self.status().get("started_at", "")),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        with self._lock:
            self._state = completed


def start_review_ui(
    host: str = "127.0.0.1",
    port: int = 8765,
    data_dir: Path | str = "data",
    private_dir: Path | str = "private",
    *,
    open_browser: bool = True,
) -> ReviewUIServer:
    data_path = Path(data_dir)
    private_path = Path(private_dir)
    handler = _build_handler(data_path=data_path, private_path=private_path)
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError as error:
        if is_address_in_use(error):
            raise SystemExit(
                f"Port {port} is already in use. Stop the other review-ui process or run:\n"
                f"  uv run internship-search review-ui --port {port + 1}"
            ) from error
        raise

    dashboard_url = f"http://{host}:{port}"
    print(f"Review UI running at {dashboard_url}")
    print("Keep this terminal open while you use the dashboard.")
    print("Press Ctrl+C to stop.")
    sys.stdout.flush()
    if open_browser:
        webbrowser.open(dashboard_url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping review UI.")
    finally:
        server.server_close()
    return ReviewUIServer(host=host, port=port, data_dir=data_path, private_dir=private_path)


def is_address_in_use(error: OSError) -> bool:
    if getattr(error, "winerror", None) == 10048:
        return True
    return error.errno in {48, 98, 10048}


def _build_handler(data_path: Path, private_path: Path):
    search_controller = ManualSearchController(data_path, private_path)

    class ReviewUIHandler(BaseHTTPRequestHandler):
        data_dir = data_path
        private_dir = private_path

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(render_review_page())
                return
            if parsed.path == "/api/dashboard":
                filters = parse_review_filters(parse_qs(parsed.query))
                payload = load_review_dashboard(self.data_dir, self.private_dir, filters=filters)
                self._send_json(payload)
                return
            if parsed.path == "/api/search-status":
                self._send_json({"ok": True, **search_controller.status()})
                return
            if parsed.path == "/api/inputs":
                self._send_json(self._input_payload())
                return
            if parsed.path == "/api/attachments":
                self._handle_get_attachments()
                return
            if parsed.path == "/api/attachments/download":
                self._handle_download_attachment(parsed.query)
                return
            self._send_error(404, "Not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_error(400, "Invalid JSON body")
                return

            if parsed.path == "/api/review":
                self._handle_review_update(payload)
                return
            if parsed.path == "/api/preferences":
                self._handle_preferences_update(payload)
                return
            if parsed.path == "/api/companies":
                self._handle_companies_update(payload)
                return
            if parsed.path == "/api/dismiss-company":
                self._handle_dismiss_company(payload)
                return
            if parsed.path == "/api/input-file":
                self._handle_input_file_update(payload)
                return
            if parsed.path == "/api/attachments/upload":
                self._handle_upload_attachment(payload)
                return
            if parsed.path == "/api/attachments/delete":
                self._handle_delete_attachment(payload)
                return
            if parsed.path == "/api/note":
                self._handle_note_update(payload)
                return
            if parsed.path == "/api/run-search":
                started, status = search_controller.start()
                self._send_json({"ok": True, "started": started, **status})
                return
            self._send_error(404, "Not found")

        def log_message(self, format: str, *args) -> None:
            return

        def _handle_review_update(self, payload: dict) -> None:
            posting_url = str(payload.get("posting_url", "")).strip()
            status = str(payload.get("status", "")).strip().lower()
            if not posting_url:
                self._send_error(400, "posting_url is required")
                return
            try:
                entry = set_posting_review(
                    posting_url=posting_url,
                    status=status,
                    output_path=self.data_dir / "posting_reviews.json",
                )
            except ValueError as error:
                self._send_error(400, str(error))
                return
            append_activity_log(
                action="opportunity_status_updated",
                subject=posting_url,
                details={"status": entry.status},
                output_path=self.data_dir / "activity_log.jsonl",
            )
            self._send_json({"ok": True, "review": entry.__dict__})

        def _handle_preferences_update(self, payload: dict) -> None:
            try:
                preferences = preferences_from_payload(payload)
                replace_preferences(
                    preferences.likes,
                    preferences.dislikes,
                    private_dir=self.private_dir,
                )
            except (PrivateInputError, ValueError) as error:
                self._send_error(400, str(error))
                return
            append_activity_log(
                action="preferences_updated",
                subject="preferences.md",
                details={"likes": len(preferences.likes), "dislikes": len(preferences.dislikes)},
                output_path=self.data_dir / "activity_log.jsonl",
            )
            self._send_json(
                {
                    "ok": True,
                    "preferences": {
                        "likes": preferences.likes,
                        "dislikes": preferences.dislikes,
                        "source": "private",
                    },
                }
            )

        def _handle_companies_update(self, payload: dict) -> None:
            companies = payload.get("companies", [])
            industries = payload.get("industries", [])
            if not isinstance(companies, list) or not isinstance(industries, list):
                self._send_error(400, "companies and industries must be lists.")
                return
            try:
                replace_companies(companies, industries, private_dir=self.private_dir)
                write_source_registry(
                    load_seed_source_registry(self.private_dir),
                    self.data_dir / "source_registry.json",
                )
            except (PrivateInputError, ValueError, TypeError) as error:
                self._send_error(400, str(error))
                return
            append_activity_log(
                action="company_list_updated",
                subject="list_of_companies.md",
                details={"companies": len(companies), "industries": len(industries)},
                output_path=self.data_dir / "activity_log.jsonl",
            )
            self._send_json({"ok": True})

        def _handle_input_file_update(self, payload: dict) -> None:
            filename = str(payload.get("filename", ""))
            content = payload.get("content", "")
            try:
                write_editable_text(filename, content, private_dir=self.private_dir)
            except (PrivateInputError, ValueError) as error:
                self._send_error(400, str(error))
                return
            append_activity_log(
                action="reference_file_updated",
                subject=filename,
                output_path=self.data_dir / "activity_log.jsonl",
            )
            self._send_json({"ok": True})

        def _handle_get_attachments(self) -> None:
            attachments_dir = Path(self.private_dir) / "attachments"
            if not attachments_dir.exists():
                self._send_json({"attachments": []})
                return
            
            from datetime import datetime, timezone
            import os
            
            attachments = []
            for file_path in sorted(attachments_dir.iterdir()):
                if file_path.is_file():
                    try:
                        mtime = os.path.getmtime(file_path)
                        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                        date_str = dt.isoformat()
                    except Exception:
                        date_str = datetime.now(timezone.utc).isoformat()
                        
                    attachments.append({
                        "filename": file_path.name,
                        "size_bytes": file_path.stat().st_size,
                        "date_uploaded": date_str,
                    })
            self._send_json({"attachments": attachments})

        def _handle_download_attachment(self, query_string: str) -> None:
            import urllib.parse
            params = urllib.parse.parse_qs(query_string)
            filename = params.get("filename", [""])[0].strip()
            if not filename:
                self._send_error(400, "filename is required")
                return
            
            try:
                sanitized = sanitize_attachment_filename(filename)
                attachments_dir = (Path(self.private_dir) / "attachments").resolve()
                file_path = (attachments_dir / sanitized).resolve()
                
                # Check path traversal
                if not str(file_path).startswith(str(attachments_dir)):
                    self._send_error(403, "Access denied")
                    return
                
                if not file_path.exists() or not file_path.is_file():
                    self._send_error(404, "File not found")
                    return
                
                content_bytes = file_path.read_bytes()
                
                # Guess mime type
                import mimetypes
                mime_type, _ = mimetypes.guess_type(sanitized)
                if not mime_type:
                    mime_type = "application/octet-stream"
                
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Disposition", f"attachment; filename=\"{sanitized}\"")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(content_bytes)))
                self.end_headers()
                self.wfile.write(content_bytes)
            except Exception as e:
                self._send_error(400, str(e))

        def _handle_upload_attachment(self, payload: dict) -> None:
            filename = str(payload.get("filename", "")).strip()
            content_base64 = str(payload.get("content_base64", "")).strip()
            
            if not filename or not content_base64:
                self._send_error(400, "filename and content_base64 are required")
                return
            
            try:
                # 1. Sanitize filename
                sanitized = sanitize_attachment_filename(filename)
                
                # 2. Check extension
                ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".png", ".jpg", ".jpeg", ".gif"}
                suffix = Path(sanitized).suffix.lower()
                if suffix not in ALLOWED_EXTENSIONS:
                    self._send_error(400, "Unsupported or unsafe file type. Only document and image attachments are supported.")
                    return
                
                # 3. Decode base64
                import base64
                try:
                    content_bytes = base64.b64decode(content_base64)
                except Exception:
                    self._send_error(400, "Invalid base64 content")
                    return
                
                # 4. Check size limit
                MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
                if len(content_bytes) > MAX_FILE_SIZE:
                    self._send_error(400, "File size exceeds 5MB limit.")
                    return
                
                # 5. Resolve paths and check directory traversal
                attachments_dir = (Path(self.private_dir) / "attachments").resolve()
                attachments_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = (attachments_dir / sanitized).resolve()
                if not str(file_path).startswith(str(attachments_dir)):
                    self._send_error(403, "Access denied")
                    return
                
                # 6. Save the file
                file_path.write_bytes(content_bytes)
                
                # 7. Log activity
                append_activity_log(
                    action="reference_attachment_uploaded",
                    subject=sanitized,
                    output_path=self.data_dir / "activity_log.jsonl",
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_error(400, str(e))

        def _handle_delete_attachment(self, payload: dict) -> None:
            filename = str(payload.get("filename", "")).strip()
            if not filename:
                self._send_error(400, "filename is required")
                return
            
            try:
                sanitized = sanitize_attachment_filename(filename)
                attachments_dir = (Path(self.private_dir) / "attachments").resolve()
                file_path = (attachments_dir / sanitized).resolve()
                
                if not str(file_path).startswith(str(attachments_dir)):
                    self._send_error(403, "Access denied")
                    return
                
                if file_path.exists() and file_path.is_file():
                    file_path.unlink()
                    append_activity_log(
                        action="reference_attachment_deleted",
                        subject=sanitized,
                        output_path=self.data_dir / "activity_log.jsonl",
                    )
                    self._send_json({"ok": True})
                else:
                    self._send_error(404, "File not found")
            except Exception as e:
                self._send_error(400, str(e))

        def _handle_note_update(self, payload: dict) -> None:
            posting_url = payload.get("posting_url", "")
            notes = payload.get("notes", "")
            try:
                saved_notes = set_posting_note(
                    str(posting_url),
                    notes,
                    output_path=self.data_dir / "posting_notes.json",
                )
            except ValueError as error:
                self._send_error(400, str(error))
                return
            append_activity_log(
                action="posting_note_updated",
                subject=str(posting_url),
                details={"has_notes": bool(saved_notes)},
                output_path=self.data_dir / "activity_log.jsonl",
            )
            self._send_json({"ok": True, "notes": saved_notes})

        def _handle_dismiss_company(self, payload: dict) -> None:
            name = str(payload.get("name", "")).strip()
            if not name:
                self._send_error(400, "Company name is required")
                return
            dismissed_path = self.data_dir / "company_dismissals.json"
            dismissed_names = []
            if dismissed_path.exists():
                try:
                    dismissed_names = json.loads(dismissed_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if name not in dismissed_names:
                dismissed_names.append(name)
            dismissed_path.parent.mkdir(parents=True, exist_ok=True)
            dismissed_path.write_text(json.dumps(dismissed_names, indent=2) + "\n", encoding="utf-8")
            append_activity_log(
                action="company_suggestion_dismissed",
                subject=name,
                output_path=self.data_dir / "activity_log.jsonl",
            )
            self._send_json({"ok": True})

        def _input_payload(self) -> dict:
            return {
                "files": {
                    filename: read_editable_text(filename, private_dir=self.private_dir)
                    for filename in (
                        "course_list.md",
                        "connections.md",
                        "resume_summary.md",
                    )
                }
            }

        def _send_html(self, content: str) -> None:
            encoded = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_error(self, status_code: int, message: str) -> None:
            payload = {"ok": False, "error": message}
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return ReviewUIHandler


def render_review_page() -> str:
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Internship Review</title>
  <style>
    :root {
      --bg: #f6f6fb;
      --surface: #ffffff;
      --border: #e6e6f0;
      --text: #1f2333;
      --text-muted: #6b7280;
      --accent: #4f46e5;
      --accent-soft: #eef2ff;
      --success: #15803d;
      --success-bg: #dcfce7;
      --neutral-bg: #f1f5f9;
      --neutral-text: #64748b;
      --danger: #b91c1c;
      --radius: 12px;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 20px rgba(15, 23, 42, 0.05);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .app-shell { max-width: 1080px; margin: 0 auto; padding: 32px 24px 72px; }
    header.topbar { margin-bottom: 12px; }
    .topbar-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
    header.topbar h1 { margin: 0; font-size: 22px; font-weight: 600; }
    .search-controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    #search-status { color: var(--text-muted); font-size: 13px; max-width: 520px; }
    #search-status.error { color: var(--danger); }
    #search-status.message { color: var(--success); }
    button:disabled { cursor: wait; opacity: .65; }
    .policy-banner {
      background: var(--accent-soft); color: #3730a3; border-radius: var(--radius);
      padding: 10px 14px; font-size: 13px; margin: 0 0 24px;
    }
    nav.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 24px; flex-wrap: wrap; }
    .tab-btn {
      border: none; background: none; padding: 10px 16px; font-size: 14px; font-weight: 500;
      color: var(--text-muted); cursor: pointer; border-bottom: 2px solid transparent;
    }
    .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
    .card {
      background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
      box-shadow: var(--shadow); padding: 20px; margin-bottom: 20px;
    }
    .card h2 { margin: 0 0 4px; font-size: 15px; font-weight: 600; }
    .card .subtitle { color: var(--text-muted); font-size: 13px; margin: 0 0 14px; }
    table.clean { width: 100%; border-collapse: collapse; }
    table.clean th {
      text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .03em;
      color: var(--text-muted); padding: 0 10px 8px; border-bottom: 1px solid var(--border);
    }
    table.clean td { padding: 10px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: middle; }
    table.clean tr:last-child td { border-bottom: none; }
    a { color: var(--accent); text-decoration: none; font-weight: 500; }
    a:hover { text-decoration: underline; }
    .badge {
      display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px;
      border-radius: 999px; font-size: 12px; font-weight: 600;
    }
    .badge.yes { background: var(--success-bg); color: var(--success); }
    .badge.no { background: var(--neutral-bg); color: var(--neutral-text); }
    select, textarea, input:not([type="checkbox"]) {
      border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; font: inherit; background: #fff;
      width: 100%;
    }
    textarea { min-height: 120px; resize: vertical; }
    input[type="checkbox"] { width: auto; height: 16px; }
    button {
      border: 1px solid var(--border); background: #fff; border-radius: 8px; padding: 8px 14px;
      font-size: 13px; font-weight: 500; cursor: pointer;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.danger { background: var(--danger); border-color: var(--danger); color: #fff; }
    .actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
    .empty { color: var(--text-muted); font-size: 14px; padding: 20px; text-align: center; }
    .message { color: var(--success); font-size: 13px; margin-top: 8px; }
    .error { color: var(--danger); font-size: 13px; margin-top: 8px; }
    ul.activity-list { list-style: none; margin: 0; padding: 0; }
    ul.activity-list li { padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
    ul.activity-list li:last-child { border-bottom: none; }
    .activity-date { color: var(--text-muted); font-size: 12px; display: block; }
    label.field { display: block; font-size: 13px; font-weight: 600; margin-bottom: 14px; }
    label.field textarea, label.field input { margin-top: 6px; }
    details.posting-details { margin-top: 8px; color: var(--text-muted); font-size: 13px; }
    details.posting-details summary { color: var(--accent); cursor: pointer; font-weight: 500; }
    .posting-summary { margin: 10px 0 8px; color: var(--text); white-space: pre-wrap; }
    .highlight-list { margin: 0 0 12px; padding-left: 18px; }
    .highlight-list li { margin: 4px 0; }
    .posting-note textarea { min-height: 84px; margin-top: 6px; }
    .note-actions { align-items: center; margin-top: 8px; }
  </style>
</head>
<body>
  <div id="js-debug-console" style="position: fixed; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.9); color: #ff5555; font-family: monospace; font-size: 13px; padding: 12px; z-index: 10000; display: none; max-height: 200px; overflow-y: auto; border-top: 3px solid #ff3333; box-shadow: 0 -4px 10px rgba(0,0,0,0.3);">
    <strong style="color: #ff3333;">Browser Javascript Errors:</strong>
    <button onclick="this.parentElement.style.display='none'" style="float: right; color: #fff; background: #ff3333; border: none; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;">Dismiss</button>
    <div id="js-debug-errors" style="margin-top: 8px;"></div>
  </div>
  <script>
    window.onerror = function(message, source, lineno, colno, error) {
      const consoleDiv = document.getElementById("js-debug-console");
      if (consoleDiv) consoleDiv.style.display = "block";
      const errorsDiv = document.getElementById("js-debug-errors");
      if (errorsDiv) {
        errorsDiv.innerHTML += `<div style="margin-bottom: 4px; border-bottom: 1px solid #444; padding-bottom: 4px;"><strong>${message}</strong><br><span style="color: #aaa; font-size: 11px;">at ${source}:${lineno}:${colno}</span></div>`;
      }
      return false;
    };
  </script>

  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-row">
        <h1>Internship Review</h1>
        <div class="search-controls">
          <span id="search-status">Ready to search all monitored companies.</span>
          <button id="run-search" class="primary" type="button">Run search now</button>
        </div>
      </div>
      <p id="location-policy" class="policy-banner"></p>
    </header>
    <nav class="tabs" role="tablist">
      <button class="tab-btn active" data-tab="postings" type="button">Postings</button>
      <button class="tab-btn" data-tab="companies" type="button">Companies</button>
      <button class="tab-btn" data-tab="preferences" type="button">Preferences</button>
      <button class="tab-btn" data-tab="files" type="button">Reference Files</button>
      <button class="tab-btn" data-tab="activity" type="button">Activity Log</button>
    </nav>
    <main>
      <section id="tab-postings" class="tab-panel active"><div id="postings"></div></section>
      <section id="tab-companies" class="tab-panel"><div id="companies-panel"></div></section>
      <section id="tab-preferences" class="tab-panel"><div id="preferences-panel"></div></section>
      <section id="tab-files" class="tab-panel"><div id="files-panel"></div></section>
      <section id="tab-activity" class="tab-panel"><div id="activity-panel"></div></section>
    </main>
  </div>

  <script>
    const statusLabels = {
      "to_review": "To review",
      "applied": "Applied",
      "not_interested": "Not interested",
      "archived": "Archived"
    };

    const statusOrder = ["to_review", "applied", "not_interested", "archived"];

    const sections = [
      { key: "to_review", title: "To review", match: posting => posting.review_status === "to_review" },
      { key: "applied", title: "Applied", match: posting => posting.review_status === "applied" },
      { key: "not_interested", title: "Not interested", match: posting => posting.review_status === "not_interested" },
      { key: "archived", title: "Archived", match: posting => posting.review_status === "archived" }
    ];
    let dashboardIndustries = [];
    let lastRenderedSearchCompletion = "";

    function orderedStatusOptions(statusOptions) {
      const remaining = statusOptions.filter(status => !statusOrder.includes(status));
      return statusOrder.filter(status => statusOptions.includes(status)).concat(remaining);
    }

    function initTabs() {
      document.querySelectorAll(".tab-btn").forEach(button => {
        button.addEventListener("click", () => switchTab(button.getAttribute("data-tab")));
      });
    }

    function switchTab(tabId) {
      document.querySelectorAll(".tab-btn").forEach(button => {
        button.classList.toggle("active", button.getAttribute("data-tab") === tabId);
      });
      document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === `tab-${tabId}`);
      });
      if (tabId === "files") {
        renderReferenceFiles();
      } else if (tabId === "companies" || tabId === "postings") {
        loadDashboard();
      }
    }

    async function loadDashboard() {
      const response = await fetch(`/api/dashboard?ts=${Date.now()}`);
      const data = await response.json();
      const policy = document.getElementById("location-policy");
      if (policy) {
        policy.textContent = data.location_policy || "";
      }
      renderPreferences(data.preferences || { likes: [], dislikes: [] });
      dashboardIndustries = data.industries || [];
      renderCompaniesPanel(data.monitored_companies || [], data.suggested_companies || []);
      renderActivityLog(data.activity || []);
      renderPostings(data.postings, data.status_options);
    }

    function renderSearchStatus(status) {
      const button = document.getElementById("run-search");
      const message = document.getElementById("search-status");
      if (!button || !message) return;
      const running = status.state === "running";
      button.disabled = running;
      button.textContent = running ? "Searching…" : "Run search now";
      message.className = status.state === "failed" ? "error" :
        (status.state === "succeeded" || status.state === "partial" ? "message" : "");
      message.textContent = status.message || "Ready to search all monitored companies.";
    }

    async function loadSearchStatus() {
      try {
        const response = await fetch(`/api/search-status?ts=${Date.now()}`);
        const status = await response.json();
        renderSearchStatus(status);
        return status;
      } catch (error) {
        renderSearchStatus({ state: "failed", message: `Could not check search status: ${error}` });
        return { state: "failed" };
      }
    }

    async function runSearchNow() {
      const button = document.getElementById("run-search");
      if (button) button.disabled = true;
      try {
        const status = await postJson("/api/run-search", {});
        renderSearchStatus(status);
      } catch (error) {
        renderSearchStatus({ state: "failed", message: `Could not start search: ${error}` });
      }
    }

    function escapeHtml(value) {
      if (value === undefined || value === null) {
        return "";
      }
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function websiteUrl(website) {
      const value = String(website || "").trim();
      if (!value) {
        return "";
      }
      const url = /^https?:\/\//i.test(value) ? value : `https://${value}`;
      return /^https?:\/\//i.test(url) ? url : "";
    }

    let autoSaveTimeout = null;
    function triggerAutoSave() {
      if (autoSaveTimeout) clearTimeout(autoSaveTimeout);
      autoSaveTimeout = setTimeout(async () => {
        const entries = getMyCompaniesFromDOM();
        const response = await postJson("/api/companies", {
          companies: entries,
          industries: listFromTextarea(document.getElementById("industries-input").value),
        });
        const msg = document.getElementById("companies-message");
        if (msg) {
          if (response.ok) {
            msg.className = "message";
            msg.textContent = "Changes auto-saved.";
          } else {
            msg.className = "error";
            msg.textContent = "Auto-save failed: " + (response.error || "unknown error");
          }
          setTimeout(() => {
            if (msg.textContent === "Changes auto-saved.") {
              msg.textContent = "";
            }
          }, 2000);
        }
      }, 750);
    }

    function renderCompaniesPanel(companies, suggestedCompanies) {
      const container = document.getElementById("companies-panel");
      const rows = companies.map(companyRow).join("");

      const suggestedRows = suggestedCompanies.map(s => {
        const prov = [];
        if (s.reason) prov.push(`<strong>Why:</strong> ${escapeHtml(s.reason)}`);
        if (s.source) prov.push(`<strong>Source:</strong> ${escapeHtml(s.source)}`);
        if (s.industry_tags && s.industry_tags.length) prov.push(`<strong>Tags:</strong> ${escapeHtml(s.industry_tags.join(", "))}`);
        if (s.evidence_title) {
          const title = escapeHtml(s.evidence_title);
          const url = s.evidence_url ? escapeHtml(s.evidence_url) : '#';
          const snippet = s.evidence_snippet ? `: <em>"${escapeHtml(s.evidence_snippet)}"</em>` : '';
          prov.push(`<strong>Evidence:</strong> <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>${snippet}`);
        }
        const provHtml = prov.map(p => `<div style="margin-bottom: 4px; line-height: 1.4;">${p}</div>`).join("");

        return `
          <tr data-name="${escapeHtml(s.name)}">
            <td>
              <strong>${escapeHtml(s.name)}</strong>
              <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                <details>
                  <summary style="cursor: pointer; color: var(--accent); font-weight: 500;">Show provenance details</summary>
                  <div style="margin-top: 6px; padding: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px;">
                    ${provHtml}
                  </div>
                </details>
              </div>
            </td>
            <td>
              <a href="${escapeHtml(websiteUrl(s.careers_url || s.website))}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.careers_url || s.website)}</a>
            </td>
            <td style="white-space: nowrap;">
              <div class="actions" style="margin: 0; gap: 8px; justify-content: flex-start;">
                <button class="primary add-suggested-btn" type="button" onclick="addSuggestionToMyCompanies('${escapeHtml(s.name).replace(/'/g, "\\'")}', '${escapeHtml(s.website || "").replace(/'/g, "\\'")}', '${escapeHtml(s.careers_url || "").replace(/'/g, "\\'")}')">Add to My Companies</button>
                <button class="dismiss-suggested-btn" type="button" onclick="dismissSuggestedCompany('${escapeHtml(s.name).replace(/'/g, "\\'")}')">Dismiss</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");

      const suggestedCard = suggestedCompanies.length ? `
        <div class="card" style="margin-top: 24px;">
          <h2>Suggested Companies <span class="empty" style="display:inline;padding:0;">(${suggestedCompanies.length} available)</span></h2>
          <p class="subtitle">Recommendations aligned with your search preferences. Review provenance, then add them to My Companies or dismiss them.</p>
          <table class="clean" id="suggested-companies-table">
            <thead><tr><th style="width: 45%;">Company</th><th style="width: 35%;">Career page</th><th style="width: 20%;">Actions</th></tr></thead>
            <tbody>${suggestedRows}</tbody>
          </table>
        </div>
      ` : `
        <div class="card" style="margin-top: 24px;">
          <h2>Suggested Companies</h2>
          <p class="empty">No new company suggestions available at the moment.</p>
        </div>
      `;

      container.innerHTML = `
        <div class="card">
          <details class="industries-details" style="margin-bottom: 0px;">
            <summary style="font-weight: 600; font-size: 15px; cursor: pointer; color: var(--text);">Industries of interest</summary>
            <div style="margin-top: 10px;">
              <p class="subtitle" style="margin-bottom: 8px;">One industry per line. These terms are used to guide web-search company discovery.</p>
              <textarea id="industries-input" style="height: 100px;">${escapeHtml(dashboardIndustries.join("\n"))}</textarea>
            </div>
          </details>
        </div>

        ${suggestedCard}

        <div class="card" style="margin-top: 24px;">
          <h2>My Companies <span class="empty" style="display:inline;padding:0;">(${companies.length} monitored)</span></h2>
          <p class="subtitle">Add, edit, or remove companies you're tracking. Use official career or jobs-search pages so links and collection target the right place. Saving updates your live source registry.</p>
          
          <div class="actions" style="margin-bottom: 12px; margin-top: 12px;">
            <button id="add-company" class="primary" type="button">Add company</button>
          </div>
          
          <table class="clean" id="company-editor-table">
            <thead><tr><th>Company</th><th>Career page</th><th>Latest scan</th><th>Know someone?</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
          
          <div class="actions" style="margin-top: 20px;">
            <button id="save-companies" class="primary" type="button">Save changes</button>
          </div>
          <p id="companies-message"></p>
        </div>
      `;

      // Event listeners are initialized once at page load in initCompaniesPanel()
    }

    function getMyCompaniesFromDOM() {
      const container = document.getElementById("companies-panel");
      return [...container.querySelectorAll("#company-editor-table tbody tr")].map(row => ({
        name: row.querySelector('[data-field="name"]').value.trim(),
        website: row.querySelector('[data-field="website"]').value.trim(),
        has_connection: row.querySelector('[data-field="connection"]').checked,
        connection_name: row.querySelector('[data-field="connection_name"]').value.trim(),
      })).filter(company => company.name || company.website);
    }

    async function addSuggestionToMyCompanies(name, website, careersUrl) {
      const entries = getMyCompaniesFromDOM();
      // Avoid duplicate names if they clicked multiple times
      if (entries.some(e => e.name.toLowerCase() === name.toLowerCase())) {
        alert("This company is already in My Companies.");
        return;
      }
      entries.push({
        name: name,
        website: careersUrl || website || "",
        has_connection: false,
        connection_name: "",
      });
      const response = await postJson("/api/companies", {
        companies: entries,
        industries: listFromTextarea(document.getElementById("industries-input").value),
      });
      if (response.ok) {
        await loadDashboard();
      } else {
        alert("Error adding company: " + (response.error || "unknown error"));
      }
    }

    async function dismissSuggestedCompany(name) {
      const response = await postJson("/api/dismiss-company", { name });
      if (response.ok) {
        await loadDashboard();
      } else {
        alert("Error dismissing company: " + (response.error || "unknown error"));
      }
    }

    function toggleConnectionCheckbox(checkbox) {
      const parentLabel = checkbox.parentElement;
      const connectionNameInput = parentLabel.nextElementSibling;
      if (connectionNameInput) {
        connectionNameInput.style.display = checkbox.checked ? 'block' : 'none';
        if (!checkbox.checked) {
          connectionNameInput.value = '';
          triggerAutoSave();
        }
      }
    }

    function companyRow(company) {
      const showNameInput = company.has_connection ? 'block' : 'none';
      let scanStatus = '<span class="empty">Not scanned yet</span>';
      if (company.source_issue) {
        scanStatus = `<span class="error" title="${escapeHtml(company.source_issue)}">Source issue</span>`;
      } else if (company.has_scan_results) {
        const count = Number(company.internships_found || 0);
        scanStatus = `<span class="message">Working</span><div class="empty" style="padding: 3px 0 0;">${count} internship${count === 1 ? "" : "s"} found</div>`;
      }
      return `<tr>
        <td><input data-field="name" value="${escapeHtml(company.name || "")}" aria-label="Company name"></td>
        <td><input data-field="website" value="${escapeHtml(company.careers_url || company.website || "")}" aria-label="Career page URL"></td>
        <td>${scanStatus}</td>
        <td>
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <label style="display: flex; align-items: center; gap: 6px; font-weight: normal; font-size: 13px;">
              <input data-field="connection" type="checkbox" ${company.has_connection ? "checked" : ""} onchange="toggleConnectionCheckbox(this)">
              Know someone?
            </label>
            <input data-field="connection_name" type="text" placeholder="Who?" value="${escapeHtml(company.connection_name || "")}" style="display: ${showNameInput}; font-size: 12px; padding: 4px 6px;" aria-label="Connection name">
          </div>
        </td>
        <td><button class="remove-company" type="button">Remove</button></td>
      </tr>`;
    }

    function renderPreferences(preferences) {
      const container = document.getElementById("preferences-panel");
      container.innerHTML = `
        <div class="card">
          <h2>Search preferences</h2>
          <p class="subtitle">One preference per line. These settings are used by future scoring runs.</p>
          <label class="field">Things I like<textarea id="likes-input">${escapeHtml((preferences.likes || []).join("\n"))}</textarea></label>
          <label class="field">Things I don't like<textarea id="dislikes-input">${escapeHtml((preferences.dislikes || []).join("\n"))}</textarea></label>
          <div class="actions"><button id="save-preferences" class="primary" type="button">Save preferences</button></div>
          <p id="preferences-message"></p>
        </div>
      `;
      container.querySelector("#save-preferences").addEventListener("click", async () => {
        const response = await postJson("/api/preferences", {
          likes: listFromTextarea(container.querySelector("#likes-input").value),
          dislikes: listFromTextarea(container.querySelector("#dislikes-input").value),
        });
        showMessage(container.querySelector("#preferences-message"), response, "Preferences saved.");
        if (response.ok) await loadDashboard();
      });
    }

    let referenceFilesLoaded = false;
    async function renderReferenceFiles() {
      const container = document.getElementById("files-panel");
      if (referenceFilesLoaded) return;
      container.innerHTML = '<p class="empty">Loading reference files…</p>';
      
      // Fetch text files
      const textResponse = await fetch("/api/inputs");
      const textData = await textResponse.json();
      if (!textResponse.ok) {
        container.innerHTML = `<p class="error">${escapeHtml(textData.error || "Unable to load reference files.")}</p>`;
        return;
      }

      // Fetch attachments
      let attachments = [];
      try {
        const attResponse = await fetch("/api/attachments");
        const attData = await attResponse.json();
        if (attResponse.ok) {
          attachments = attData.attachments || [];
        }
      } catch (e) {
        console.error("Error loading attachments:", e);
      }

      referenceFilesLoaded = true;
      const labels = {
        "course_list.md": "Course and program information",
        "connections.md": "Connection notes",
        "resume_summary.md": "Resume summary",
      };

      // 1. Text Card HTML
      const textCardsHtml = Object.entries(textData.files).map(([filename, content]) => `
        <div class="card">
          <h2>${escapeHtml(labels[filename] || filename)}</h2>
          <textarea data-file="${escapeHtml(filename)}">${escapeHtml(content)}</textarea>
          <div class="actions"><button data-save-file="${escapeHtml(filename)}" class="primary" type="button">Save</button></div>
          <p class="save-message" data-message-for="${escapeHtml(filename)}"></p>
        </div>
      `).join("");

      // 2. Attachments Card HTML Helpers
      function formatSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
      }

      function formatDate(isoStr) {
        try {
          const d = new Date(isoStr);
          return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch(e) {
          return isoStr;
        }
      }

      let attachmentsHtml = '';
      if (attachments.length === 0) {
        attachmentsHtml = '<p class="empty" style="margin: 16px 0;">No attachments uploaded yet.</p>';
      } else {
        const rows = attachments.map(att => `
          <tr data-filename="${escapeHtml(att.filename)}">
            <td>
              <a href="/api/attachments/download?filename=${encodeURIComponent(att.filename)}" target="_blank" style="font-weight: 500;">
                ${escapeHtml(att.filename)}
              </a>
            </td>
            <td>${formatSize(att.size_bytes)}</td>
            <td>${formatDate(att.date_uploaded)}</td>
            <td>
              <div class="actions" style="margin:0; gap: 8px; justify-content: flex-start;">
                <button class="replace-attachment-btn" type="button" data-replace="${escapeHtml(att.filename)}">Replace</button>
                <button class="danger delete-attachment-btn" type="button" data-delete="${escapeHtml(att.filename)}">Delete</button>
              </div>
            </td>
          </tr>
        `).join("");
        
        attachmentsHtml = `
          <table class="clean" style="margin-top: 12px; margin-bottom: 16px;">
            <thead>
              <tr>
                <th style="width: 45%;">File Name</th>
                <th style="width: 15%;">Size</th>
                <th style="width: 25%;">Uploaded At</th>
                <th style="width: 15%;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rows}
            </tbody>
          </table>
        `;
      }

      const attachmentsCard = `
        <div class="card" style="margin-top: 24px;">
          <h2>Supporting Attachments</h2>
          <p class="subtitle">Upload supporting materials such as full resumes, transcripts, or reference letters. Supported formats: PDF, Word (.docx, .doc), text (.txt, .md), and images. Max size: 5MB.</p>
          
          ${attachmentsHtml}
          
          <div style="border-top: 1px solid var(--border); padding-top: 16px; margin-top: 16px;">
            <div style="display: flex; align-items: center; gap: 12px;">
              <input type="file" id="attachment-file-input" style="flex: 1;" accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg,.gif">
              <button id="upload-attachment-btn" class="primary" type="button">Upload file</button>
            </div>
            <p id="attachment-message" style="margin-top: 10px; font-size: 14px;"></p>
          </div>
        </div>
      `;

      container.innerHTML = textCardsHtml + attachmentsCard;

      // 3. Setup Listeners for Text Files
      container.querySelectorAll("[data-save-file]").forEach(button => button.addEventListener("click", async () => {
        const filename = button.getAttribute("data-save-file");
        const content = container.querySelector(`[data-file="${filename}"]`).value;
        const result = await postJson("/api/input-file", { filename, content });
        showMessage(container.querySelector(`[data-message-for="${filename}"]`), result, `${filename} saved.`);
        if (result.ok) {
          await loadDashboard();
          referenceFilesLoaded = false;
          await renderReferenceFiles();
        }
      }));

      // 4. Setup Listeners for Attachments
      const fileInput = container.querySelector("#attachment-file-input");
      const uploadBtn = container.querySelector("#upload-attachment-btn");
      const msgEl = container.querySelector("#attachment-message");
      let replaceTargetFilename = null;

      container.querySelectorAll(".delete-attachment-btn").forEach(button => button.addEventListener("click", async () => {
        const filename = button.getAttribute("data-delete");
        if (confirm(`Are you sure you want to delete "${filename}"?`)) {
          const result = await postJson("/api/attachments/delete", { filename });
          showMessage(msgEl, result, `${filename} deleted.`);
          if (result.ok) {
            referenceFilesLoaded = false;
            setTimeout(async () => {
              await renderReferenceFiles();
            }, 1000);
          }
        }
      }));

      container.querySelectorAll(".replace-attachment-btn").forEach(button => button.addEventListener("click", () => {
        replaceTargetFilename = button.getAttribute("data-replace");
        fileInput.click();
      }));

      uploadBtn.addEventListener("click", async () => {
        const file = fileInput.files[0];
        if (!file) {
          msgEl.className = "error";
          msgEl.textContent = "Please select a file first.";
          return;
        }
        await uploadFile(file, file.name);
      });

      fileInput.addEventListener("change", async () => {
        if (replaceTargetFilename) {
          const file = fileInput.files[0];
          if (file) {
            await uploadFile(file, replaceTargetFilename);
          }
          replaceTargetFilename = null;
          fileInput.value = ""; // Reset picker
        }
      });

      async function uploadFile(file, destFilename) {
        if (file.size > 5 * 1024 * 1024) {
          msgEl.className = "error";
          msgEl.textContent = "File size exceeds 5MB limit.";
          return;
        }
        
        const allowed = [".pdf", ".docx", ".doc", ".txt", ".md", ".png", ".jpg", ".jpeg", ".gif"];
        const ext = destFilename.slice(destFilename.lastIndexOf(".")).toLowerCase();
        if (!allowed.includes(ext)) {
          msgEl.className = "error";
          msgEl.textContent = "Unsupported file type.";
          return;
        }

        msgEl.className = "message";
        msgEl.textContent = "Uploading...";
        
        const reader = new FileReader();
        reader.onerror = () => {
          msgEl.className = "error";
          msgEl.textContent = "Error reading file.";
        };
        reader.onload = async () => {
          const base64 = reader.result.split(",")[1];
          const result = await postJson("/api/attachments/upload", {
            filename: destFilename,
            content_base64: base64,
            mime_type: file.type
          });
          showMessage(msgEl, result, `${destFilename} uploaded successfully.`);
          if (result.ok) {
            referenceFilesLoaded = false;
            setTimeout(async () => {
              await renderReferenceFiles();
            }, 1000);
          }
        };
        reader.readAsDataURL(file);
      }
    }

    function listFromTextarea(value) {
      return value.split("\n").map(item => item.trim()).filter(Boolean);
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return { ok: response.ok, ...(await response.json()) };
    }

    function showMessage(element, response, success) {
      element.className = response.ok ? "message" : "error";
      element.textContent = response.ok ? success : response.error || "Save failed.";
    }

    let currentActivityEvents = [];
    let activityFilterType = "all";
    let activityFilterStart = "";
    let activityFilterEnd = "";

    function renderActivityLog(events) {
      currentActivityEvents = events;
      const container = document.getElementById("activity-panel");
      if (!events.length) {
        container.innerHTML = '<div class="card"><p class="empty">No activity has been logged yet.</p></div>';
        return;
      }
      
      const types = ["all", "posting status", "note edit", "company edit", "file upload", "collection", "scoring", "email", "other"];
      const typeOptions = types.map(t => 
        `<option value="${t}" ${activityFilterType === t ? "selected" : ""}>${t.charAt(0).toUpperCase() + t.slice(1)}</option>`
      ).join("");

      container.innerHTML = `
        <div class="card">
          <h2>Activity log</h2>
          <div style="display: flex; gap: 16px; margin: 16px 0; padding: 12px; background: var(--bg); border-radius: var(--radius); border: 1px solid var(--border); flex-wrap: wrap; align-items: flex-end;">
            <div style="flex: 1; min-width: 140px;">
              <label style="font-size: 12px; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 6px;">Activity Type</label>
              <select id="act-type-filter" style="padding: 6px 10px; font-size: 13px;">
                ${typeOptions}
              </select>
            </div>
            <div style="flex: 1; min-width: 140px;">
              <label style="font-size: 12px; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 6px;">From Date</label>
              <input type="date" id="act-start-filter" value="${escapeHtml(activityFilterStart)}" style="padding: 5px 10px; font-size: 13px;">
            </div>
            <div style="flex: 1; min-width: 140px;">
              <label style="font-size: 12px; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 6px;">To Date</label>
              <input type="date" id="act-end-filter" value="${escapeHtml(activityFilterEnd)}" style="padding: 5px 10px; font-size: 13px;">
            </div>
            <div style="display: flex; gap: 8px;">
              <button id="act-clear-btn" type="button" style="padding: 6px 12px; font-size: 13px;">Clear</button>
            </div>
          </div>
          
          <ul class="activity-list" id="activity-list-container"></ul>
          <p id="activity-count" style="margin-top: 12px; font-size: 13px; color: var(--text-muted);"></p>
        </div>
      `;

      const typeSel = container.querySelector("#act-type-filter");
      const startIn = container.querySelector("#act-start-filter");
      const endIn = container.querySelector("#act-end-filter");
      const clearBtn = container.querySelector("#act-clear-btn");

      const applyFilters = () => {
        activityFilterType = typeSel.value;
        activityFilterStart = startIn.value;
        activityFilterEnd = endIn.value;
        updateFilteredActivityList();
      };

      typeSel.addEventListener("change", applyFilters);
      startIn.addEventListener("change", applyFilters);
      endIn.addEventListener("change", applyFilters);
      
      clearBtn.addEventListener("click", () => {
        typeSel.value = "all";
        startIn.value = "";
        endIn.value = "";
        applyFilters();
      });

      updateFilteredActivityList();
    }

    function updateFilteredActivityList() {
      const listContainer = document.getElementById("activity-list-container");
      const countEl = document.getElementById("activity-count");
      if (!listContainer) return;

      const filtered = currentActivityEvents.filter(event => {
        if (activityFilterType !== "all") {
          const type = event.activity_type || "other";
          if (type !== activityFilterType) return false;
        }
        if (activityFilterStart && event.date < activityFilterStart) return false;
        if (activityFilterEnd && event.date > activityFilterEnd) return false;
        return true;
      });

      if (filtered.length === 0) {
        listContainer.innerHTML = '<li class="empty" style="text-align: center; color: var(--text-muted); padding: 16px 0;">No matching log entries found.</li>';
        countEl.textContent = "Showing 0 of " + currentActivityEvents.length + " actions";
        return;
      }

      listContainer.innerHTML = filtered.map(event => {
        const type = event.activity_type || "other";
        let costHtml = "";
        const details = event.details || {};
        const apiInvoked = event.api_invoked !== undefined ? event.api_invoked : details.api_invoked;
        const cost = event.cost || details.cost || {};
        
        if (apiInvoked) {
          if (cost.amount !== undefined && cost.amount !== null) {
            const formattedAmount = cost.amount.toFixed(2);
            costHtml = `
              <span class="badge yes" style="margin-left: 8px; font-size: 11px; padding: 1px 6px;" title="Basis: ${escapeHtml(cost.basis || 'API charge')}">
                Cost: ${escapeHtml(cost.currency || 'USD')} ${escapeHtml(formattedAmount)}
              </span>
            `;
          } else {
            costHtml = `
              <span class="badge no" style="margin-left: 8px; font-size: 11px; padding: 1px 6px;" title="Cost details are unavailable">
                Cost: Unavailable
              </span>
            `;
          }
        } else {
          costHtml = `
            <span class="badge no" style="margin-left: 8px; font-size: 11px; padding: 1px 6px;" title="Local action - no API or cost incurred">
              Cost: N/A
            </span>
          `;
        }

        const typeBadgeColors = {
          "posting status": "background: #e0f2fe; color: #0369a1;",
          "note edit": "background: #fef3c7; color: #b45309;",
          "company edit": "background: #f3e8ff; color: #7e22ce;",
          "file upload": "background: #dcfce7; color: #15803d;",
          "collection": "background: #e11d48; color: #fff;",
          "scoring": "background: #4f46e5; color: #fff;",
          "email": "background: #0d9488; color: #fff;",
          "other": "background: #f1f5f9; color: #64748b;"
        };
        const typeStyle = typeBadgeColors[type] || typeBadgeColors["other"];
        const typeBadge = `<span class="badge" style="margin-right: 8px; font-size: 11px; padding: 2px 8px; font-weight: 600; border-radius: 4px; ${typeStyle}">${escapeHtml(type)}</span>`;

        return `
          <li style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border);">
            <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
              <span class="activity-date" style="margin-right: 8px; width: 85px; flex-shrink: 0; font-size: 12px; color: var(--text-muted); font-weight: 500;">${escapeHtml(event.date)}</span>
              ${typeBadge}
              <span style="font-weight: 500; font-size: 14px;">${escapeHtml(event.action)}</span>: 
              <span style="color: var(--text-muted); font-size: 13px;">${escapeHtml(event.subject)}</span>
            </div>
            <div>
              ${costHtml}
            </div>
          </li>
        `;
      }).join("");

      countEl.textContent = "Showing " + filtered.length + " of " + currentActivityEvents.length + " actions";
    }

    function renderTable(postings, statusOptions) {
      if (!postings.length) {
        return '<p class="empty">No internships in this list.</p>';
      }

      const rows = postings.map(posting => {
        const options = orderedStatusOptions(statusOptions).map(status =>
            `<option value="${status}" ${posting.review_status === status ? "selected" : ""}>${statusLabels[status]}</option>`
          );
        const postingUrl = websiteUrl(posting.posting_url);
        const postingLink = postingUrl
          ? `<a href="${escapeHtml(postingUrl)}" target="_blank" rel="noopener noreferrer">Open posting</a>`
          : "Posting URL unavailable";
        const connectionBadge = posting.has_connection
          ? '<span class="badge yes">Know someone</span>'
          : '<span class="badge no">No connection</span>';
        const highlights = (posting.highlights || []).map(highlight =>
          `<li>${escapeHtml(highlight)}</li>`
        ).join("") || "<li>No additional highlights are available yet.</li>";
        
        let companyCell = escapeHtml(posting.company);
        if (posting.suggested_company_overview) {
          companyCell = `
            <div>
              <strong>${escapeHtml(posting.company)}</strong>
              <details style="font-size: 12px; margin-top: 4px; color: var(--text-muted);">
                <summary style="cursor: pointer; color: var(--accent); font-weight: 500;">Why suggested?</summary>
                <div style="margin-top: 4px; padding: 8px; background: var(--neutral-bg); border-radius: 6px; line-height: 1.4; white-space: normal;">
                  <strong>${escapeHtml(posting.suggested_company_overview.company_name)}</strong> is suggested because:
                  <p style="margin: 4px 0 0; font-size: 11px;">${escapeHtml(posting.suggested_company_overview.reason)}</p>
                  <span style="font-size: 10px; color: var(--text-muted); display: block; margin-top: 4px;">Source: ${escapeHtml(posting.suggested_company_overview.source)}</span>
                </div>
              </details>
            </div>
          `;
        }

        return `
          <tr>
            <td>
              <strong>${escapeHtml(posting.title)}</strong>
              <details class="posting-details">
                <summary>Summary &amp; notes</summary>
                <p class="posting-summary">${escapeHtml(posting.summary || "")}</p>
                <strong>Highlights</strong>
                <ul class="highlight-list">${highlights}</ul>
                <label class="field posting-note">Your notes
                  <textarea data-note-url="${escapeHtml(posting.posting_url)}" aria-label="Notes for ${escapeHtml(posting.title)}">${escapeHtml(posting.notes || "")}</textarea>
                </label>
                <div class="actions note-actions">
                  <button data-save-note="${escapeHtml(posting.posting_url)}" type="button">Save notes</button>
                  <span class="save-message"></span>
                </div>
              </details>
            </td>
            <td>${companyCell}</td>
            <td>${escapeHtml(posting.location)}</td>
            <td>${connectionBadge}</td>
            <td>${postingLink}</td>
            <td><select data-url="${escapeHtml(posting.posting_url)}">${options.join("")}</select></td>
          </tr>
        `;
      }).join("");

      return `
        <table class="clean">
          <thead>
            <tr>
              <th>Job title</th>
              <th>Company</th>
              <th>Location</th>
              <th>Connection</th>
              <th>Link</th>
              <th>Review status</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderPostings(postings, statusOptions) {
      const container = document.getElementById("postings");
      if (!postings.length) {
        container.innerHTML = '<div class="card"><p class="empty">No internships in this list.</p></div>';
        return;
      }

      const visibleSections = sections
        .map(section => ({
          ...section,
          sectionPostings: postings.filter(section.match),
        }))
        .filter(section => section.sectionPostings.length);

      if (!visibleSections.length) {
        container.innerHTML = '<div class="card"><p class="empty">No internships in this list.</p></div>';
        return;
      }

      container.innerHTML = visibleSections.map(section => `
          <div class="card">
            <h2>${section.title} <span class="empty" style="display:inline;padding:0;">(${section.sectionPostings.length})</span></h2>
            ${renderTable(section.sectionPostings, statusOptions)}
          </div>
        `).join("");

      container.querySelectorAll("select").forEach(select => {
        select.addEventListener("change", async (event) => {
          const postingUrl = event.target.getAttribute("data-url");
          const status = event.target.value;
          await fetch("/api/review", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ posting_url: postingUrl, status })
          });
          await loadDashboard();
        });
      });
      container.querySelectorAll("[data-save-note]").forEach(button => {
        button.addEventListener("click", async () => {
          const postingUrl = button.getAttribute("data-save-note");
          const details = button.closest(".posting-details");
          const notes = details.querySelector("[data-note-url]").value;
          const result = await postJson("/api/note", { posting_url: postingUrl, notes });
          showMessage(details.querySelector(".save-message"), result, "Notes saved.");
        });
      });
    }

    function initCompaniesPanel() {
      document.addEventListener("click", event => {
        const target = event.target;
        if (!target) return;

        if (target.id === "add-company") {
          event.preventDefault();
          const tbody = document.getElementById("company-editor-table")?.querySelector("tbody");
          if (tbody) {
            tbody.insertAdjacentHTML("afterbegin", companyRow({ name: "", careers_url: "", has_connection: false, connection_name: "" }));
          }
        } else if (target.id === "save-companies") {
          event.preventDefault();
          (async () => {
            const entries = getMyCompaniesFromDOM();
            const response = await postJson("/api/companies", {
              companies: entries,
              industries: listFromTextarea(document.getElementById("industries-input").value),
            });
            showMessage(document.getElementById("companies-message"), response, "Company list and industries saved.");
            if (response.ok) await loadDashboard();
          })();
        } else if (target.classList.contains("remove-company")) {
          event.preventDefault();
          target.closest("tr")?.remove();
          triggerAutoSave();
        }
      });

      document.addEventListener("input", event => {
        const target = event.target;
        const field = target.getAttribute("data-field");
        if (field === "name" || field === "website" || field === "connection_name" || target.id === "industries-input") {
          triggerAutoSave();
        }
      });

      document.addEventListener("change", event => {
        const target = event.target;
        const field = target.getAttribute("data-field");
        if (field === "connection") {
          triggerAutoSave();
        }
      });
    }

    initTabs();
    document.getElementById("run-search").addEventListener("click", runSearchNow);
    initCompaniesPanel();
    loadDashboard();
    loadSearchStatus();
    setInterval(() => {
      if (!document.querySelector("textarea:focus, input:focus")) {
        loadDashboard();
      }
    }, 30000);
    setInterval(async () => {
      if (document.visibilityState !== "visible") return;
      const status = await loadSearchStatus();
      if (
        (status.state === "succeeded" || status.state === "partial") &&
        status.finished_at &&
        status.finished_at !== lastRenderedSearchCompletion
      ) {
        lastRenderedSearchCompletion = status.finished_at;
        loadDashboard();
      }
    }, 3000);
  </script>
</body>
</html>"""
