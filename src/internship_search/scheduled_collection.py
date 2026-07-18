"""Run the local internship search pipeline as a repeatable scheduled workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class WorkflowStepResult:
    name: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class ScheduledCollectionResult:
    status: str
    started_at: str
    finished_at: str
    postings_collected: int
    source_errors: int
    new_postings: int
    included_postings: int
    excluded_postings: int
    scored_postings: int
    email_postings: int
    email_draft_path: str
    email_sent: bool
    log_path: Path
    errors: list[str]
    steps: list[WorkflowStepResult]
    scoring_provider: str
    ai_fallback_count: int


WorkflowStep = Callable[[], object]


def run_scheduled_collection(
    private_dir: Path | str = "private",
    data_dir: Path | str = "data",
    generate_email: bool = True,
    send_email: bool = False,
    resume_aware: bool | None = None,
    include_job_boards: bool = False,
    target_year: str = "2027",
    now: Callable[[], datetime] | None = None,
) -> ScheduledCollectionResult:
    """Run collection, detection, filtering, reporting, scoring, and email draft steps."""

    clock = now or (lambda: datetime.now(timezone.utc))
    started_at = clock().isoformat()
    data_path = Path(data_dir)
    errors: list[str] = []
    steps: list[WorkflowStepResult] = []

    registry_path = data_path / "source_registry.json"
    postings_path = data_path / "postings.jsonl"
    history_path = data_path / "posting_history.json"
    changes_path = data_path / "posting_changes.jsonl"
    new_postings_path = data_path / "new_postings.jsonl"
    included_path = data_path / "filtered_postings.jsonl"
    excluded_path = data_path / "excluded_postings.jsonl"
    report_path = data_path / "latest_report.md"
    scored_path = data_path / "scored_postings.jsonl"
    collection_errors_path = data_path / "collection_errors.jsonl"
    email_path = data_path / "weekly_email_summary.md"
    sent_history_path = data_path / "email_sent_history.json"
    log_path = data_path / "scheduled_collection_runs.jsonl"

    collection_result = None
    detection_result = None
    filter_result = None
    score_result = None
    email_result = None

    try:
        from internship_search.source_registry import (
            load_seed_source_registry,
            write_source_registry,
        )

        sources = load_seed_source_registry(private_dir)
        write_source_registry(sources, registry_path)
        steps.append(
            WorkflowStepResult(
                "registry",
                "succeeded",
                f"Registered {len(sources)} career sources.",
            )
        )
    except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
        message = str(error)
        errors.append(message)
        steps.append(WorkflowStepResult("registry", "failed", message))

    if not any(step.name == "registry" and step.status == "failed" for step in steps):
        try:
            from internship_search.job_collector import collect_from_registry_file

            collection_result = collect_from_registry_file(
                registry_path=registry_path,
                output_path=postings_path,
                errors_output_path=collection_errors_path,
                include_job_boards=include_job_boards,
                target_year=target_year,
            )
            detail = f"Collected {len(collection_result.postings)} posting candidates."
            try:
                from internship_search.review_state import append_activity_log
                append_activity_log(
                    action="collection",
                    subject="internship postings",
                    details={
                        "postings_collected": len(collection_result.postings),
                        "source_errors": len(collection_result.errors),
                        "api_invoked": False,
                        "cost": {"status": "unavailable"}
                    },
                    output_path=data_path / "activity_log.jsonl"
                )
            except Exception:
                pass
            if collection_result.errors:
                detail += f" {len(collection_result.errors)} source errors."
                errors.extend(
                    f"{error.company}: {error.message}"
                    for error in collection_result.errors
                )
            steps.append(
                WorkflowStepResult(
                    "collect",
                    "warning" if collection_result.errors else "succeeded",
                    detail,
                )
            )
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("collect", "failed", message))

    if collection_result is not None:
        try:
            from internship_search.posting_history import detect_new_postings_file

            detection_result = detect_new_postings_file(
                postings_path=postings_path,
                history_path=history_path,
                changes_output_path=changes_path,
                new_output_path=new_postings_path,
            )
            steps.append(
                WorkflowStepResult(
                    "detect",
                    "succeeded",
                    f"Detected {len(detection_result.new_postings)} new postings.",
                )
            )
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("detect", "failed", message))

    if collection_result is not None:
        try:
            from internship_search.posting_filter import filter_postings_file

            filter_result = filter_postings_file(
                input_path=postings_path,
                included_output_path=included_path,
                excluded_output_path=excluded_path,
            )
            steps.append(
                WorkflowStepResult(
                    "filter",
                    "succeeded",
                    (
                        f"Included {len(filter_result.included)} postings; "
                        f"excluded {len(filter_result.excluded)}."
                    ),
                )
            )
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("filter", "failed", message))

    if filter_result is not None:
        try:
            from internship_search.review_report import generate_review_report_file

            generate_review_report_file(
                included_path=included_path,
                excluded_path=excluded_path,
                registry_path=registry_path,
                output_path=report_path,
            )
            steps.append(
                WorkflowStepResult(
                    "report",
                    "succeeded",
                    f"Wrote review report to {report_path}.",
                )
            )
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("report", "failed", message))

    if filter_result is not None:
        try:
            from internship_search.fit_scoring import score_postings_file

            score_result = score_postings_file(
                postings_path=included_path,
                private_dir=private_dir,
                registry_path=registry_path,
                output_path=scored_path,
                resume_aware=resume_aware,
            )
            detail = (
                f"Scored {len(score_result.scored_postings)} postings "
                f"with {score_result.provider}."
            )
            try:
                from internship_search.review_state import append_activity_log
                is_gemini = (score_result.provider == "gemini")
                cost_info = {}
                if is_gemini and score_result.usage:
                    cost_info = {
                        "amount": 0.0,
                        "currency": "USD",
                        "basis": f"Gemini API free tier ({score_result.usage.total_tokens} tokens)"
                    }
                else:
                    cost_info = {
                        "status": "unavailable"
                    }
                append_activity_log(
                    action="scoring",
                    subject="internship scoring",
                    details={
                        "scored_postings": len(score_result.scored_postings),
                        "provider": score_result.provider,
                        "api_invoked": is_gemini,
                        "prompt_tokens": score_result.usage.prompt_tokens if (is_gemini and score_result.usage) else 0,
                        "output_tokens": score_result.usage.output_tokens if (is_gemini and score_result.usage) else 0,
                        "cost": cost_info
                    },
                    output_path=data_path / "activity_log.jsonl"
                )
            except Exception:
                pass
            if score_result.ai_fallback_count:
                detail += f" {score_result.ai_fallback_count} postings used local fallback."
            steps.append(
                WorkflowStepResult(
                    "score",
                    "warning" if score_result.ai_fallback_count else "succeeded",
                    detail,
                )
            )
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("score", "failed", message))

    if generate_email and score_result is not None:
        try:
            from internship_search.email_summary import generate_weekly_email_summary_file

            email_result = generate_weekly_email_summary_file(
                scored_path=scored_path,
                new_postings_path=new_postings_path,
                registry_path=registry_path,
                output_path=email_path,
                sent_history_path=sent_history_path,
                history_path=history_path,
                collection_errors_path=collection_errors_path,
                send=send_email,
            )
            detail = f"Selected {len(email_result.selected_postings)} postings for email."
            if email_result.email_sent:
                detail += " Email sent."
            try:
                from internship_search.review_state import append_activity_log
                append_activity_log(
                    action="email",
                    subject="weekly summary email",
                    details={
                        "recipient": email_result.recipient if hasattr(email_result, 'recipient') else "user",
                        "sent": email_result.email_sent,
                        "api_invoked": email_result.email_sent,
                        "cost": {
                            "amount": 0.0 if email_result.email_sent else None,
                            "currency": "USD" if email_result.email_sent else None,
                            "basis": "Gmail SMTP (free tier)" if email_result.email_sent else None,
                            "status": "unavailable" if not email_result.email_sent else None
                        }
                    },
                    output_path=data_path / "activity_log.jsonl"
                )
            except Exception:
                pass
            steps.append(
                WorkflowStepResult(
                    "email",
                    "succeeded",
                    detail,
                )
            )
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("email", "failed", message))
    elif not generate_email:
        steps.append(WorkflowStepResult("email", "skipped", "Email generation disabled."))

    finished_at = clock().isoformat()
    status = determine_run_status(steps)
    result = ScheduledCollectionResult(
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        postings_collected=len(collection_result.postings) if collection_result else 0,
        source_errors=len(collection_result.errors) if collection_result else 0,
        new_postings=len(detection_result.new_postings) if detection_result else 0,
        included_postings=len(filter_result.included) if filter_result else 0,
        excluded_postings=len(filter_result.excluded) if filter_result else 0,
        scored_postings=len(score_result.scored_postings) if score_result else 0,
        email_postings=len(email_result.selected_postings) if email_result else 0,
        email_draft_path=str(email_result.output_path) if email_result else "",
        email_sent=email_result.email_sent if email_result else False,
        log_path=log_path,
        errors=errors,
        steps=steps,
        scoring_provider=score_result.provider if score_result else "",
        ai_fallback_count=score_result.ai_fallback_count if score_result else 0,
    )
    write_run_log(result)
    return result


def determine_run_status(steps: list[WorkflowStepResult]) -> str:
    if any(step.status == "failed" for step in steps):
        return "failed"
    if any(step.status == "warning" for step in steps):
        return "partial"
    return "success"


def is_scheduled_run_operationally_successful(result: ScheduledCollectionResult) -> bool:
    """Return True when required downstream steps completed despite source warnings."""
    if result.status == "failed":
        return False

    step_statuses = {step.name: step.status for step in result.steps}
    if step_statuses.get("score") == "failed":
        return False
    if step_statuses.get("email") == "failed":
        return False
    return True


def write_run_log(result: ScheduledCollectionResult) -> Path:
    result.log_path.parent.mkdir(parents=True, exist_ok=True)
    with result.log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(asdict(result), default=str, sort_keys=True) + "\n")
    return result.log_path


def summarize_scheduled_collection(result: ScheduledCollectionResult) -> str:
    lines = [
        "Scheduled collection summary",
        "============================",
        f"Status: {result.status}",
        f"Started: {result.started_at}",
        f"Finished: {result.finished_at}",
        "",
        "Step results:",
    ]
    for step in result.steps:
        detail = f" - {step.detail}" if step.detail else ""
        lines.append(f"- {step.name}: {step.status}{detail}")

    lines.extend(
        [
            "",
            "Counts:",
            f"- Posting candidates collected: {result.postings_collected}",
            f"- Source errors: {result.source_errors}",
            f"- New postings: {result.new_postings}",
            f"- Included postings: {result.included_postings}",
            f"- Excluded postings: {result.excluded_postings}",
            f"- Scored postings: {result.scored_postings}",
            f"- Scoring provider: {result.scoring_provider or 'Not run'}",
            f"- AI fallback postings: {result.ai_fallback_count}",
            f"- Email draft postings: {result.email_postings}",
            f"- Email sent: {result.email_sent}",
            f"- Email draft path: {result.email_draft_path or 'Not generated'}",
            f"- Run log: {result.log_path}",
        ]
    )
    if result.errors:
        lines.append("")
        lines.append("Errors and warnings:")
        lines.extend(f"- {error}" for error in result.errors)
    return "\n".join(lines)
