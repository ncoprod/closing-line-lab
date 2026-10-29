from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from closing_line_lab import forward, ledger, odds


@pytest.mark.parametrize(
    "started", [datetime(2026, 10, 30, 14, tzinfo=UTC), datetime(2027, 1, 28, 23, tzinfo=UTC)]
)
def test_synthetic_api_forecast_close_settlement_receipts(tmp_path, monkeypatch, cfg, started):
    kickoff = started + timedelta(hours=24)
    path = tmp_path / "ledger.jsonl"
    artifact = tmp_path / "model.json"
    artifact.write_text(
        '{"feature_max_available":"2026-10-29T00:00:00Z","artifact_sha":"synthetic"}'
    )
    clock = [started]
    event = {
        "id": "synthetic",
        "sport_key": "soccer_epl",
        "commence_time": kickoff.isoformat(),
        "home_team": "A",
        "away_team": "B",
    }
    fc = odds.forward_config()
    fc["sports"] = {"soccer_epl": "E0"}
    result = {
        **event,
        "completed": True,
        "scores": [{"name": "A", "score": "2"}, {"name": "B", "score": "1"}],
    }

    class Client:
        def get(self, sport, endpoint):
            if endpoint == "scores":
                return [result], {"sha256": "synthetic-result"}
            return [event], {"retrieved_at": clock[0].isoformat(), "sha256": "synthetic-quote"}

    def quote(event, priority, retrieved, config):
        return {
            "prices": [2.2, 3.2, 4.0],
            "effective_prices": [2.176, 3.156, 3.94],
            "raw_prices": [2.2, 3.2, 4.0],
            "bookmaker": "betfair_ex_eu",
            "updated_at": retrieved,
            "retrieved_at": retrieved,
            "commission": 0.02,
        }

    monkeypatch.setattr(forward, "ARTIFACT", artifact)
    monkeypatch.setattr(forward, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(forward, "now_utc", lambda: clock[0])
    monkeypatch.setattr(forward, "forward_config", lambda: fc)
    monkeypatch.setattr(forward, "frozen_runtime", lambda: {**cfg, "model": "blend"})
    monkeypatch.setattr(forward, "OddsClient", Client)
    monkeypatch.setattr(forward, "quote", quote)
    monkeypatch.setattr(forward, "predict", lambda *args: np.array([0.6, 0.2, 0.2]))
    monkeypatch.setattr(forward, "git", lambda *args: "synthetic-commit")
    monkeypatch.setattr(forward, "read_ledger", lambda: ledger.read_ledger(path))
    monkeypatch.setattr(forward, "append_event", lambda event: ledger.append_event(event, path))
    receipts = []
    monkeypatch.setattr(
        forward, "verify", lambda: ledger.verify_records(ledger.read_ledger(path), receipts)
    )
    report = forward.forecast()
    assert report["new_forecasts"] == 1
    first = ledger.read_ledger(path)[0]
    receipts.append(
        {
            "created_at": (started + timedelta(minutes=1)).isoformat(),
            "ledger_hashes": [first["hash"]],
        }
    )
    assert forward.forecast()["new_forecasts"] == 0
    clock[0] = kickoff - timedelta(minutes=30)
    assert forward.forecast()["new_closing_snapshots"] == 1
    closing = ledger.read_ledger(path)[-1]
    receipts.append(
        {
            "created_at": (clock[0] + timedelta(minutes=1)).isoformat(),
            "ledger_hashes": [closing["hash"]],
        }
    )
    clock[0] = kickoff + timedelta(days=1)
    assert forward.settle()["new_settlements"] == 1
    records = ledger.read_ledger(path)
    assert ledger.verify_records(records, receipts)["settlements"] == 1
    assert ledger.replay_account(records)["open_stakes"] == 0
    assert records[-1]["profit_units"] == pytest.approx(first["bet"]["stake_units"] * 1.176)
    assert records[-1]["log_clv"] == pytest.approx(0)
    assert records[-1]["closing_gap_minutes"] == 30
    assert forward.settle()["new_settlements"] == 0
