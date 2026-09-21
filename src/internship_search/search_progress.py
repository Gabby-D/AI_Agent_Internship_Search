"""Persist live search progress for the dashboard to poll."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from internship_search.paths import default_data_dir

PROGRESS_FILENAME = "search_progress.json"
STALE_AFTER_SECONDS = 2 * 60 * 60
COLLECT_START_PERCENT = 5
COLLECT_END_PERCENT = 86
JOB_BOARDS_LABEL = "job boards"


@dataclass(frozen=True)
class SearchProgress:
    state: str
    percent: int
    message: str
    current: int = 0
    total: int = 0
    phase: str = ""
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""

    def is_running(self) -> bool:
        if self.state != "running":
            return False
        if not self.updated_at:
            return True
        try:
            updated = datetime.fromisoformat(self.updated_at)
        except ValueError:
            return True
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds()
        return age < STALE_AFTER_SECONDS


def search_progress_path(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir or default_data_dir()) / PROGRESS_FILENAME


def collect_percent(current: int, total: int) -> int:
    """Map company index (1-based, about to search) onto the collect phase band."""

    if total <= 0:
        return COLLECT_START_PERCENT
    ratio = max(0, current - 1) / total
    span = COLLECT_END_PERCENT - COLLECT_START_PERCENT
    return COLLECT_START_PERCENT + int(span * ratio)


def write_search_progress(
    data_dir: Path | str,
    *,
    state: str,
    percent: int,
    message: str,
    current: int = 0,
    total: int = 0,
    phase: str = "",
    started_at: str = "",
    finished_at: str = "",
) -> Path:
    path = search_progress_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    existing = read_search_progress(data_dir, include_stale=True)
    payload = {
        "state": state,
        "percent": max(0, min(100, int(percent))),
        "message": message,
        "current": int(current),
        "total": int(total),
        "phase": phase,
        "started_at": started_at or (existing.started_at if existing else now),
        "updated_at": now,
        "finished_at": finished_at,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_search_progress(
    data_dir: Path | str | None = None,
    *,
    include_stale: bool = False,
) -> SearchProgress | None:
    path = search_progress_path(data_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        percent = int(float(payload.get("percent") or 0))
        current = int(float(payload.get("current") or 0))
        total = int(float(payload.get("total") or 0))
    except (TypeError, ValueError):
        return None
    progress = SearchProgress(
        state=str(payload.get("state") or ""),
        percent=percent,
        message=str(payload.get("message") or ""),
        current=current,
        total=total,
        phase=str(payload.get("phase") or ""),
        started_at=str(payload.get("started_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
        finished_at=str(payload.get("finished_at") or ""),
    )
    if include_stale:
        return progress
    if progress.state == "paused":
        return progress
    if progress.state == "running" and not progress.is_running():
        return None
    return progress
