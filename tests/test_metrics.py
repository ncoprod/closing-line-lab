import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from closing_line_lab.metrics import block_ci, clv, deflated_sharpe, devig, power_analysis, scores


@given(st.lists(st.floats(min_value=1.01, max_value=100), min_size=3, max_size=3))
def test_devig_is_a_probability_vector(odds):
    p = devig(odds)
    assert p.sum() == pytest.approx(1)
    assert (p > 0).all()
    assert p[0] / p[1] == pytest.approx(odds[1] / odds[0])


def test_clv_math_and_direction():
    assert clv(2.2, 2) == pytest.approx(np.log(1.1))
    assert clv(2, 2) == 0
    assert clv(1.9, 2) < 0
    with pytest.raises(ValueError):
        devig([0, 2, 3])


def test_block_bootstrap_keeps_unequal_date_sizes():
    result = block_ci([0, 0, 0, 1], ["a", "a", "a", "b"], samples=100)
    assert result["mean"] == 0.25
    assert result["blocks"] == 2
    assert result["ci95"][0] <= 0.25 <= result["ci95"][1]
    assert block_ci([], [])["mean"] is None
    assert power_analysis([], [])["status"] == "NOT_ESTIMABLE"


def test_scores_separate_results_from_closing_distribution():
    result = scores([[0.5, 0.3, 0.2]], [0], [[0.4, 0.3, 0.3]])
    assert result["log_loss"] == pytest.approx(-np.log(0.5))
    assert result["brier"] == pytest.approx(0.38)
    assert result["closing_cross_entropy"] > result["log_loss"]


def test_more_trials_reduce_deflated_sharpe():
    returns = np.random.default_rng(19).normal(0.001, 0.02, 500)
    single = deflated_sharpe(returns, [0.05], 1)
    many = deflated_sharpe(returns, [0.05] * 100, 100)
    assert 0 <= many["probability"] < single["probability"] <= 1
    assert many["trial_sharpe_variance"] > 0


def test_power_scales_with_inverse_squared_effect():
    report = power_analysis([0.01, -0.02, 0.03, -0.04] * 20, list(range(80)))
    required = report["required_bets"]
    assert report["status"] == "ESTIMATED"
    assert required["5"] >= required["10"] >= required["100"] > 0
