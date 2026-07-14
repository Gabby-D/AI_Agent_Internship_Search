from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from internship_search.scheduled_collection import (
    ScheduledCollectionResult,
    determine_run_status,
    is_scheduled_run_operationally_successful,
    run_scheduled_collection,
    summarize_scheduled_collection,
    WorkflowStepResult,
)


def fixed_now():
    return datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)


def test_run_scheduled_collection_composes_pipeline_and_logs(monkeypatch, tmp_path):
    calls: list[str] = []

    import internship_search.email_summary as email_summary
    import internship_search.fit_scoring as fit_scoring
    import internship_search.job_collector as job_collector
    import internship_search.posting_filter as posting_filter
    import internship_search.posting_history as posting_history
    import internship_search.review_report as review_report
    import internship_search.source_registry as source_registry

    monkeypatch.setattr(
        source_registry,
        "load_seed_source_registry",
        lambda private_dir: calls.append("load_sources") or ["source"],
    )
    monkeypatch.setattr(
        source_registry,
        "write_source_registry",
        lambda sources, output_path: calls.append("write_registry") or Path(output_path),
    )
    monkeypatch.setattr(
        job_collector,
        "collect_from_registry_file",
        lambda registry_path, output_path, include_job_boards=False, target_year="2027": calls.append("collect")
        or SimpleNamespace(postings=[object(), object()], errors=[]),
    )
    monkeypatch.setattr(
        posting_history,
        "detect_new_postings_file",
        lambda postings_path, history_path, changes_output_path, new_output_path: calls.append("detect")
        or SimpleNamespace(new_postings=[object()]),
    )
    monkeypatch.setattr(
        posting_filter,
        "filter_postings_file",
        lambda input_path, included_output_path, excluded_output_path: calls.append("filter")
        or SimpleNamespace(included=[object()], excluded=[object(), object()]),
    )
    monkeypatch.setattr(
        review_report,
        "generate_review_report_file",
        lambda included_path, excluded_path, registry_path, output_path: calls.append("report")
        or SimpleNamespace(output_path=Path(output_path)),
    )
    monkeypatch.setattr(
        fit_scoring,
        "score_postings_file",
        lambda postings_path, private_dir, registry_path, output_path, resume_aware=None: calls.append("score")
        or SimpleNamespace(scored_postings=[object()], provider="local_rule_based", ai_fallback_count=0),
    )
    monkeypatch.setattr(
        email_summary,
        "generate_weekly_email_summary_file",
        lambda **kwargs: calls.append("email")
        or SimpleNamespace(
            selected_postings=[object()],
            output_path=Path(kwargs["output_path"]),
            email_sent=False,
        ),
    )

    result = run_scheduled_collection(
        private_dir=tmp_path / "private",
        data_dir=tmp_path / "data",
        now=fixed_now,
    )

    assert result.status == "success"
    assert result.scoring_provider == "local_rule_based"
    assert result.ai_fallback_count == 0
    assert result.postings_collected == 2
    assert result.new_postings == 1
    assert result.included_postings == 1
    assert result.excluded_postings == 2
    assert result.scored_postings == 1
    assert result.email_postings == 1
    assert calls == [
        "load_sources",
        "write_registry",
        "collect",
        "detect",
        "filter",
        "report",
        "score",
        "email",
    ]
    assert result.log_path.exists()
    assert '"status": "success"' in result.log_path.read_text(encoding="utf-8")
    summary = summarize_scheduled_collection(result)
    assert "Step results:" in summary
    assert "- collect: succeeded" in summary


def test_run_scheduled_collection_marks_partial_when_source_errors_occur(monkeypatch, tmp_path):
    import internship_search.fit_scoring as fit_scoring
    import internship_search.job_collector as job_collector
    import internship_search.posting_filter as posting_filter
    import internship_search.posting_history as posting_history
    import internship_search.review_report as review_report
    import internship_search.source_registry as source_registry

    monkeypatch.setattr(source_registry, "load_seed_source_registry", lambda private_dir: ["source"])
    monkeypatch.setattr(
        source_registry,
        "write_source_registry",
        lambda sources, output_path: Path(output_path),
    )
    monkeypatch.setattr(
        job_collector,
        "collect_from_registry_file",
        lambda registry_path, output_path, include_job_boards=False, target_year="2027": SimpleNamespace(
            postings=[object()],
            errors=[SimpleNamespace(company="McKinsey", message="timed out")],
        ),
    )
    monkeypatch.setattr(
        posting_history,
        "detect_new_postings_file",
        lambda **kwargs: SimpleNamespace(new_postings=[]),
    )
    monkeypatch.setattr(
        posting_filter,
        "filter_postings_file",
        lambda **kwargs: SimpleNamespace(included=[object()], excluded=[]),
    )
    monkeypatch.setattr(
        review_report,
        "generate_review_report_file",
        lambda **kwargs: SimpleNamespace(output_path=Path("data/latest_report.md")),
    )
    monkeypatch.setattr(
        fit_scoring,
        "score_postings_file",
        lambda **kwargs: SimpleNamespace(
            scored_postings=[object()],
            provider="gemini",
            ai_fallback_count=0,
        ),
    )

    result = run_scheduled_collection(
        private_dir=tmp_path / "private",
        data_dir=tmp_path / "data",
        generate_email=False,
        now=fixed_now,
    )

    assert result.status == "partial"
    assert result.source_errors == 1
    summary = summarize_scheduled_collection(result)
    assert "- collect: warning" in summary
    assert "McKinsey: timed out" in summary


