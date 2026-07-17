import json

import pytest

from internship_search.ai_scoring import (
    AiUsage,
    GeminiFitScorer,
    LocalRuleBasedScorer,
    build_profile_context,
    build_scoring_prompt,
    get_fit_scorer,
    parse_gemini_scoring_response,
    post_json_request,
    score_posting_with_gemini,
)
from internship_search.fit_scoring import score_postings
from internship_search.posting_filter import FilteredPosting
from internship_search.private_inputs import (
    Course,
    Preferences,
    PrivateInputs,
    ProgramInfo,
)
from internship_search.source_registry import CompanySource


def make_private_inputs() -> PrivateInputs:
    return PrivateInputs(
        companies=[],
        industries=["finance", "operations"],
        preferences=Preferences(
            likes=["Preferred location", "Preferred work arrangement"],
            dislikes=["marketing"],
        ),
        program=ProgramInfo(
            faculty="Desautels Faculty of Management",
            major="Mathematics and Statistics for Management",
            minor_or_concentration="Operations Management",
        ),
        courses=[
            Course(code="MGCR 233", title="Data Programming for Business", category="Core"),
            Course(code="MGSC 373", title="Operations Research", category="Analytics"),
        ],
        connections_notes="",
        resume_path=None,
    )


def make_posting(
    title: str = "2027 Summer Analyst Intern",
    company: str = "Connected Co",
) -> FilteredPosting:
    return FilteredPosting(
        title=title,
        company=company,
        location="Remote",
        posting_url="https://example.com/jobs/2027-summer-analyst-intern",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        included=True,
        reasons=["Mentions internship terms: intern."],
    )


def make_source(company: str = "Connected Co", has_connection: bool = True) -> CompanySource:
    return CompanySource(
        company=company,
        website="https://example.com",
        careers_url="https://example.com/careers",
        source_type="company_careers_page",
        origin="seed",
        has_connection=has_connection,
        notes="Test source",
    )


SAMPLE_GEMINI_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "score": 82,
                                    "fit_level": "strong",
                                    "explanations": [
                                        "Strong match for analytics and finance internship."
                                    ],
                                    "gaps": ["Location is remote only."],
                                }
                            )
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 210,
            "candidatesTokenCount": 48,
            "totalTokenCount": 258,
        },
    }
)


def test_build_profile_context_excludes_resume():
    context = build_profile_context(make_private_inputs(), has_connection=True)

    assert context["resume_included"] is False
    assert "courses" in context
    assert "major" in context["program"]


def test_build_scoring_prompt_includes_posting_and_profile():
    prompt = build_scoring_prompt(
        posting=make_posting(),
        profile_context=build_profile_context(make_private_inputs(), has_connection=True),
    )

    assert "2027 Summer Analyst Intern" in prompt
    assert '"resume_included": false' in prompt


def test_parse_gemini_scoring_response_extracts_fields():
    parsed = parse_gemini_scoring_response(SAMPLE_GEMINI_RESPONSE)

    assert parsed.score == 82
    assert parsed.fit_level == "strong"
    assert parsed.provider == "gemini"
    assert parsed.usage.total_tokens == 258


def test_gemini_scorer_uses_mock_api():
    def mock_post(url: str, body: bytes) -> str:
        assert "generateContent" in url
        payload = json.loads(body.decode("utf-8"))
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        return SAMPLE_GEMINI_RESPONSE

    scorer = GeminiFitScorer(api_key="test-key", post_json=mock_post)
    parsed = scorer.score_posting(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
    )

    assert parsed.score == 82
    assert parsed.provider == "gemini"
    assert scorer.usage.total_tokens == 258


def test_gemini_scorer_falls_back_on_api_error():
    def broken_post(url: str, body: bytes) -> str:
        raise RuntimeError("provider unavailable")

    scorer = GeminiFitScorer(api_key="test-key", post_json=broken_post)
    parsed = scorer.score_posting(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
    )

    assert parsed.provider == "local_rule_based"
    assert any("AI scoring unavailable" in item for item in parsed.explanations)


def test_get_fit_scorer_defaults_to_local_without_api_key(monkeypatch):
    monkeypatch.setattr(
        "internship_search.ai_scoring.load_env_into_process",
        lambda path=".env": {},
    )
    monkeypatch.delenv("AI_PROVIDER_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "auto")

    scorer = get_fit_scorer()

    assert scorer.name == "local_rule_based"


def test_get_fit_scorer_requires_api_key_for_gemini(monkeypatch):
    monkeypatch.setattr(
        "internship_search.ai_scoring.load_env_into_process",
        lambda path=".env": {},
    )
    monkeypatch.delenv("AI_PROVIDER_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "gemini")

    with pytest.raises(ValueError, match="AI_PROVIDER_API_KEY"):
        get_fit_scorer("gemini")


def test_score_postings_with_local_provider(tmp_path):
    result = score_postings(
        postings=[make_posting()],
        private_inputs=make_private_inputs(),
        sources=[make_source()],
        output_path=tmp_path / "scored.jsonl",
        provider_name="local",
    )

    assert result.provider == "local_rule_based"
    assert result.scored_postings[0].provider == "local_rule_based"
    assert result.output_path.exists()


def test_score_posting_with_gemini_mock():
    def mock_post(url: str, body: bytes) -> str:
        return SAMPLE_GEMINI_RESPONSE

    parsed = score_posting_with_gemini(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
        api_key="test-key",
        post_json=mock_post,
    )

    assert parsed.score == 82
    assert isinstance(parsed.usage, AiUsage)


def test_post_json_request_retries_transient_http_errors(monkeypatch):
    attempts = {"count": 0}

    def flaky_once(url: str, body: bytes) -> str:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("Gemini API HTTP 503: unavailable")
        return SAMPLE_GEMINI_RESPONSE

    monkeypatch.setattr(
        "internship_search.ai_scoring._post_json_request_once",
        flaky_once,
    )

    raw = post_json_request("https://example.test", b"{}")
    parsed = parse_gemini_scoring_response(raw)

    assert attempts["count"] == 2
    assert parsed.score == 82


def test_score_posting_with_gemini_attachments(tmp_path):
    import base64
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir()
    
    # Write one text file
    (attachments_dir / "skills.txt").write_text("Python, Pytest", encoding="utf-8")
    # Write one dummy PDF
    (attachments_dir / "resume.pdf").write_bytes(b"pdf data")
    
    posted_payload = []
    def mock_post(url: str, body: bytes) -> str:
        posted_payload.append(json.loads(body.decode("utf-8")))
        return SAMPLE_GEMINI_RESPONSE
        
    parsed = score_posting_with_gemini(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
        api_key="test-key",
        post_json=mock_post,
        private_dir=tmp_path
    )
    
    assert parsed.score == 82
    assert len(posted_payload) == 1
    parts = posted_payload[0]["contents"][0]["parts"]
    
    # Check that text and inline data parts exist
    assert any("Attachment (skills.txt)" in p.get("text", "") for p in parts)
    
    inline_parts = [p for p in parts if "inline_data" in p]
    assert len(inline_parts) == 1
    assert inline_parts[0]["inline_data"]["mime_type"] == "application/pdf"
    assert inline_parts[0]["inline_data"]["data"] == base64.b64encode(b"pdf data").decode("utf-8")
