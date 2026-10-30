import json

import numpy as np
import pytest

from closing_line_lab import report
from closing_line_lab.metrics import devig


def test_forward_report_pairs_closing_scores_and_counts_missing_closes(tmp_path, monkeypatch):
    records = []
    for mid, close in [("quoted", [2.0, 3.0, 4.0]), ("missing", None)]:
        records += [
            {
                "kind": "forecast",
                "match_id": mid,
                "probabilities": [0.5, 0.3, 0.2],
                "decision_at": "2026-11-01T12:00:00+00:00",
                "kickoff_utc": "2026-11-02T12:00:00+00:00",
                "bet": {"stake_units": 1.0},
            },
            {
                "kind": "settlement",
                "match_id": mid,
                "status": "SETTLED",
                "outcome": 0,
                "closing_prices": close,
                "recorded_at": "2026-11-03T12:00:00+00:00",
                "profit_units": 1.2,
                "log_clv": float(np.log(1.1)) if close else None,
                "fair_log_clv": 0.01 if close else None,
                "same_book_log_clv": None,
            },
        ]
    (tmp_path / "results").mkdir()
    (tmp_path / "README.md").write_text("<!-- RESULTS:START --><!-- RESULTS:END -->")
    monkeypatch.setattr(report, "ROOT", tmp_path)
    monkeypatch.setattr(report, "read_ledger", lambda: records)
    monkeypatch.setattr(report, "figures", lambda *args: None)
    monkeypatch.setattr(report, "git", lambda *args: "synthetic")
    report.generate()
    result = json.loads((tmp_path / "results/forward.json").read_text())
    assert result["settled_forecasts"] == 2
    assert result["scored_forecasts"] == result["scores"]["matches"] == 1
    assert result["closing_baseline"]["matches"] == 1
    assert result["scores"]["log_loss"] == pytest.approx(-np.log(0.5))
    assert result["closing_baseline"]["log_loss"] == pytest.approx(-np.log(devig([2, 3, 4])[0]))
    assert result["log_loss_gap"] == pytest.approx(np.log(devig([2, 3, 4])[0] / 0.5))
    assert result["clv_missing"] == 1
    assert result["clv"]["observations"] == result["fair_log_clv"]["observations"] == 1
    assert result["same_book_log_clv"]["observations"] == 0
    assert result["profit_units"] == pytest.approx(2.4)


def test_schedule_evidence_paginates_independently_of_recent_ci(tmp_path, monkeypatch):
    import subprocess

    (tmp_path / "results").mkdir()
    monkeypatch.setattr(report, "ROOT", tmp_path)
    schedule = {
        "id": 123,
        "event": "schedule",
        "head_sha": "sha",
        "created_at": "time",
        "status": "completed",
        "conclusion": "success",
        "html_url": "url",
        "head_branch": "main",
    }

    def output(args, **kwargs):
        if "list" in args:
            return json.dumps([{"event": "push", "conclusion": "success"}])
        assert "--paginate" in args and "--slurp" in args
        return json.dumps([{"workflow_runs": [schedule]}, {"workflow_runs": [schedule]}])

    monkeypatch.setattr(subprocess, "check_output", output)
    evidence = report.actions_evidence()
    assert evidence["successful_scheduled_runs"] == 2
    assert len(evidence["scheduled_runs"]) == 2
    assert all(r["event"] == "schedule" for r in evidence["scheduled_runs"])
