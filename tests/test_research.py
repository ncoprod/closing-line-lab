import numpy as np
import pandas as pd
import pytest

from closing_line_lab import research
from closing_line_lab.research import choose_bet, daily_returns, evaluate, simulate


def test_kelly_cap_and_no_bet(cfg):
    bet = choose_bet([0.6, 0.2, 0.2], [2, 3, 4], cfg)
    assert bet["side"] == "H"
    assert bet["stake_fraction"] == cfg["stake_cap"]
    assert choose_bet([0.4, 0.3, 0.3], [2, 3, 3], cfg) is None


def test_portfolio_never_uses_future_winnings_for_simultaneous_bets(history, cfg):
    frame = history.iloc[:20].copy()
    frame["decision_at"] = pd.Timestamp("2017-12-31", tz="UTC")
    frame[["pH", "pD", "pA"]] = [0.7, 0.2, 0.1]
    frame["outcome"] = 0
    bets = simulate(frame, cfg)
    assert len(bets) == 10
    assert bets.stake_units.sum() == pytest.approx(10)
    assert np.max(bets.stake_units) <= 1


def test_missing_closing_prices_do_not_change_bets_or_stakes(history, cfg):
    frame = history.iloc[:12].copy()
    frame["decision_at"] = frame.kickoff_utc - pd.Timedelta(days=1)
    frame[["pH", "pD", "pA"]] = [0.7, 0.2, 0.1]
    baseline = simulate(frame, cfg)
    changed = frame.copy()
    changed.loc[:, ["AvgCH", "AvgCD", "AvgCA"]] = np.nan
    missing = simulate(changed, cfg)
    assert missing.match_id.tolist() == baseline.match_id.tolist()
    np.testing.assert_allclose(missing.stake_units, baseline.stake_units)
    assert missing.log_clv.isna().all()
    assert len(daily_returns(baseline)) >= len(baseline)


def test_evaluation_closing_baseline_uses_identical_matches(history, cfg):
    frame = history.iloc[:12].copy()
    frame["decision_at"] = frame.kickoff_utc - pd.Timedelta(days=1)
    frame[["pH", "pD", "pA"]] = [0.7, 0.2, 0.1]
    frame.loc[frame.index[0], "AvgCH"] = np.nan
    report, _ = evaluate(frame, cfg)
    assert report["model"]["matches"] == report["closing_baseline"]["matches"] == 11
    assert report["missing_closing_triples"] == 1


def test_heldout_guard_precedes_data_read(monkeypatch):
    def blocked():
        raise RuntimeError("not frozen")

    monkeypatch.setattr(research, "assert_frozen", blocked)
    monkeypatch.setattr(research, "load_matches", lambda: pytest.fail("Holdout opened"))
    with pytest.raises(RuntimeError, match="not frozen"):
        research.build_features("test")


def test_heldout_second_open_is_refused(tmp_path, monkeypatch):
    (tmp_path / "results").mkdir()
    (tmp_path / "results/test.json").write_text("{}")
    monkeypatch.setattr(research, "ROOT", tmp_path)
    monkeypatch.setattr(research, "assert_frozen", lambda: None)
    with pytest.raises(RuntimeError, match="already opened"):
        research.run_backtest("test")


def test_daily_returns_keep_inactive_boundary_days():
    bets = pd.DataFrame({"settled_at": ["2026-01-03T12:00:00+00:00"], "profit_units": [1.0]})
    result = daily_returns(
        bets, pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-01-05", tz="UTC")
    )
    assert len(result) == 5
    assert result.iloc[0] == result.iloc[-1] == 0
    assert result.iloc[2] == pytest.approx(0.01)
