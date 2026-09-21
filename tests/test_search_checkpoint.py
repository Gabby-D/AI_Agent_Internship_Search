from internship_search.search_checkpoint import (
    SearchCheckpoint,
    SearchRunLock,
    checkpoint_is_incomplete,
    read_search_checkpoint,
    write_search_checkpoint,
)


def test_write_and_read_search_checkpoint(tmp_path):
    original = SearchCheckpoint(
        status="paused",
        started_at="2026-07-23T10:00:00+00:00",
        collected_on="2026-07-23",
        include_job_boards=False,
        generate_email=False,
        send_email=False,
        resume_aware=None,
        target_year="2027",
        completed_source_keys=("alpha|https://alpha.example/careers/",),
        job_boards_done=False,
        collect_done=False,
        percent=41,
        message="Paused. Search will resume when this computer is back on.",
        current=12,
        total=30,
        phase="collect",
    )
    write_search_checkpoint(tmp_path, original)
    loaded = read_search_checkpoint(tmp_path)
    assert loaded == original
    assert checkpoint_is_incomplete(tmp_path)


def test_search_run_lock_is_exclusive(tmp_path):
    first = SearchRunLock(tmp_path)
    second = SearchRunLock(tmp_path)
    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()
    assert second.acquire() is True
    second.release()
