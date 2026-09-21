from pathlib import Path

from internship_search.cli import build_parser
from internship_search.env_loader import load_env_file
from internship_search.location_filter import DEFAULT_LOCATION_PREFERENCES_PATH
from internship_search.paths import (
    EXTERNAL_FILES_ROOT,
    default_data_dir,
    default_data_file,
    default_env_file,
    default_private_dir,
)


def test_external_files_root_is_google_drive_project_folder():
    assert EXTERNAL_FILES_ROOT == Path(
        r"G:\My Drive\none_git_files\AI_Agent_Internship_Search"
    )
    assert default_private_dir() == EXTERNAL_FILES_ROOT / "private"
    assert default_data_dir() == EXTERNAL_FILES_ROOT / "data"
    assert default_env_file() == EXTERNAL_FILES_ROOT / ".env"
    assert default_data_file("postings.jsonl") == EXTERNAL_FILES_ROOT / "data" / "postings.jsonl"
    assert DEFAULT_LOCATION_PREFERENCES_PATH == default_private_dir() / "location_preferences.txt"


def test_cli_defaults_use_google_drive_runtime_files():
    parser = build_parser()
    review = parser.parse_args(["review-ui"])
    scheduled = parser.parse_args(["run-scheduled-collection"])

    assert review.private_dir == default_private_dir()
    assert review.data_dir == default_data_dir()
    assert scheduled.private_dir == default_private_dir()
    assert scheduled.data_dir == default_data_dir()


def test_env_loader_reads_an_explicit_path(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("EXAMPLE_KEY=value\n", encoding="utf-8")

    assert load_env_file(env_path) == {"EXAMPLE_KEY": "value"}
