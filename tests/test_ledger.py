from copy import deepcopy

import pytest

from closing_line_lab.common import digest
from closing_line_lab.ledger import append_event, read_ledger, replay_account, verify_records


def forecast():
    return {
        "kind": "forecast",
        "match_id": "synthetic-match",
        "kickoff_utc": "2026-11-01T15:00:00+00:00",
        "quote_retrieved_at": "2026-11-01T10:00:00+00:00",
        "decision_at": "2026-11-01T10:01:00+00:00",
        "recorded_at": "2026-11-01T10:02:00+00:00",
        "feature_max_available": "2026-10-31T10:00:00+00:00",
        "probabilities": [0.5, 0.3, 0.2],
        "prices": [2.2, 3.2, 4.0],
        "stake_cap_units": 1.0,
        "bet": {"side_index": 0, "side": "H", "odds": 2.2, "stake_units": 1.0},
    }


def receipt(record, at="2026-11-01T10:03:00+00:00"):
    return {"created_at": at, "ledger_hashes": [record["hash"]]}


def test_hash_chain_tamper_and_truncation(tmp_path):
    path = tmp_path / "ledger.jsonl"
    first = append_event(forecast(), path)
    assert read_ledger(path)[0] == first
    changed = deepcopy(first)
    changed["probabilities"] = [0.4, 0.3, 0.3]
    with pytest.raises(ValueError, match="hash"):
        verify_records([changed], [receipt(first)])
    path.write_text(path.read_text().rstrip("\n"))
    with pytest.raises(ValueError, match="Truncated"):
        read_ledger(path)


def test_server_receipt_required_and_late_push_rejected(tmp_path):
    record = append_event(forecast(), tmp_path / "ledger")
    assert verify_records([record], [receipt(record)])["status"] == "VERIFIED"
    with pytest.raises(ValueError, match="server receipt"):
        verify_records([record], [])
    with pytest.raises(ValueError, match="server receipt"):
        verify_records([record], [receipt(record, "2026-11-01T15:00:00+00:00")])
    # No locally selected git author/committer time can rescue a late server receipt.
    assert verify_records([], [])["status"] == "NO_FORECASTS"


def test_late_forecast_even_with_valid_chain_is_rejected(tmp_path):
    payload = forecast()
    payload["recorded_at"] = payload["kickoff_utc"]
    record = append_event(payload, tmp_path / "ledger")
    with pytest.raises(ValueError, match="pre-kickoff"):
        verify_records([record], [receipt(record)])


def test_asof_violation_even_with_valid_chain_is_rejected(tmp_path):
    payload = forecast()
    payload["feature_max_available"] = payload["decision_at"]
    record = append_event(payload, tmp_path / "ledger")
    with pytest.raises(ValueError, match="as-of"):
        verify_records([record], [receipt(record)])


def test_duplicate_and_account_replay(tmp_path):
    path = tmp_path / "ledger"
    record = append_event(forecast(), path)
    account = replay_account([record])
    assert account["cash"] == 99
    assert account["open_stakes"] == 1
    settlement = append_event(
        {
            "kind": "settlement",
            "match_id": record["match_id"],
            "forecast_hash": record["hash"],
            "recorded_at": "2026-11-02T10:00:00+00:00",
            "status": "SETTLED",
            "profit_units": 1.2,
        },
        path,
    )
    assert replay_account([record, settlement])["cash"] == pytest.approx(101.2)
    duplicate = deepcopy(record)
    duplicate["sequence"], duplicate["previous_hash"] = 2, record["hash"]
    duplicate["hash"] = digest({k: v for k, v in duplicate.items() if k != "hash"})
    with pytest.raises(ValueError, match="Duplicate"):
        verify_records([record, duplicate], [receipt(record), receipt(duplicate)])


def test_valid_chain_cannot_hide_wrong_settlement_profit(tmp_path):
    path = tmp_path / "ledger"
    record = append_event(forecast(), path)
    settlement = append_event(
        {
            "kind": "settlement",
            "match_id": record["match_id"],
            "forecast_hash": record["hash"],
            "recorded_at": "2026-11-02T10:00:00+00:00",
            "status": "SETTLED",
            "result_kickoff_utc": record["kickoff_utc"],
            "closing_prices": [2.0, 3.0, 4.0],
            "outcome": 2,
            "profit_units": 1.2,
            "log_clv": 0.1,
        },
        path,
    )
    with pytest.raises(ValueError, match="profit does not replay"):
        verify_records([record, settlement], [receipt(record)])
