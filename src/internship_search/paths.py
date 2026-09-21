"""Locations of gitignored runtime files.

Personal inputs, generated data, and `.env` live on Google Drive so they sync
across machines. The git repository only keeps README placeholders under
`private/` and `data/`.
"""

from __future__ import annotations

from pathlib import Path

EXTERNAL_FILES_ROOT = Path(r"G:\My Drive\none_git_files\AI_Agent_Internship_Search")


def default_files_root() -> Path:
    return EXTERNAL_FILES_ROOT


def default_private_dir() -> Path:
    return default_files_root() / "private"


def default_data_dir() -> Path:
    return default_files_root() / "data"


def default_env_file() -> Path:
    return default_files_root() / ".env"


def default_data_file(name: str) -> Path:
    return default_data_dir() / name
