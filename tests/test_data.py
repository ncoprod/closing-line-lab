import pandas as pd
import pytest

from closing_line_lab import data


def test_permission_gate_precedes_network(monkeypatch, tmp_path):
    permission = tmp_path / "permission.json"
    permission.write_text('{"automated_collection":false,"evidence":null}')
    monkeypatch.setattr(data, "PERMISSION", permission)
    monkeypatch.setattr(
        data.urllib.request, "urlopen", lambda *a, **k: pytest.fail("Network contacted")
    )
    with pytest.raises(data.PermissionMissing):
        data.cached_download("fixtures.csv")


def test_training_permission_does_not_authorize_ledger_publication(monkeypatch, tmp_path):
    permission = tmp_path / "permission.json"
    permission.write_text(
        '{"automated_collection":true,"model_training":true,"evidence":"synthetic"}'
    )
    monkeypatch.setattr(data, "PERMISSION", permission)
    data.require_permission(training=True)
    with pytest.raises(data.PermissionMissing, match="ledger"):
        data.require_permission(publishing=True)


def test_normalize_timezone_and_missing_values(tmp_path):
    path = tmp_path / "fixture.csv"
    path.write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,B365H,B365D,B365A\n"
        "E0,28/03/2026,15:00,A,B,2,1,2,3,4\n"
        "E0,29/03/2026,15:00,C,D,,,,,\n"
    )
    result = data.normalize(path, "synthetic")
    assert result.kickoff_utc.iloc[0].hour == 15
    assert result.kickoff_utc.iloc[1].hour == 14
    assert pd.isna(result.outcome.iloc[1])
    assert pd.isna(result.B365H.iloc[1])
    assert result.available_at.iloc[0] - result.kickoff_utc.iloc[0] == pd.Timedelta(hours=12)


def test_no_time_and_duplicates(tmp_path):
    path = tmp_path / "old.csv"
    line = "E0,01/02/2012,A,B,1,1\n"
    path.write_text("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\n" + line)
    frame = data.normalize(path, "synthetic")
    assert not frame.time_known.iloc[0]
    assert frame.available_at.iloc[0] - frame.kickoff_utc.iloc[0] == pd.Timedelta(hours=36)
    path.write_text(path.read_text() + line)
    with pytest.raises(ValueError, match="Duplicate"):
        data.normalize(path, "synthetic")
