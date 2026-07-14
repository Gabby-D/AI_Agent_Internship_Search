from pathlib import Path

import json
import pytest

from internship_search.ai_scoring import (
    GeminiFitScorer,
    build_profile_context,
    build_scoring_prompt,
    get_fit_scorer,
    score_posting_with_gemini,
)
from internship_search.resume_scoring import (
    load_resume_scoring_config,
    load_resume_summary,
    resolve_resume_scoring_enabled,
    truncate_resume_summary,
)
from internship_search.posting_filter import FilteredPosting
from internship_search.private_inputs import (
    Course,
    Preferences,
    PrivateInputs,
    ProgramInfo,
)


def make_private_inputs() -> PrivateInputs:
    return PrivateInputs(
        companies=[],
        industries=["finance"],
        preferences=Preferences(likes=["Paid position"], dislikes=["marketing"]),
        program=ProgramInfo(
            faculty="Desautels Faculty of Management",
            major="Mathematics and Statistics for Management",
            minor_or_concentration="Operations Management",
        ),
        courses=[
            Course(code="MGCR 233", title="Data Programming for Business", category="Core"),
        ],
        connections_notes="",
        resume_path=Path("private/Resume - Gabrielle Dar.pdf"),
    )


def make_posting() -> FilteredPosting:
    return FilteredPosting(
        title="2027 Summer Analyst Intern",
        company="Connected Co",
        location="Remote",
        posting_url="https://example.com/jobs/2027-summer-analyst-intern",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        included=True,
        reasons=["Listing type: Specific internship listing."],
    )


def test_resolve_resume_scoring_enabled_defaults_to_false(monkeypatch):
    monkeypatch.delenv("AI_RESUME_SCORING_ENABLED", raising=False)

    assert resolve_resume_scoring_enabled() is False


def test_resolve_resume_scoring_enabled_honors_env_flag(monkeypatch):
    monkeypatch.setenv("AI_RESUME_SCORING_ENABLED", "true")

    assert resolve_resume_scoring_enabled() is True


def test_resolve_resume_scoring_enabled_cli_override_beats_env(monkeypatch):
    monkeypatch.setenv("AI_RESUME_SCORING_ENABLED", "true")

    assert resolve_resume_scoring_enabled(False) is False


def test_load_resume_summary_prefers_resume_summary_md(tmp_path):
    (tmp_path / "resume.md").write_text("older resume", encoding="utf-8")
    (tmp_path / "resume_summary.md").write_text(
        "- Python and SQL experience\n- Operations research projects",
        encoding="utf-8",
    )

    summary, source_path = load_resume_summary(tmp_path)

    assert summary is not None
    assert "Python and SQL" in summary
    assert source_path == tmp_path / "resume_summary.md"


def test_load_resume_scoring_config_disabled_does_not_load_summary(tmp_path):
    (tmp_path / "resume_summary.md").write_text("Should not load", encoding="utf-8")

    config = load_resume_scoring_config(tmp_path, resume_aware=False)

    assert config.enabled is False
    assert config.summary is None


def test_build_profile_context_includes_resume_only_when_summary_provided():
    context = build_profile_context(
        make_private_inputs(),
        has_connection=True,
        resume_summary="- Built finance dashboards in Python",
    )

    assert context["resume_included"] is True
    assert "resume_summary" in context


def test_build_scoring_prompt_excludes_resume_by_default():
    prompt = build_scoring_prompt(
        posting=make_posting(),
        profile_context=build_profile_context(make_private_inputs(), has_connection=True),
    )

    assert '"resume_included": false' in prompt
    assert "resume_summary" not in prompt


def test_build_scoring_prompt_includes_resume_when_opted_in():
    prompt = build_scoring_prompt(
        posting=make_posting(),
        profile_context=build_profile_context(
            make_private_inputs(),
            has_connection=True,
            resume_summary="- Built finance dashboards in Python",
        ),
    )

    assert '"resume_included": true' in prompt
    assert "finance dashboards in Python" in prompt
    assert "Reference relevant resume skills" in prompt


def test_gemini_scorer_does_not_send_resume_without_opt_in():
    captured: dict[str, bytes] = {}

    def mock_post(url: str, body: bytes) -> str:
        captured["body"] = body
        return (
            '{"candidates":[{"content":{"parts":[{"text":"{\\"score\\": 70, \\"fit_level\\": \\"medium\\", '
            '\\"explanations\\": [\\"Good fit.\\"], \\"gaps\\": []}"}]}}]}'
        )

    scorer = GeminiFitScorer(api_key="test-key", post_json=mock_post)
    scorer.score_posting(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
    )

    payload = json.loads(captured["body"].decode("utf-8"))
    prompt = payload["contents"][0]["parts"][0]["text"]
    assert "resume_summary" not in prompt
    assert '"resume_included": false' in prompt


def test_gemini_scorer_sends_resume_summary_when_opted_in():
    captured: dict[str, bytes] = {}

    def mock_post(url: str, body: bytes) -> str:
        captured["body"] = body
        return (
            '{"candidates":[{"content":{"parts":[{"text":"{\\"score\\": 88, \\"fit_level\\": \\"strong\\", '
            '\\"explanations\\": [\\"Resume Python experience aligns with analytics internship.\\"], '
            '\\"gaps\\": []}"}]}}],'
            '"usageMetadata":{"promptTokenCount":10,"candidatesTokenCount":5,"totalTokenCount":15}}'
        )

    from internship_search.resume_scoring import ResumeScoringConfig

    scorer = GeminiFitScorer(
        api_key="test-key",
        post_json=mock_post,
        resume_config=ResumeScoringConfig(
            enabled=True,
            summary="- Python and SQL experience",
            source_path=Path("private/resume_summary.md"),
        ),
    )
    parsed = scorer.score_posting(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
    )

    payload = json.loads(captured["body"].decode("utf-8"))
    prompt = payload["contents"][0]["parts"][0]["text"]
    assert "Python and SQL experience" in prompt
    assert '"resume_included": true' in prompt
    assert any("Resume Python" in item for item in parsed.explanations)


def test_get_fit_scorer_does_not_include_resume_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "internship_search.ai_scoring.load_env_into_process",
        lambda path=".env": {},
    )
    monkeypatch.delenv("AI_RESUME_SCORING_ENABLED", raising=False)
    monkeypatch.setenv("AI_PROVIDER_API_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    (tmp_path / "resume_summary.md").write_text("secret resume content", encoding="utf-8")

    scorer = get_fit_scorer("gemini", private_dir=tmp_path, resume_aware=False)

    assert scorer.resume_config.included is False


def test_truncate_resume_summary_limits_length():
    long_text = "\n".join(f"Line {index}" for index in range(200))

    truncated = truncate_resume_summary(long_text, max_chars=100)

    assert len(truncated) <= 120
    assert truncated.endswith("[truncated]")
