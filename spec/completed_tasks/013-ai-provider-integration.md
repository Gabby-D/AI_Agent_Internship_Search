# Completed Task: AI Provider Integration

## Completed Outcome

Connected fit scoring to Google Gemini while preserving the existing local rule-based scorer for offline use, tests, and fallback.

## Implemented Files

- `src/internship_search/ai_scoring.py`
- `src/internship_search/fit_scoring.py`
- `src/internship_search/cli.py`
- `tests/test_ai_scoring.py`
- `tests/test_fit_scoring.py`

## Generated Local Output

- `data/scored_postings.jsonl`

## Behavior

- Uses Gemini when `AI_PROVIDER_API_KEY` is set and `AI_PROVIDER=auto` (default).
- Falls back to `local_rule_based` scoring when Gemini is unavailable or a request fails.
- Sends only minimal profile context: program, courses, industries, preferences, and connection status.
- Does not send resume text.
- Returns the same scored output shape: score, fit level, explanations, gaps, and provider.
- Reports token usage in the CLI summary when Gemini is used.

## Environment Variables

- `AI_PROVIDER_API_KEY` - Gemini API key.
- `AI_PROVIDER` - `auto` (default), `local`, or `gemini`.
- `AI_PROVIDER_MODEL` - defaults to `gemini-2.5-flash`.

## CLI

Score with the default provider (`auto`):

```powershell
uv run internship-search score-postings
```

Force local scoring:

```powershell
uv run internship-search score-postings --provider local
```

Force Gemini:

```powershell
uv run internship-search score-postings --provider gemini
```

## Verification

```powershell
uv run pytest
```

Result: `64 passed`, including mocked Gemini provider tests.

## Latest Local Run

- Provider: `gemini`
- Scored postings: 4
- Model: `gemini-2.5-flash`
- Total tokens: 12040
- Output: `data/scored_postings.jsonl`

## Notes

The scoring interface is provider-agnostic. Additional providers such as OpenAI or Claude can be added behind the same `FitScorer` interface later.
