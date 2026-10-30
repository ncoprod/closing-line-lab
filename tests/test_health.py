import importlib.util
from datetime import UTC, datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_forward", Path(__file__).resolve().parents[1] / "ops/check_forward.py"
)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


def test_health_counts_completed_hours_not_skip_or_failed_launches():
    rows = [
        {"status": "COMPLETED", "slot": "2026-10-30T05", "checked_at": "2026-10-30T05:05:00Z"},
        {"status": "SKIPPED_BUSY_OR_COMPLETED", "slot": "2026-10-30T05"},
        {"status": "FAILED"},
        {"status": "COMPLETED", "slot": "2026-10-30T07", "checked_at": "2026-10-30T07:05:00Z"},
    ]
    result = health.cycle_health(rows, datetime(2026, 10, 30, 7, 10, tzinfo=UTC))
    assert result["completed_cycles"] == 2
    assert result["failed_log_entries"] == result["skipped_log_entries"] == 1
    assert result["missing_between_completed_slots"] == ["2026-10-30T06:00:00+00:00"]
    assert result["minutes_since_completion"] == 5
    assert result["fresh_within_90_minutes"]


def test_no_successful_cycle_is_unknown_not_healthy():
    result = health.cycle_health([], datetime(2026, 10, 30, 9, tzinfo=UTC))
    assert result["completed_cycles"] == 0
    assert result["minutes_since_completion"] is None
    assert not result["fresh_within_90_minutes"]


def test_publication_summary_uses_earliest_valid_server_receipt(monkeypatch):
    monkeypatch.setattr(health, "verify_records", lambda *args: {"forecasts": 1})
    records = [
        {
            "kind": "forecast",
            "hash": "h",
            "recorded_at": "2026-10-30T12:00:00Z",
            "kickoff_utc": "2026-10-31T12:00:00Z",
        }
    ]
    receipts = [
        {"created_at": time, "ledger_hashes": ["h"]}
        for time in [
            "2026-10-30T12:03:00Z",
            "2026-10-30T12:01:00Z",
            "2026-10-31T13:00:00Z",
        ]
    ]
    result = health.publication_health(records, receipts)
    assert result["receipted_forecasts"] == 1
    assert result["minimum_receipt_lead_minutes"] == 1439
    assert result["maximum_publication_delay_seconds"] == 60
