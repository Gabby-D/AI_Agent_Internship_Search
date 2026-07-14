"""Optional resume-aware scoring configuration and resume summary loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from internship_search.env_loader import get_env

RESUME_SUMMARY_FILENAMES = (
    "resume_summary.md",
    "resume.md",
    "resume.txt",
)
DEFAULT_RESUME_SUMMARY_MAX_CHARS = 4000
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ResumeScoringConfig:
    enabled: bool
    summary: str | None
    source_path: Path | None = None

    @property
    def included(self) -> bool:
        return self.enabled and bool(self.summary)


def resolve_resume_scoring_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return override
    value = (get_env("AI_RESUME_SCORING_ENABLED", "false") or "false").strip().lower()
    return value in TRUTHY_ENV_VALUES


def load_resume_scoring_config(
    private_dir: Path | str = "private",
    *,
    resume_aware: bool | None = None,
) -> ResumeScoringConfig:
    enabled = resolve_resume_scoring_enabled(resume_aware)
    if not enabled:
        return ResumeScoringConfig(enabled=False, summary=None, source_path=None)

    summary, source_path = load_resume_summary(private_dir)
    return ResumeScoringConfig(
        enabled=True,
        summary=summary,
        source_path=source_path,
    )


def load_resume_summary(
    private_dir: Path | str = "private",
    *,
    max_chars: int = DEFAULT_RESUME_SUMMARY_MAX_CHARS,
) -> tuple[str | None, Path | None]:
    private_path = Path(private_dir)
    for filename in RESUME_SUMMARY_FILENAMES:
        path = private_path / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        return truncate_resume_summary(text, max_chars=max_chars), path
    return None, None


def truncate_resume_summary(text: str, *, max_chars: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars].rsplit("\n", 1)[0].strip()
    return f"{truncated}\n[truncated]"


def summarize_resume_scoring_config(config: ResumeScoringConfig) -> str:
    if not config.enabled:
        return "Resume-aware scoring: disabled."
    if not config.summary:
        return (
            "Resume-aware scoring: enabled, but no resume summary file was found. "
            "Add private/resume_summary.md to include resume context."
        )
    source = config.source_path.name if config.source_path else "resume summary"
    return f"Resume-aware scoring: enabled using {source}."
