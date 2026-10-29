from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import numpy as np
import pandas as pd
import pytest

from closing_line_lab import forward, ledger


def test_synthetic_forecast_settlement_and_receipt_replay(tmp_path, monkeypatch, history, cfg):
    """Exercise production transformations locally; no provider data or GitHub mutation."""
    started = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    kickoff = started + timedelta(days=2)
    local = pd.Timestamp(kickoff).tz_convert("Europe/London")
    fixture = tmp_path / "fixtures.csv"
    header = "Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A"
    line = f"E0,{local:%d/%m/%Y},{local:%H:%M},Team 0,Team 1,4,4,4"
    fixture.write_text(header + "\n" + line + "\n")
    result = tmp_path / "results.csv"
    result.write_text(
        header
        + ",FTHG,FTAG,AvgCH,AvgCD,AvgCA,B365CH,B365CD,B365CA\n"
        + line
        + ",2,1,3,3.2,3.4,3.1,3.2,3.3\n"
    )
    entry = {
        "sha256": "synthetic",
        "retrieved_at": started.isoformat(),
        "last_modified": format_datetime(started),
    }
    path = tmp_path / "ledger.jsonl"
    shifted = history.copy()
    shift = pd.Timestamp(started - timedelta(days=10)) - shifted.kickoff_utc.max()
    shifted["kickoff_utc"] += shift
    shifted["available_at"] += shift
    monkeypatch.setattr(forward, "now_utc", lambda: started + timedelta(minutes=1))
    monkeypatch.setattr(forward, "require_permission", lambda **kw: None)
    monkeypatch.setattr(forward, "frozen_runtime", lambda: {**cfg, "model": "market"})
    monkeypatch.setattr(forward, "download_history", lambda: None)
    monkeypatch.setattr(forward, "load_matches", lambda: shifted)
    monkeypatch.setattr(
        forward,
        "cached_download",
        lambda relative, **kw: (fixture if relative == "fixtures.csv" else result, entry),
    )
    monkeypatch.setattr(forward, "file_sha", lambda path: "synthetic")
    monkeypatch.setattr(forward, "git", lambda *args: "synthetic-commit")
    monkeypatch.setattr(forward, "read_ledger", lambda: ledger.read_ledger(path))
    monkeypatch.setattr(forward, "append_event", lambda event: ledger.append_event(event, path))
    report = forward.forecast()
    assert report["new_forecasts"] == report["new_bets"] == 1
    forecast = ledger.read_ledger(path)[0]
    receipt = {
        "created_at": (started + timedelta(minutes=3)).isoformat(),
        "ledger_hashes": [forecast["hash"]],
    }
    monkeypatch.setattr(
        forward, "verify", lambda: ledger.verify_records(ledger.read_ledger(path), [receipt])
    )
    # Re-observation cannot replace or duplicate the forecast.
    assert forward.forecast()["new_forecasts"] == 0
    monkeypatch.setattr(forward, "now_utc", lambda: kickoff + timedelta(hours=24))
    assert forward.settle()["new_settlements"] == 1
    records = ledger.read_ledger(path)
    assert ledger.verify_records(records, [receipt])["settlements"] == 1
    assert ledger.replay_account(records)["open_stakes"] == 0
    expected = forecast["bet"]["stake_units"] * (3 if forecast["bet"]["side_index"] == 0 else -1)
    assert records[-1]["profit_units"] == pytest.approx(expected)
    assert records[-1]["log_clv"] == pytest.approx(
        np.log(4 / [3, 3.2, 3.4][forecast["bet"]["side_index"]])
    )
    assert forward.settle()["new_settlements"] == 0
