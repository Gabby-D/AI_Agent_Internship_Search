"""Track new, seen, changed, and missing posting candidates over time."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from internship_search.job_collector import JobPosting, canonical_posting_url, read_postings_jsonl


@dataclass(frozen=True)
class PostingHistoryEntry:
    posting_id: str
    title: str
    company: str
    location: str
    posting_url: str
    source_url: str
    first_seen: str
    last_seen: str
    content_hash: str
    active: bool
    role_key: str = ""


@dataclass(frozen=True)
class PostingChange:
    status: str
    posting_id: str
    title: str
    company: str
    posting_url: str
    first_seen: str
    last_seen: str
    reason: str


@dataclass(frozen=True)
class DetectionResult:
    changes: list[PostingChange]
    new_postings: list[JobPosting]
    history_output_path: Path
    changes_output_path: Path
    new_output_path: Path


@dataclass(frozen=True)
class DedupedCurrentPostings:
    postings_by_id: dict[str, JobPosting]
    duplicate_changes: list[PostingChange]


def detect_new_postings_file(
    postings_path: Path | str = "data/postings.jsonl",
    history_path: Path | str = "data/posting_history.json",
    changes_output_path: Path | str = "data/posting_changes.jsonl",
    new_output_path: Path | str = "data/new_postings.jsonl",
) -> DetectionResult:
    postings = read_postings_jsonl(postings_path)
    existing_history = read_history(history_path)
    return detect_new_postings(
        current_postings=postings,
        existing_history=existing_history,
        history_output_path=history_path,
        changes_output_path=changes_output_path,
        new_output_path=new_output_path,
    )


def detect_new_postings(
    current_postings: list[JobPosting],
    existing_history: dict[str, PostingHistoryEntry],
    history_output_path: Path | str,
    changes_output_path: Path | str,
    new_output_path: Path | str,
) -> DetectionResult:
    deduped = deduplicate_current_postings(current_postings)
    current_by_id = deduped.postings_by_id
    role_index = build_role_index(existing_history)
    updated_history: dict[str, PostingHistoryEntry] = {}
    changes: list[PostingChange] = list(deduped.duplicate_changes)
    new_postings: list[JobPosting] = []
    matched_history_ids: set[str] = set()

    for posting_id, posting in sorted(current_by_id.items()):
        previous = existing_history.get(posting_id)
        history_id = posting_id
        matched_by_role = False

        if previous is None:
            alternate_id = role_index.get(role_key(posting))
            if alternate_id and alternate_id != posting_id:
                previous = existing_history.get(alternate_id)
                history_id = alternate_id
                matched_by_role = True

        current_hash = content_hash(posting)

        if previous is None:
            entry = history_entry_from_posting(posting_id, posting, current_hash)
            changes.append(change_from_entry("new", entry, "Posting was not in history."))
            new_postings.append(posting)
        elif not previous.active:
            entry = update_history_entry(previous, posting, current_hash, active=True)
            changes.append(
                change_from_entry(
                    "changed",
                    entry,
                    describe_reopened_posting(previous, posting),
                )
            )
        elif previous.content_hash != current_hash:
            entry = update_history_entry(previous, posting, current_hash, active=True)
            changes.append(
                change_from_entry(
                    "changed",
                    entry,
                    describe_content_change(previous, posting, matched_by_role=matched_by_role),
                )
            )
        else:
            entry = update_history_entry(previous, posting, current_hash, active=True)
            reason = "Posting was seen before."
            if matched_by_role and canonical_posting_id(previous.posting_url) != posting_id:
                reason = (
                    "Same role matched by company, title, and location at an alternate URL: "
                    f"{posting.posting_url}."
                )
            changes.append(change_from_entry("seen", entry, reason))

        updated_history[history_id] = entry
        matched_history_ids.add(history_id)

    for posting_id, previous in sorted(existing_history.items()):
        if posting_id in matched_history_ids:
            continue
        missing_entry = replace(previous, active=False)
        updated_history[posting_id] = missing_entry
        changes.append(
            change_from_entry(
                "missing",
                missing_entry,
                describe_missing_posting(previous),
            )
        )

    history_path = write_history(updated_history, history_output_path)
    changes_path = write_changes_jsonl(changes, changes_output_path)
    new_path = write_new_postings_jsonl(new_postings, new_output_path)

    return DetectionResult(
        changes=changes,
        new_postings=new_postings,
        history_output_path=history_path,
        changes_output_path=changes_path,
        new_output_path=new_path,
    )


def read_history(path: Path | str) -> dict[str, PostingHistoryEntry]:
    history_path = Path(path)
    if not history_path.exists():
        return {}

    raw_entries = json.loads(history_path.read_text(encoding="utf-8"))
    return {
        raw_entry["posting_id"]: normalize_history_entry(raw_entry)
        for raw_entry in raw_entries
    }


def normalize_history_entry(raw_entry: dict[str, object]) -> PostingHistoryEntry:
    entry = PostingHistoryEntry(
        posting_id=str(raw_entry["posting_id"]),
        title=str(raw_entry["title"]),
        company=str(raw_entry["company"]),
        location=str(raw_entry["location"]),
        posting_url=str(raw_entry["posting_url"]),
        source_url=str(raw_entry["source_url"]),
        first_seen=str(raw_entry["first_seen"]),
        last_seen=str(raw_entry["last_seen"]),
        content_hash=str(raw_entry["content_hash"]),
        active=bool(raw_entry["active"]),
        role_key=str(raw_entry.get("role_key", "")),
    )
    if entry.role_key:
        return entry
    return replace(
        entry,
        role_key=role_key_from_parts(entry.company, entry.title, entry.location),
    )


def write_history(
    history: dict[str, PostingHistoryEntry],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = sorted(history.values(), key=lambda entry: (entry.company, entry.title, entry.posting_id))
    path.write_text(
        json.dumps([asdict(entry) for entry in entries], indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_changes_jsonl(changes: list[PostingChange], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(change), sort_keys=True) for change in changes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def write_new_postings_jsonl(postings: list[JobPosting], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(posting), sort_keys=True) for posting in postings]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def summarize_detection_result(result: DetectionResult) -> str:
    counts: dict[str, int] = {}
    for change in result.changes:
        counts[change.status] = counts.get(change.status, 0) + 1

    lines = [
        "New posting detection summary",
        "=============================",
        f"Changes recorded: {len(result.changes)}",
        f"New postings: {len(result.new_postings)}",
        f"Wrote history to: {result.history_output_path}",
        f"Wrote changes to: {result.changes_output_path}",
        f"Wrote new postings to: {result.new_output_path}",
    ]

    if counts:
        lines.append("")
        lines.append("Status counts:")
        lines.extend(f"- {status}: {count}" for status, count in sorted(counts.items()))

    return "\n".join(lines)


def deduplicate_current_postings(postings: list[JobPosting]) -> DedupedCurrentPostings:
    grouped_by_role: dict[str, dict[str, JobPosting]] = {}
    for posting in postings:
        posting_id = canonical_posting_id(posting.posting_url)
        role = role_key(posting)
        grouped_by_role.setdefault(role, {})
        grouped_by_role[role].setdefault(posting_id, posting)

    postings_by_id: dict[str, JobPosting] = {}
    duplicate_changes: list[PostingChange] = []

    for role, postings_by_url in grouped_by_role.items():
        if len(postings_by_url) == 1:
            posting_id, posting = next(iter(postings_by_url.items()))
            postings_by_id[posting_id] = posting
            continue

        kept_id, kept_posting = select_preferred_posting(postings_by_url)
        postings_by_id[kept_id] = kept_posting
        for posting_id, posting in postings_by_url.items():
            if posting_id == kept_id:
                continue
            duplicate_changes.append(
                PostingChange(
                    status="duplicate",
                    posting_id=kept_id,
                    title=kept_posting.title,
                    company=kept_posting.company,
                    posting_url=kept_posting.posting_url,
                    first_seen=kept_posting.date_collected,
                    last_seen=kept_posting.date_collected,
                    reason=(
                        "Duplicate role merged from alternate URL "
                        f"{posting.posting_url} using company, title, and location signals."
                    ),
                )
            )

    return DedupedCurrentPostings(
        postings_by_id=postings_by_id,
        duplicate_changes=duplicate_changes,
    )


def build_role_index(history: dict[str, PostingHistoryEntry]) -> dict[str, str]:
    role_index: dict[str, str] = {}
    for posting_id, entry in history.items():
        role_index.setdefault(entry.role_key, posting_id)
    return role_index


def inactive_posting_urls(history: dict[str, PostingHistoryEntry]) -> set[str]:
    return {
        entry.posting_url
        for entry in history.values()
        if not entry.active
    }


def select_preferred_posting(
    postings_by_url: dict[str, JobPosting],
) -> tuple[str, JobPosting]:
    def preference(item: tuple[str, JobPosting]) -> tuple[int, int, int, int, str]:
        posting_id, posting = item
        url = posting.posting_url.lower()
        career_source = int(not posting.source_url.startswith("job-board://"))
        direct_listing = int(
            "linkedin.com" not in url
            and "indeed.com" not in url
        )
        specific_url = int(
            "/job/" in url
            or "/jobs/" in url
            or "greenhouse.io" in url
            or "lever.co" in url
        )
        return (career_source, direct_listing, specific_url, len(url), posting_id)

    return max(postings_by_url.items(), key=preference)


def canonical_posting_id(url: str) -> str:
    canonical = canonical_posting_url(url)
    if canonical:
        return canonical
    return url.strip().lower()


def role_key(posting: JobPosting) -> str:
    return role_key_from_parts(posting.company, posting.title, posting.location)


def role_key_from_parts(company: str, title: str, location: str) -> str:
    return "|".join(
        [
            normalize_role_text(company),
            normalize_role_text(title),
            normalize_role_text(location if location != "Unknown" else ""),
        ]
    )


def normalize_role_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def content_hash(posting: JobPosting) -> str:
    payload = {
        "title": posting.title,
        "company": posting.company,
        "location": posting.location,
        "posting_url": canonical_posting_id(posting.posting_url),
        "source_url": posting.source_url,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def history_entry_from_posting(
    posting_id: str,
    posting: JobPosting,
    current_hash: str,
) -> PostingHistoryEntry:
    return PostingHistoryEntry(
        posting_id=posting_id,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        posting_url=posting.posting_url,
        source_url=posting.source_url,
        first_seen=posting.date_collected,
        last_seen=posting.date_collected,
        content_hash=current_hash,
        active=True,
        role_key=role_key(posting),
    )


def update_history_entry(
    previous: PostingHistoryEntry,
    posting: JobPosting,
    current_hash: str,
    active: bool,
) -> PostingHistoryEntry:
    return PostingHistoryEntry(
        posting_id=previous.posting_id,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        posting_url=posting.posting_url,
        source_url=posting.source_url,
        first_seen=previous.first_seen,
        last_seen=posting.date_collected,
        content_hash=current_hash,
        active=active,
        role_key=role_key(posting),
    )


def describe_content_change(
    previous: PostingHistoryEntry,
    posting: JobPosting,
    *,
    matched_by_role: bool,
) -> str:
    details: list[str] = []
    if matched_by_role and canonical_posting_id(previous.posting_url) != canonical_posting_id(
        posting.posting_url
    ):
        details.append(
            f"URL changed from {previous.posting_url} to {posting.posting_url}"
        )
    if previous.title != posting.title:
        details.append(f"title changed from '{previous.title}' to '{posting.title}'")
    if previous.location != posting.location:
        details.append(f"location changed from '{previous.location}' to '{posting.location}'")
    if previous.source_url != posting.source_url:
        details.append("source URL changed")
    if not details:
        return "Posting content changed."
    return "Posting content changed: " + "; ".join(details) + "."


def describe_reopened_posting(
    previous: PostingHistoryEntry,
    posting: JobPosting,
) -> str:
    if canonical_posting_id(previous.posting_url) != canonical_posting_id(posting.posting_url):
        return (
            "Previously missing role reappeared at a new URL and may have reopened: "
            f"{posting.posting_url}."
        )
    return "Previously missing role reappeared in collection and may have reopened."


def describe_missing_posting(previous: PostingHistoryEntry) -> str:
    if previous.active:
        return (
            "Posting no longer appears in the current collection and is likely closed or expired."
        )
    return "Posting remains absent from the current collection and is still likely closed or expired."


def change_from_entry(status: str, entry: PostingHistoryEntry, reason: str) -> PostingChange:
    return PostingChange(
        status=status,
        posting_id=entry.posting_id,
        title=entry.title,
        company=entry.company,
        posting_url=entry.posting_url,
        first_seen=entry.first_seen,
        last_seen=entry.last_seen,
        reason=reason,
    )
