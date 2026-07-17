"""Windowed entry point for the local internship-search dashboard."""

from __future__ import annotations

import os
import sys
import traceback
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path


def project_root() -> Path:
    """Locate the project containing the ignored private and data folders."""

    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        return executable_dir.parent if executable_dir.name.lower() == "app" else executable_dir
    return Path(__file__).resolve().parents[1]


def dashboard_is_healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/dashboard", timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def show_error(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "Internship Search", 0x10)
    except Exception:
        pass


def main() -> int:
    root = project_root()
    data_dir = root / "data"
    private_dir = root / "private"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "app_launcher.log"
    host = "127.0.0.1"
    port = int(os.environ.get("INTERNSHIP_APP_PORT", "8765"))
    open_browser = os.environ.get("INTERNSHIP_APP_OPEN_BROWSER", "true").lower() != "false"
    url = f"http://{host}:{port}"

    if dashboard_is_healthy(url):
        if open_browser:
            webbrowser.open(url)
        return 0

    if not private_dir.exists():
        message = (
            "The private data folder was not found. Keep the app inside the project's "
            "app folder so it can load your local data."
        )
        show_error(message)
        return 1

    os.chdir(root)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = log
        sys.stderr = log
        print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Starting {url}")
        try:
            from internship_search.review_ui import start_review_ui

            start_review_ui(
                host=host,
                port=port,
                data_dir=data_dir,
                private_dir=private_dir,
                open_browser=open_browser,
            )
        except BaseException as error:
            traceback.print_exc()
            message = (
                "The Internship Search app could not start. Close any older Internship "
                f"Search process and try again. Details are in {log_path}.\n\n{error}"
            )
            show_error(message)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
