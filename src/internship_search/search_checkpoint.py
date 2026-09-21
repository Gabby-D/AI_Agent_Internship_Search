"""Checkpoint a search so it can pause across shutdown and resume later."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from internship_search.paths import default_data_dir

CHECKPOINT_FILENAME = "search_checkpoint.json"
PARTIAL_POSTINGS_FILENAME = "search_collect_partial.jsonl"
PARTIAL_ERRORS_FILENAME = "search_collect_errors.jsonl"
LOCK_FILENAME = "search_run.lock"
JOB_BOARDS_CHECKPOINT_KEY = "__job_boards__"

_pause_event = threading.Event()
_shutdown_handler_installed = False
_ctrl_handlers: list[object] = []


class SearchPaused(Exception):
    """Raised when a search should stop and resume after the computer is back on."""


class SearchRunLock:
    """Process-wide exclusive lock so dashboard and scheduled runs do not overlap."""

    def __init__(self, data_dir: Path | str) -> None:
        self.path = Path(data_dir) / LOCK_FILENAME
        self._handle: Any = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            handle.close()

    def __enter__(self) -> SearchRunLock:
        if not self.acquire():
            raise RuntimeError("A search is already running.")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass(frozen=True)
class SearchCheckpoint:
    status: str
    started_at: str
    collected_on: str
    include_job_boards: bool
    generate_email: bool
    send_email: bool
    resume_aware: bool | None
    target_year: str
    completed_source_keys: tuple[str, ...]
    job_boards_done: bool
    collect_done: bool
    percent: int = 0
    message: str = ""
    current: int = 0
    total: int = 0
    phase: str = ""

    def is_incomplete(self) -> bool:
        return self.status in {"running", "paused"}


def search_checkpoint_path(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or default_data_dir()) / CHECKPOINT_FILENAME


def partial_postings_path(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or default_data_dir()) / PARTIAL_POSTINGS_FILENAME


def partial_errors_path(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or default_data_dir()) / PARTIAL_ERRORS_FILENAME


def request_search_pause() -> None:
    _pause_event.set()


def clear_search_pause() -> None:
    _pause_event.clear()


def search_pause_requested() -> bool:
    return _pause_event.is_set()


def raise_if_search_paused() -> None:
    if search_pause_requested():
        raise SearchPaused()


def install_search_pause_on_shutdown() -> None:
    """Stop the current company loop when Windows shuts down or the process is asked to exit."""

    global _shutdown_handler_installed
    if _shutdown_handler_installed:
        return
    _shutdown_handler_installed = True

    if sys.platform == "win32":
        import ctypes

        handler_routine = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong)

        def handle(ctrl_type: int) -> int:
            if ctrl_type in {2, 5, 6}:
                request_search_pause()
                return 1
            return 0

        callback = handler_routine(handle)
        _ctrl_handlers.append(callback)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, True)
        return

    import signal

    def handle(signum, frame) -> None:  # noqa: ARG001
        request_search_pause()

    signal.signal(signal.SIGTERM, handle)


def source_checkpoint_key(source: object) -> str:
    company = str(getattr(source, "company", "") or "").strip().lower()
    careers_url = str(getattr(source, "careers_url", "") or "").strip().lower()
    if company and careers_url:
        return f"{company}|{careers_url}"
    return careers_url or company


def write_search_checkpoint(
    data_dir: Path | str,
    checkpoint: SearchCheckpoint,
) -> Path:
    path = search_checkpoint_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": checkpoint.status,
        "started_at": checkpoint.started_at,
        "collected_on": checkpoint.collected_on,
        "include_job_boards": checkpoint.include_job_boards,
        "generate_email": checkpoint.generate_email,
        "send_email": checkpoint.send_email,
        "resume_aware": checkpoint.resume_aware,
        "target_year": checkpoint.target_year,
        "completed_source_keys": list(checkpoint.completed_source_keys),
        "job_boards_done": checkpoint.job_boards_done,
        "collect_done": checkpoint.collect_done,
        "percent": checkpoint.percent,
        "message": checkpoint.message,
        "current": checkpoint.current,
        "total": checkpoint.total,
        "phase": checkpoint.phase,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_search_checkpoint(data_dir: Path | str | None = None) -> SearchCheckpoint | None:
    path = search_checkpoint_path(data_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    keys = payload.get("completed_source_keys") or []
    if not isinstance(keys, list):
        keys = []
    resume_aware = payload.get("resume_aware", None)
    if resume_aware is not None:
        resume_aware = bool(resume_aware)
    try:
        percent = int(float(payload.get("percent") or 0))
        current = int(float(payload.get("current") or 0))
        total = int(float(payload.get("total") or 0))
    except (TypeError, ValueError):
        percent = 0
        current = 0
        total = 0
    return SearchCheckpoint(
        status=str(payload.get("status") or ""),
        started_at=str(payload.get("started_at") or ""),
        collected_on=str(payload.get("collected_on") or date.today().isoformat()),
        include_job_boards=bool(payload.get("include_job_boards")),
        generate_email=bool(payload.get("generate_email")),
        send_email=bool(payload.get("send_email")),
        resume_aware=resume_aware,
        target_year=str(payload.get("target_year") or "2027"),
        completed_source_keys=tuple(str(key) for key in keys),
        job_boards_done=bool(payload.get("job_boards_done")),
        collect_done=bool(payload.get("collect_done")),
        percent=percent,
        message=str(payload.get("message") or ""),
        current=current,
        total=total,
        phase=str(payload.get("phase") or ""),
    )


def mark_search_paused(data_dir: Path | str) -> SearchCheckpoint | None:
    existing = read_search_checkpoint(data_dir)
    if existing is None or not existing.is_incomplete():
        return existing
    paused = replace(
        existing,
        status="paused",
        message="Paused. Search will resume when this computer is back on.",
    )
    write_search_checkpoint(data_dir, paused)
    return paused


def checkpoint_is_incomplete(data_dir: Path | str | None = None) -> bool:
    checkpoint = read_search_checkpoint(data_dir)
    return bool(checkpoint and checkpoint.is_incomplete())


def clear_partial_collection_files(data_dir: Path | str) -> None:
    for path in (partial_postings_path(data_dir), partial_errors_path(data_dir)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
