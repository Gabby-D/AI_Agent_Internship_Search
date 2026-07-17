"""AI-backed fit scoring providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from internship_search.env_loader import get_env, load_env_into_process
from internship_search.posting_filter import FilteredPosting
from internship_search.private_inputs import PrivateInputs
from internship_search.resume_scoring import ResumeScoringConfig, load_resume_scoring_config

PostJson = Callable[[str, bytes], str]

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class AiUsage:
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: AiUsage) -> AiUsage:
        return AiUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True)
class ParsedFitScore:
    score: int
    fit_level: str
    explanations: list[str]
    gaps: list[str]
    provider: str
    usage: AiUsage


class FitScorer(Protocol):
    name: str

    def score_posting(
        self,
        posting: FilteredPosting,
        private_inputs: PrivateInputs,
        has_connection: bool,
    ) -> ParsedFitScore:
        ...


class LocalRuleBasedScorer:
    name = "local_rule_based"

    def score_posting(
        self,
        posting: FilteredPosting,
        private_inputs: PrivateInputs,
        has_connection: bool,
    ) -> ParsedFitScore:
        from internship_search.fit_scoring import fit_level, score_posting

        scored = score_posting(
            posting=posting,
            private_inputs=private_inputs,
            has_connection=has_connection,
        )
        return ParsedFitScore(
            score=scored.score,
            fit_level=scored.fit_level,
            explanations=list(scored.explanations),
            gaps=list(scored.gaps),
            provider=self.name,
            usage=AiUsage(),
        )


class GeminiFitScorer:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        post_json: PostJson | None = None,
        fallback_scorer: FitScorer | None = None,
        resume_config: ResumeScoringConfig | None = None,
        private_dir: Path | str = "private",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.post_json = post_json or post_json_request
        self.fallback_scorer = fallback_scorer or LocalRuleBasedScorer()
        self.resume_config = resume_config or ResumeScoringConfig(enabled=False, summary=None)
        self.private_dir = Path(private_dir)
        self.usage = AiUsage()

    def score_posting(
        self,
        posting: FilteredPosting,
        private_inputs: PrivateInputs,
        has_connection: bool,
    ) -> ParsedFitScore:
        try:
            parsed = score_posting_with_gemini(
                posting=posting,
                private_inputs=private_inputs,
                has_connection=has_connection,
                api_key=self.api_key,
                model=self.model,
                post_json=self.post_json,
                resume_summary=self.resume_config.summary if self.resume_config.included else None,
                private_dir=self.private_dir,
            )
            self.usage = self.usage.add(parsed.usage)
            return parsed
        except Exception as error:  # noqa: BLE001 - fall back to local scoring per posting.
            fallback = self.fallback_scorer.score_posting(
                posting=posting,
                private_inputs=private_inputs,
                has_connection=has_connection,
            )
            explanations = [
                f"AI scoring unavailable ({error}); used local fallback.",
                *fallback.explanations,
            ]
            return ParsedFitScore(
                score=fallback.score,
                fit_level=fallback.fit_level,
                explanations=explanations,
                gaps=fallback.gaps,
                provider=fallback.provider,
                usage=fallback.usage,
            )


def get_fit_scorer(
    provider_name: str | None = None,
    *,
    private_dir: Path | str = "private",
    resume_aware: bool | None = None,
) -> FitScorer:
    load_env_into_process()
    selected = (provider_name or get_env("AI_PROVIDER", "auto")).lower()
    api_key = get_env("AI_PROVIDER_API_KEY")
    model = get_env("AI_PROVIDER_MODEL", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL
    resume_config = load_resume_scoring_config(private_dir, resume_aware=resume_aware)

    if selected == "local":
        return LocalRuleBasedScorer()
    if selected in {"gemini", "auto"} and api_key:
        return GeminiFitScorer(
            api_key=api_key,
            model=model,
            resume_config=resume_config,
            private_dir=private_dir,
        )
    if selected == "gemini" and not api_key:
        raise ValueError("AI_PROVIDER_API_KEY is required when AI_PROVIDER=gemini.")
    return LocalRuleBasedScorer()


def score_posting_with_gemini(
    posting: FilteredPosting,
    private_inputs: PrivateInputs,
    has_connection: bool,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    post_json: PostJson | None = None,
    resume_summary: str | None = None,
    private_dir: Path | str = "private",
) -> ParsedFitScore:
    prompt = build_scoring_prompt(
        posting=posting,
        profile_context=build_profile_context(
            private_inputs=private_inputs,
            has_connection=has_connection,
            resume_summary=resume_summary,
        ),
    )
    
    parts: list[dict[str, object]] = [{"text": prompt}]
    
    attachments_dir = Path(private_dir) / "attachments"
    if attachments_dir.exists():
        import base64
        import mimetypes
        for file_path in sorted(attachments_dir.iterdir()):
            if file_path.is_file():
                suffix = file_path.suffix.lower()
                if suffix in {".txt", ".md"}:
                    try:
                        text_content = file_path.read_text(encoding="utf-8")
                        parts.append({"text": f"\nAttachment ({file_path.name}):\n{text_content}\n"})
                    except Exception:
                        pass
                elif suffix in {".pdf", ".png", ".jpg", ".jpeg", ".gif"}:
                    try:
                        mime_type, _ = mimetypes.guess_type(file_path.name)
                        if not mime_type:
                            mime_type = "application/octet-stream"
                        file_bytes = file_path.read_bytes()
                        b64_data = base64.b64encode(file_bytes).decode("utf-8")
                        parts.append({
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data
                            }
                        })
                    except Exception:
                        pass

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }
    request_body = json.dumps(payload).encode("utf-8")
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"
    raw = (post_json or post_json_request)(url, request_body)
    return parse_gemini_scoring_response(raw)


def build_profile_context(
    private_inputs: PrivateInputs,
    has_connection: bool,
    resume_summary: str | None = None,
) -> dict[str, object]:
    context: dict[str, object] = {
        "program": {
            "faculty": private_inputs.program.faculty,
            "major": private_inputs.program.major,
            "minor_or_concentration": private_inputs.program.minor_or_concentration,
        },
        "courses": [
            {"code": course.code, "title": course.title, "category": course.category}
            for course in private_inputs.courses
        ],
        "industries": private_inputs.industries,
        "likes": private_inputs.preferences.likes,
        "dislikes": private_inputs.preferences.dislikes,
        "has_connection": has_connection,
        "resume_included": bool(resume_summary),
    }
    if resume_summary:
        context["resume_summary"] = resume_summary
    return context


def build_scoring_prompt(
    posting: FilteredPosting,
    profile_context: dict[str, object],
) -> str:
    posting_context = {
        "title": posting.title,
        "company": posting.company,
        "location": posting.location,
        "posting_url": posting.posting_url,
        "filter_reasons": posting.reasons,
    }
    instructions = (
        "Score this internship posting for fit against the student profile and any attached reference documents (such as uploaded resumes, transcripts, or notes).\n"
        "Return JSON only with keys: score (0-100 integer), fit_level "
        '("strong", "medium", or "weak"), explanations (string array), gaps (string array).\n'
        "Apply the user's private profile preferences and industries without adding assumptions.\n"
        "Do not invent facts not supported by the posting, profile, or attachments.\n"
    )
    if profile_context.get("resume_included"):
        instructions += (
            "Resume summary is included. Reference relevant resume skills or experience "
            "in explanations when they support the fit assessment.\n"
        )
    return (
        f"{instructions}\n"
        f"Profile:\n{json.dumps(profile_context, indent=2, sort_keys=True)}\n\n"
        f"Posting:\n{json.dumps(posting_context, indent=2, sort_keys=True)}"
    )


def parse_gemini_scoring_response(raw: str) -> ParsedFitScore:
    payload = json.loads(raw)
    usage = parse_gemini_usage(payload)
    text = extract_gemini_text(payload)
    parsed = json.loads(text)
    score = int(parsed["score"])
    fit_level = str(parsed["fit_level"]).strip().lower()
    explanations = [str(item) for item in parsed.get("explanations", [])]
    gaps = [str(item) for item in parsed.get("gaps", [])]

    if score < 0 or score > 100:
        raise ValueError(f"Gemini score out of range: {score}")
    if fit_level not in {"strong", "medium", "weak"}:
        fit_level = fit_level_from_score(score)

    if not explanations:
        explanations.append("AI scoring completed with limited explanation detail.")

    return ParsedFitScore(
        score=score,
        fit_level=fit_level,
        explanations=explanations,
        gaps=gaps,
        provider="gemini",
        usage=usage,
    )


def parse_gemini_usage(payload: dict[str, object]) -> AiUsage:
    usage = payload.get("usageMetadata", {})
    if not isinstance(usage, dict):
        return AiUsage()
    return AiUsage(
        prompt_tokens=int(usage.get("promptTokenCount", 0) or 0),
        output_tokens=int(usage.get("candidatesTokenCount", 0) or 0),
        total_tokens=int(usage.get("totalTokenCount", 0) or 0),
    )


def extract_gemini_text(payload: dict[str, object]) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini response did not include candidates.")
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        raise ValueError("Gemini response did not include content parts.")
    text = parts[0].get("text", "")
    if not text:
        raise ValueError("Gemini response text was empty.")
    return str(text)


def fit_level_from_score(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 50:
        return "medium"
    return "weak"


def post_json_request(url: str, body: bytes) -> str:
    from internship_search.retry import retry_call

    return retry_call(lambda: _post_json_request_once(url, body))


def _post_json_request_once(url: str, body: bytes) -> str:
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Gemini API request failed: {error.reason}") from error


def summarize_ai_usage(usage: AiUsage, model: str = DEFAULT_GEMINI_MODEL) -> str:
    if usage.total_tokens == 0:
        return ""
    return (
        "API usage summary\n"
        f"- Model: {model}\n"
        f"- Input tokens: {usage.prompt_tokens}\n"
        f"- Output tokens: {usage.output_tokens}\n"
        f"- Total tokens: {usage.total_tokens}\n"
        "- Estimated cost: likely free tier for this run"
    )
