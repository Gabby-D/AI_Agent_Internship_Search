import json
from pathlib import Path
import pytest

from internship_search.review_state import get_activity_type, read_activity_log, append_activity_log


def test_get_activity_type_mapping():
    assert get_activity_type("opportunity_status_updated") == "posting status"
    assert get_activity_type("posting_note_updated") == "note edit"
    assert get_activity_type("company_list_updated") == "company edit"
    assert get_activity_type("company_suggestion_dismissed") == "company edit"
    assert get_activity_type("reference_file_updated") == "file upload"
    assert get_activity_type("reference_attachment_uploaded") == "file upload"
    assert get_activity_type("reference_attachment_deleted") == "file upload"
    assert get_activity_type("collection") == "collection"
    assert get_activity_type("scoring") == "scoring"
    assert get_activity_type("email") == "email"
    assert get_activity_type("preferences_updated") == "company edit"
    assert get_activity_type("random_action") == "other"
    assert get_activity_type("") == "other"


def test_read_activity_log_legacy_enrichment(tmp_path):
    log_file = tmp_path / "activity_log.jsonl"
    
    # 1. Legacy entry (no details or cost/api metadata)
    legacy_entry_1 = {
        "timestamp": "2026-07-16T12:00:00Z",
        "date": "2026-07-16",
        "action": "opportunity_status_updated",
        "subject": "https://example.com/job",
    }
    
    # 2. Legacy scoring entry with gemini provider
    legacy_entry_2 = {
        "timestamp": "2026-07-16T12:05:00Z",
        "date": "2026-07-16",
        "action": "scoring",
        "subject": "internship scoring",
        "details": {
            "provider": "gemini",
            "total_tokens": 1200
        }
    }
    
    # 3. New entry with full metadata
    new_entry = {
        "timestamp": "2026-07-16T12:10:00Z",
        "date": "2026-07-16",
        "action": "collection",
        "subject": "internship postings",
        "details": {
            "postings_collected": 5,
            "source_errors": 0,
            "api_invoked": False,
            "cost": {"status": "unavailable"}
        }
    }
    
    # Write to file
    with log_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps(legacy_entry_1) + "\n")
        f.write(json.dumps(legacy_entry_2) + "\n")
        f.write(json.dumps(new_entry) + "\n")
        
    events = read_activity_log(log_file)
    
    # Reversed ordering
    assert len(events) == 3
    
    # Check new entry (first in list because of reversed)
    assert events[0]["action"] == "collection"
    assert events[0]["activity_type"] == "collection"
    assert events[0]["api_invoked"] is False
    assert events[0]["cost"] == {"status": "unavailable"}
    
    # Check legacy scoring entry
    assert events[1]["action"] == "scoring"
    assert events[1]["activity_type"] == "scoring"
    assert events[1]["api_invoked"] is True
    assert events[1]["cost"]["amount"] == 0.0
    assert "1200 tokens" in events[1]["cost"]["basis"]
    
    # Check legacy status entry
    assert events[2]["action"] == "opportunity_status_updated"
    assert events[2]["activity_type"] == "posting status"
    assert events[2]["api_invoked"] is False
    assert events[2]["cost"] == {"status": "unavailable"}


def test_append_activity_log_writes_valid_jsonl(tmp_path):
    log_file = tmp_path / "activity_log.jsonl"
    
    append_activity_log(
        action="collection",
        subject="job list",
        details={"postings_collected": 10, "api_invoked": False, "cost": {"status": "unavailable"}},
        output_path=log_file
    )
    
    # Read and verify
    events = read_activity_log(log_file)
    assert len(events) == 1
    assert events[0]["action"] == "collection"
    assert events[0]["activity_type"] == "collection"
    assert events[0]["details"]["postings_collected"] == 10
    assert events[0]["details"]["api_invoked"] is False
    assert events[0]["details"]["cost"] == {"status": "unavailable"}
