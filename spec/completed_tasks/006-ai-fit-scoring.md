# Completed Task: AI Fit Scoring

## Completed Outcome

Implemented a modular fit-scoring tool for filtered postings. The current implementation uses a local rule-based provider so it can run without external API keys, while keeping the interface ready for a future AI provider.

## Implemented Files

- `src/internship_search/fit_scoring.py`
- `src/internship_search/cli.py`
- `tests/test_fit_scoring.py`

## Generated Local Output

- `data/scored_postings.jsonl`

This file is generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Scores each filtered posting from 0 to 100.
- Labels each posting as `strong`, `medium`, or `weak`.
- Boosts postings at companies with known connections.
- Rewards internship-related, 2027, profile-theme, preference, and location matches.
- Penalizes disliked role types such as marketing and social media.
- Records explanations and gaps for each posting.
- Does not read or expose resume text.

## CLI

Use this command to score filtered postings:

```powershell
uv run internship-search score-postings
```

## Latest Local Run

- Scored postings: 4
- Top score: 60
- Provider: `local_rule_based`

## Notes

This was the first scoring implementation using a local rule-based provider. Gemini integration is now available through `013-ai-provider-integration.md`.

## Verification

```powershell
uv run pytest
```

Result: `22 passed`.
