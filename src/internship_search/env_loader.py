"""Load local environment variables from ignored files."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path | str = ".env") -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env_into_process(path: Path | str = ".env") -> dict[str, str]:
    values = load_env_file(path)
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()
