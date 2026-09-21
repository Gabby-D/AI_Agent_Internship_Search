from datetime import datetime, timedelta, timezone
import json

from internship_search.search_progress import (
    COLLECT_END_PERCENT,
    COLLECT_START_PERCENT,
    collect_percent,
    read_search_progress,
    write_search_progress,
)


def test_write_and_read_search_progress(tmp_path):
    path = write_search_progress(
        tmp_path,
        state="running",
        percent=37,
        message="Searching BlackRock (12 of 141)",
        current=12,
        total=141,
        phase="collect",
    )

    progress = read_search_progress(tmp_path)
    assert path.name == "search_progress.json"
    assert progress is not None
    assert progress.state == "running"
    assert progress.percent == 37
    assert progress.current == 12
    assert progress.total == 141
    assert progress.is_running()


def test_read_search_progress_ignores_stale_running_state(tmp_path):
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    (tmp_path / "search_progress.json").write_text(
        json.dumps(
            {
                "state": "running",
                "percent": 40,
                "message": "Searching Example (1 of 10)",
                "current": 1,
                "total": 10,
                "phase": "collect",
                "started_at": stale_time,
                "updated_at": stale_time,
                "finished_at": "",
            }
        ),
        encoding="utf-8",
    )

    assert read_search_progress(tmp_path) is None
    stale = read_search_progress(tmp_path, include_stale=True)
    assert stale is not None
    assert stale.state == "running"
    assert stale.is_running() is False


def test_collect_percent_spans_company_search_band():
    assert collect_percent(1, 100) == COLLECT_START_PERCENT
    assert collect_percent(100, 100) < COLLECT_END_PERCENT
    assert collect_percent(100, 100) > COLLECT_START_PERCENT
    assert collect_percent(1, 0) == COLLECT_START_PERCENT
