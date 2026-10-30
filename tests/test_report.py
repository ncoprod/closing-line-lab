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


def test_forward_dashboard_empty_sample_has_no_performance_line(tmp_path, monkeypatch):
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.figure import Figure

    monkeypatch.setattr(report, "ROOT", tmp_path)
    (tmp_path / "results").mkdir()
    saved = []
    monkeypatch.setattr(Figure, "savefig", lambda self, *args, **kwargs: saved.append(self))
    report.dashboard(
        pd.DataFrame(),
        {
            "forecasts": 4,
            "paper_bets": 0,
            "settled_bets": 0,
            "pending_forecasts": 4,
            "clv_missing": 0,
            "clv": {"mean": None, "observations": 0},
        },
    )
    fig = saved[0]
    assert all(not ax.lines for ax in fig.axes)
    assert any(t.get_text() == "Not estimable" for ax in fig.axes for t in ax.texts)
    plt.close(fig)


def test_dashboard_uses_clv_complete_cases_and_all_realized_profit(tmp_path, monkeypatch):
    import pandas as pd
    from matplotlib.figure import Figure

    monkeypatch.setattr(report, "ROOT", tmp_path)
    saved = []
    monkeypatch.setattr(Figure, "savefig", lambda self, *args, **kwargs: saved.append(self))
    bets = pd.DataFrame(
        [
            {
                "match_id": "a",
                "recorded_at": "2026-11-01T12:00:00Z",
                "log_clv": 0.02,
                "profit_units": -1.0,
            },
            {
                "match_id": "b",
                "recorded_at": "2026-11-02T12:00:00Z",
                "log_clv": None,
                "profit_units": 1.2,
            },
        ]
    )
    report.dashboard(
        bets,
        {
            "forecasts": 2,
            "paper_bets": 2,
            "settled_bets": 2,
            "pending_forecasts": 0,
            "clv_missing": 1,
            "clv": {"mean": 0.02, "observations": 1},
        },
    )
    clv_axis, profit_axis = saved[0].axes[1:3]
    assert clv_axis.lines[0].get_ydata().tolist() == [0.02]
    assert profit_axis.lines[0].get_ydata().tolist() == pytest.approx([-1.0, 0.2])
