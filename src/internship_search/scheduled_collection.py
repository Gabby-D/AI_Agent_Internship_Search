"""Run the local internship search pipeline as a repeatable scheduled workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from internship_search.paths import default_data_dir, default_private_dir
from internship_search.search_checkpoint import (
    SearchCheckpoint,
    SearchPaused,
    SearchRunLock,
    clear_partial_collection_files,
    clear_search_pause,
    install_search_pause_on_shutdown,
    mark_search_paused,
    partial_errors_path,
    partial_postings_path,
    raise_if_search_paused,
    read_search_checkpoint,
    write_search_checkpoint,
)
from internship_search.search_progress import (
    COLLECT_END_PERCENT,
    JOB_BOARDS_LABEL,
    collect_percent,
    write_search_progress,
)


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
    private_dir: Path | str = default_private_dir(),
    data_dir: Path | str = default_data_dir(),
    generate_email: bool = True,
    send_email: bool = False,
    resume_aware: bool | None = None,
    include_job_boards: bool = False,
    target_year: str = "2027",
    now: Callable[[], datetime] | None = None,
) -> ScheduledCollectionResult:
    """Run collection, detection, filtering, reporting, scoring, and email draft steps."""

    install_search_pause_on_shutdown()
    clock = now or (lambda: datetime.now(timezone.utc))
    data_path = Path(data_dir)
    lock = SearchRunLock(data_path)
    if not lock.acquire():
        finished_at = clock().isoformat()
        return ScheduledCollectionResult(
            status="success",
            started_at=finished_at,
            finished_at=finished_at,
            postings_collected=0,
            source_errors=0,
            new_postings=0,
            included_postings=0,
            excluded_postings=0,
            scored_postings=0,
            email_postings=0,
            email_draft_path="",
            email_sent=False,
            log_path=data_path / "scheduled_collection_runs.jsonl",
            errors=[],
            steps=[
                WorkflowStepResult(
                    "collect",
                    "skipped",
                    "A search is already running.",
                )
            ],
            scoring_provider="",
            ai_fallback_count=0,
        )

    try:
        return _run_scheduled_collection(
            private_dir=private_dir,
            data_dir=data_path,
            generate_email=generate_email,
            send_email=send_email,
            resume_aware=resume_aware,
            include_job_boards=include_job_boards,
            target_year=target_year,
            clock=clock,
        )
    except SearchPaused:
        paused = mark_search_paused(data_path)
        try:
            write_search_progress(
                data_path,
                state="paused",
                percent=paused.percent if paused else 0,
                message="Paused. Search will resume when this computer is back on.",
                current=paused.current if paused else 0,
                total=paused.total if paused else 0,
                phase=paused.phase if paused else "collect",
                started_at=paused.started_at if paused else "",
            )
        except Exception:
            pass
        finished_at = clock().isoformat()
        return ScheduledCollectionResult(
            status="paused",
            started_at=paused.started_at if paused else finished_at,
            finished_at=finished_at,
            postings_collected=0,
            source_errors=0,
            new_postings=0,
            included_postings=0,
            excluded_postings=0,
            scored_postings=0,
            email_postings=0,
            email_draft_path="",
            email_sent=False,
            log_path=data_path / "scheduled_collection_runs.jsonl",
            errors=[],
            steps=[
                WorkflowStepResult(
                    "collect",
                    "paused",
                    "Search paused because the computer is shutting down.",
                )
            ],
            scoring_provider="",
            ai_fallback_count=0,
        )
    finally:
        lock.release()


def _run_scheduled_collection(
    *,
    private_dir: Path | str,
    data_dir: Path,
    generate_email: bool,
    send_email: bool,
    resume_aware: bool | None,
    include_job_boards: bool,
    target_year: str,
    clock: Callable[[], datetime],
) -> ScheduledCollectionResult:
    clear_search_pause()
    data_path = Path(data_dir)
    existing = read_search_checkpoint(data_path)
    resuming = bool(existing and existing.is_incomplete())
    started_at = existing.started_at if resuming and existing.started_at else clock().isoformat()
    collected_on = existing.collected_on if resuming and existing else datetime.now().date().isoformat()
    include_job_boards = bool(include_job_boards or (existing.include_job_boards if existing else False))
    generate_email = bool(generate_email or (existing.generate_email if existing else False))
    send_email = bool(send_email or (existing.send_email if existing else False))
    if resume_aware is None and existing is not None and resuming:
        resume_aware = existing.resume_aware
    if resuming and existing is not None:
        target_year = existing.target_year or target_year
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
    checkpoint_state: dict[str, object] = {
        "status": "running",
        "started_at": started_at,
        "collected_on": collected_on,
        "include_job_boards": include_job_boards,
        "generate_email": generate_email,
        "send_email": send_email,
        "resume_aware": resume_aware,
        "target_year": target_year,
        "completed_source_keys": list(existing.completed_source_keys) if resuming and existing else [],
        "job_boards_done": bool(existing.job_boards_done) if resuming and existing else False,
        "collect_done": bool(existing.collect_done) if resuming and existing else False,
        "percent": existing.percent if resuming and existing else 0,
        "message": existing.message if resuming and existing else "Starting search…",
        "current": existing.current if resuming and existing else 0,
        "total": existing.total if resuming and existing else 0,
        "phase": existing.phase if resuming and existing else "start",
    }

    def save_checkpoint(**updates: object) -> None:
        checkpoint_state.update(updates)
        keys = checkpoint_state["completed_source_keys"]
        if not isinstance(keys, (list, tuple)):
            keys = []
        try:
            write_search_checkpoint(
                data_path,
                SearchCheckpoint(
                    status=str(checkpoint_state["status"]),
                    started_at=str(checkpoint_state["started_at"]),
                    collected_on=str(checkpoint_state["collected_on"]),
                    include_job_boards=bool(checkpoint_state["include_job_boards"]),
                    generate_email=bool(checkpoint_state["generate_email"]),
                    send_email=bool(checkpoint_state["send_email"]),
                    resume_aware=checkpoint_state["resume_aware"]  # type: ignore[arg-type]
                    if checkpoint_state["resume_aware"] is None
                    else bool(checkpoint_state["resume_aware"]),
                    target_year=str(checkpoint_state["target_year"]),
                    completed_source_keys=tuple(str(key) for key in keys),
                    job_boards_done=bool(checkpoint_state["job_boards_done"]),
                    collect_done=bool(checkpoint_state["collect_done"]),
                    percent=int(checkpoint_state["percent"] or 0),
                    message=str(checkpoint_state["message"] or ""),
                    current=int(checkpoint_state["current"] or 0),
                    total=int(checkpoint_state["total"] or 0),
                    phase=str(checkpoint_state["phase"] or ""),
                ),
            )
        except Exception:
            pass

    def report_progress(
        *,
        percent: int,
        message: str,
        phase: str,
        current: int = 0,
        total: int = 0,
        state: str = "running",
        finished_at: str = "",
    ) -> None:
        checkpoint_state["percent"] = percent
        checkpoint_state["message"] = message
        checkpoint_state["phase"] = phase
        checkpoint_state["current"] = current
        checkpoint_state["total"] = total
        if state in {"running", "paused"}:
            checkpoint_state["status"] = state
        try:
            write_search_progress(
                data_path,
                state=state,
                percent=percent,
                message=message,
                current=current,
                total=total,
                phase=phase,
                started_at=started_at,
                finished_at=finished_at,
            )
        except Exception:
            pass
        save_checkpoint()

    def on_collect_progress(current: int, total: int, label: str) -> None:
        if label == JOB_BOARDS_LABEL:
            report_progress(
                percent=COLLECT_END_PERCENT,
                message="Searching job boards…",
                phase="job_boards",
                current=current,
                total=total,
            )
            return
        report_progress(
            percent=collect_percent(current, total),
            message=f"Searching {label} ({current} of {total})",
            phase="collect",
            current=current,
            total=total,
        )

    try:
        if resuming:
            report_progress(
                percent=int(checkpoint_state["percent"] or 0),
                message="Resuming the paused search…",
                phase=str(checkpoint_state["phase"] or "collect"),
                current=int(checkpoint_state["current"] or 0),
                total=int(checkpoint_state["total"] or 0),
            )
        else:
            report_progress(percent=0, message="Starting search…", phase="start")

        from internship_search.source_registry import (
            load_seed_source_registry,
            write_source_registry,
        )

        raise_if_search_paused()
        report_progress(percent=2, message="Building company list…", phase="registry")
        sources = load_seed_source_registry(private_dir)
        write_source_registry(sources, registry_path)
        steps.append(
            WorkflowStepResult(
                "registry",
                "succeeded",
                f"Registered {len(sources)} career sources.",
            )
        )
    except SearchPaused:
        raise
    except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
        message = str(error)
        errors.append(message)
        steps.append(WorkflowStepResult("registry", "failed", message))

    if not any(step.name == "registry" and step.status == "failed" for step in steps):
        try:
            from datetime import date as date_cls

            from internship_search.job_collector import (
                CollectionResult,
                collect_from_registry_file,
                read_postings_jsonl,
                write_postings_jsonl,
            )
            from internship_search.monitored_companies import (
                read_collection_errors_jsonl,
                write_collection_errors_jsonl,
            )
            from internship_search.search_checkpoint import JOB_BOARDS_CHECKPOINT_KEY

            if resuming and existing and existing.collect_done:
                collection_result = CollectionResult(
                    postings=read_postings_jsonl(postings_path),
                    errors=read_collection_errors_jsonl(collection_errors_path),
                    output_path=postings_path,
                )
                detail = (
                    f"Resumed after collecting {len(collection_result.postings)} "
                    "posting candidates."
                )
            else:
                collect_message = (
                    "Resuming company search…" if resuming else "Searching monitored companies…"
                )
                report_progress(percent=5 if not resuming else int(checkpoint_state["percent"] or 5), message=collect_message, phase="collect")
                completed_keys = set(existing.completed_source_keys) if resuming and existing else set()
                existing_postings = (
                    read_postings_jsonl(partial_postings_path(data_path)) if resuming else []
                )
                existing_errors = (
                    read_collection_errors_jsonl(partial_errors_path(data_path)) if resuming else []
                )
                collected_date = date_cls.fromisoformat(str(collected_on))

                def persist_collect(postings, collect_errors, completed_keys_list) -> None:
                    write_postings_jsonl(
                        postings,
                        partial_postings_path(data_path),
                        use_remote_apis=False,
                    )
                    write_collection_errors_jsonl(
                        collect_errors,
                        partial_errors_path(data_path),
                    )
                    save_checkpoint(
                        completed_source_keys=list(completed_keys_list),
                        job_boards_done=JOB_BOARDS_CHECKPOINT_KEY in completed_keys_list,
                        collect_done=False,
                        status="running",
                    )

                collection_result = collect_from_registry_file(
                    registry_path=registry_path,
                    output_path=postings_path,
                    errors_output_path=collection_errors_path,
                    include_job_boards=include_job_boards,
                    target_year=target_year,
                    progress_callback=on_collect_progress,
                    collected_on=collected_date,
                    completed_source_keys=completed_keys,
                    existing_postings=existing_postings,
                    existing_errors=existing_errors,
                    persist_callback=persist_collect,
                )
                save_checkpoint(
                    collect_done=True,
                    job_boards_done=True if include_job_boards else bool(checkpoint_state["job_boards_done"]),
                    status="running",
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
        except SearchPaused:
            raise
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("collect", "failed", message))

    if collection_result is not None:
        try:
            from internship_search.posting_history import detect_new_postings_file

            raise_if_search_paused()
            report_progress(percent=88, message="Checking for new postings…", phase="detect")
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
        except SearchPaused:
            raise
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("detect", "failed", message))

    if collection_result is not None:
        try:
            from internship_search.posting_filter import filter_postings_file

            raise_if_search_paused()
            report_progress(percent=91, message="Filtering undergraduate internships…", phase="filter")
            filter_result = filter_postings_file(
                input_path=postings_path,
                included_output_path=included_path,
                excluded_output_path=excluded_path,
                private_dir=private_dir,
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
        except SearchPaused:
            raise
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("filter", "failed", message))

    if filter_result is not None:
        try:
            from internship_search.review_report import generate_review_report_file

            raise_if_search_paused()
            report_progress(percent=94, message="Writing review report…", phase="report")
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
        except SearchPaused:
            raise
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("report", "failed", message))

    if filter_result is not None:
        try:
            from internship_search.fit_scoring import score_postings_file

            raise_if_search_paused()
            report_progress(percent=96, message="Scoring internships…", phase="score")
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
        except SearchPaused:
            raise
        except Exception as error:  # noqa: BLE001 - scheduled runs must record failures.
            message = str(error)
            errors.append(message)
            steps.append(WorkflowStepResult("score", "failed", message))

    if generate_email and score_result is not None:
        try:
            from internship_search.email_summary import generate_weekly_email_summary_file

            raise_if_search_paused()
            report_progress(percent=99, message="Preparing weekly email draft…", phase="email")
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
        except SearchPaused:
            raise
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
    finished_message = {
        "success": "Search complete.",
        "partial": "Search complete with some source issues.",
        "failed": "Search failed.",
    }.get(status, "Search finished.")
    report_progress(
        percent=100,
        message=finished_message,
        phase="done",
        state="failed" if status == "failed" else "completed",
        finished_at=finished_at,
    )
    save_checkpoint(
        status="failed" if status == "failed" else "completed",
        collect_done=True,
    )
    if status != "failed":
        clear_partial_collection_files(data_path)
    return result


def determine_run_status(steps: list[WorkflowStepResult]) -> str:
    if any(step.status == "failed" for step in steps):
        return "failed"
    if any(step.status == "warning" for step in steps):
        return "partial"
    return "success"


def is_scheduled_run_operationally_successful(
    result: ScheduledCollectionResult,
    *,
    require_email_sent: bool = False,
) -> bool:
    """Return True when required downstream steps completed despite source warnings."""
    if result.status in {"failed", "paused"}:
        return False

    if require_email_sent and not result.email_sent:
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
