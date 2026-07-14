"""Serve a simple local web UI for reviewing internship postings."""

from __future__ import annotations

import json
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from internship_search.review_state import (
    load_review_dashboard,
    parse_review_filters,
    preferences_from_payload,
    save_ui_preferences,
    set_posting_review,
)


@dataclass(frozen=True)
class ReviewUIServer:
    host: str
    port: int
    data_dir: Path
    private_dir: Path


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
            self._send_json({"ok": True, "review": entry.__dict__})

        def _handle_preferences_update(self, payload: dict) -> None:
            try:
                preferences = preferences_from_payload(payload)
            except ValueError as error:
                self._send_error(400, str(error))
                return
            path = save_ui_preferences(
                likes=preferences.likes,
                dislikes=preferences.dislikes,
                output_path=self.data_dir / "ui_preferences.json",
            )
            self._send_json(
                {
                    "ok": True,
                    "preferences": {
                        "likes": preferences.likes,
                        "dislikes": preferences.dislikes,
                        "source": "ui",
                    },
                    "path": str(path),
                }
            )

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
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Internship Review</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f7f7f8; color: #1f2933; }
    h1 { margin-bottom: 20px; }
    h2 { margin: 0 0 12px; font-size: 18px; }
    .section { margin-bottom: 28px; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9dde3; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }
    th { background: #f8fafc; font-size: 14px; }
    td { font-size: 14px; }
    a { color: #1d4ed8; }
    select { width: 100%; max-width: 180px; }
    .empty { padding: 12px; background: #fff; border: 1px solid #d9dde3; color: #52606d; font-size: 14px; }
    .count { color: #52606d; font-weight: normal; font-size: 14px; }
  </style>
</head>
<body>
  <h1>Internship Review</h1>
  <p id="location-policy" class="empty"></p>
  <div id="postings"></div>

  <script>
    const statusLabels = {
      "": "Not reviewed",
      "interested": "Interested",
      "applied": "Applied",
      "ignored": "Ignored",
      "needs_follow_up": "Needs follow-up"
    };

    const statusOrder = ["interested", "applied", "needs_follow_up", "ignored"];

    const sections = [
      { key: "to_review", title: "To review", match: posting => !posting.review_status },
      { key: "interested", title: "Interested", match: posting => posting.review_status === "interested" },
      { key: "applied", title: "Applied", match: posting => posting.review_status === "applied" },
      { key: "needs_follow_up", title: "Needs follow-up", match: posting => posting.review_status === "needs_follow_up" },
      { key: "ignored", title: "Ignored", match: posting => posting.review_status === "ignored" }
    ];

    function orderedStatusOptions(statusOptions) {
      const remaining = statusOptions.filter(status => !statusOrder.includes(status));
      return statusOrder.filter(status => statusOptions.includes(status)).concat(remaining);
    }

    async function loadDashboard() {
      const response = await fetch(`/api/dashboard?ts=${Date.now()}`);
      const data = await response.json();
      const policy = document.getElementById("location-policy");
      if (policy) {
        policy.textContent = data.location_policy || "";
      }
      renderPostings(data.postings, data.status_options);
    }

    function renderTable(postings, statusOptions) {
      if (!postings.length) {
        return '<p class="empty">No internships in this list.</p>';
      }

      const rows = postings.map(posting => {
        const options = ['<option value="">Not reviewed</option>']
          .concat(orderedStatusOptions(statusOptions).map(status =>
            `<option value="${status}" ${posting.review_status === status ? "selected" : ""}>${statusLabels[status]}</option>`
          ));
        return `
          <tr>
            <td>${posting.title}</td>
            <td>${posting.company}</td>
            <td>${posting.location}</td>
            <td><a href="${posting.posting_url}" target="_blank">Open posting</a></td>
            <td><select data-url="${posting.posting_url}">${options.join("")}</select></td>
          </tr>
        `;
      }).join("");

      return `
        <table>
          <thead>
            <tr>
              <th>Job title</th>
              <th>Company</th>
              <th>Location</th>
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
        container.innerHTML = "";
        return;
      }

      const visibleSections = sections
        .map(section => ({
          ...section,
          sectionPostings: postings.filter(section.match),
        }))
        .filter(section => section.sectionPostings.length);

      if (!visibleSections.length) {
        container.innerHTML = "";
        return;
      }

      container.innerHTML = visibleSections.map(section => `
          <div class="section">
            <h2>${section.title} <span class="count">(${section.sectionPostings.length})</span></h2>
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
    }

    loadDashboard();
  </script>
</body>
</html>"""
