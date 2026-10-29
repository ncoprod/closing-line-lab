import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from closing_line_lab.models import DixonColes, OffsetBlend, as_of, make_features


@given(st.integers(min_value=1, max_value=1000))
def test_asof_excludes_cutoff_and_future(seconds):
    cutoff = pd.Timestamp("2026-01-01", tz="UTC")
    frame = pd.DataFrame(
        {
            "available_at": [
                cutoff - pd.Timedelta(seconds=seconds),
                cutoff,
                cutoff + pd.Timedelta(seconds=seconds),
            ],
            "outcome": [0, 1, 2],
            "kickoff_utc": [cutoff - pd.Timedelta(days=2)] * 3,
        }
    )
    assert as_of(frame, cutoff).outcome.tolist() == [0]


def test_dixon_coles_probabilities_and_cutoff(history, cfg):
    cutoff = pd.Timestamp("2019-06-01", tz="UTC")
    model = DixonColes(cfg).fit(history, cutoff)
    p = model.predict("Team 0", "Team 1")
    assert p.sum() == pytest.approx(1)
    assert (p > 0).all()
    assert model.train_max_available < cutoff
    assert model.diagnostics["converged"]
    assert np.isfinite(model.predict("Unseen promoted team", "Team 0")).all()


@settings(
    max_examples=8, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(goals=st.integers(min_value=0, max_value=20))
def test_feature_property_future_and_closing_mutations_cannot_change_forecast(goals, history, cfg):
    cutoff = pd.Timestamp("2019-05-01", tz="UTC")
    target = history.iloc[[-1]].copy()
    target["decision_at"] = cutoff
    target["kickoff_utc"] = cutoff + pd.Timedelta(days=1)
    changed = history.copy()
    changed.loc[changed.available_at >= cutoff, ["hg", "ag"]] = goals
    changed.loc[:, ["AvgCH", "AvgCD", "AvgCA"]] = 100
    first = make_features(history, target, cfg)
    second = make_features(changed, target, cfg)
    pd.testing.assert_frame_equal(first, second)
    assert first.feature_max_available.max() < cutoff


def test_blend_does_not_train_on_future_outcomes(history, cfg):
    features = make_features(history, history.iloc[120:], cfg)
    frame = features.merge(history, on="match_id")
    cutoff = frame.available_at.iloc[15]
    first = OffsetBlend().fit(frame, cutoff)
    altered = frame.copy()
    altered.loc[altered.available_at >= cutoff, "outcome"] = 2
    second = OffsetBlend().fit(altered, cutoff)
    np.testing.assert_allclose(first.theta, second.theta)
    assert first.train_max_available < cutoff