def test_run_scheduled_collection_summary_includes_ai_fallbacks(monkeypatch, tmp_path):
    import internship_search.fit_scoring as fit_scoring
    import internship_search.job_collector as job_collector
    import internship_search.posting_filter as posting_filter
    import internship_search.posting_history as posting_history
    import internship_search.review_report as review_report
    import internship_search.source_registry as source_registry

    monkeypatch.setattr(source_registry, "load_seed_source_registry", lambda private_dir: ["source"])
    monkeypatch.setattr(
        source_registry,
        "write_source_registry",
        lambda sources, output_path: Path(output_path),
    )
    monkeypatch.setattr(
        job_collector,
        "collect_from_registry_file",
        lambda registry_path, output_path, include_job_boards=False, target_year="2027": SimpleNamespace(
            postings=[object()],
            errors=[],
        ),
    )
    monkeypatch.setattr(
        posting_history,
        "detect_new_postings_file",
        lambda **kwargs: SimpleNamespace(new_postings=[]),
    )
    monkeypatch.setattr(
        posting_filter,
        "filter_postings_file",
        lambda **kwargs: SimpleNamespace(included=[object(), object()], excluded=[]),
    )
    monkeypatch.setattr(
        review_report,
        "generate_review_report_file",
        lambda **kwargs: SimpleNamespace(output_path=Path("data/latest_report.md")),
    )
    monkeypatch.setattr(
        fit_scoring,
        "score_postings_file",
        lambda **kwargs: SimpleNamespace(
            scored_postings=[object(), object()],
            provider="gemini",
            ai_fallback_count=2,
        ),
    )

    result = run_scheduled_collection(
        private_dir=tmp_path / "private",
        data_dir=tmp_path / "data",
        generate_email=False,
        now=fixed_now,
    )

    assert result.status == "partial"
    assert result.ai_fallback_count == 2
    summary = summarize_scheduled_collection(result)
    assert "- score: warning" in summary
    assert "AI fallback postings: 2" in summary


def test_determine_run_status_prefers_failed_over_partial():
    steps = [
        WorkflowStepResult("collect", "warning", "1 source error"),
        WorkflowStepResult("score", "failed", "provider unavailable"),
    ]

    assert determine_run_status(steps) == "failed"


def test_is_scheduled_run_operationally_successful_for_partial_source_warnings(tmp_path):
    result = ScheduledCollectionResult(
        status="partial",
        started_at="2026-07-10T00:00:00+00:00",
        finished_at="2026-07-10T00:05:00+00:00",
        postings_collected=14,
        source_errors=57,
        new_postings=14,
        included_postings=14,
        excluded_postings=0,
        scored_postings=14,
        email_postings=14,
        email_draft_path="data/weekly_email_summary.md",
        email_sent=False,
        log_path=tmp_path / "runs.jsonl",
        errors=[],
        steps=[
            WorkflowStepResult("collect", "warning", "57 source errors"),
            WorkflowStepResult("score", "succeeded", "Scored 14 postings."),
            WorkflowStepResult("email", "succeeded", "Selected 14 postings for email."),
        ],
        scoring_provider="gemini",
        ai_fallback_count=0,
    )

    assert is_scheduled_run_operationally_successful(result) is True


def test_is_scheduled_run_operationally_successful_false_when_score_fails(tmp_path):
    result = ScheduledCollectionResult(
        status="failed",
        started_at="2026-07-10T00:00:00+00:00",
        finished_at="2026-07-10T00:05:00+00:00",
        postings_collected=1,
        source_errors=1,
        new_postings=0,
        included_postings=0,
        excluded_postings=0,
        scored_postings=0,
        email_postings=0,
        email_draft_path="",
        email_sent=False,
        log_path=tmp_path / "runs.jsonl",
        errors=["provider unavailable"],
        steps=[
            WorkflowStepResult("collect", "warning", "1 source error"),
            WorkflowStepResult("score", "failed", "provider unavailable"),
        ],
        scoring_provider="",
        ai_fallback_count=0,
    )

    assert is_scheduled_run_operationally_successful(result) is False


def test_run_scheduled_collection_records_failure_and_skips_email(monkeypatch, tmp_path):
    import internship_search.email_summary as email_summary
    import internship_search.job_collector as job_collector
    import internship_search.source_registry as source_registry

    monkeypatch.setattr(source_registry, "load_seed_source_registry", lambda private_dir: [])
    monkeypatch.setattr(source_registry, "write_source_registry", lambda sources, output_path: Path(output_path))

    def fail_collection(registry_path, output_path, include_job_boards=False, target_year="2027"):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(job_collector, "collect_from_registry_file", fail_collection)
    monkeypatch.setattr(
        email_summary,
        "generate_weekly_email_summary_file",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("email should be skipped")),
    )

    result = run_scheduled_collection(
        private_dir=tmp_path / "private",
        data_dir=tmp_path / "data",
        now=fixed_now,
    )

    assert result.status == "failed"
    assert result.email_postings == 0
    assert result.errors == ["network unavailable"]
    assert "Status: failed" in summarize_scheduled_collection(result)
