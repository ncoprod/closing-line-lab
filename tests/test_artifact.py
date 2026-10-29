import numpy as np
import pandas as pd
import pytest

from closing_line_lab.artifact import predict
from closing_line_lab.common import digest
from closing_line_lab.metrics import devig
from closing_line_lab.models import SIDES, DixonColes, Elo, OffsetBlend


def test_exported_parameters_reproduce_in_memory_probabilities(history, cfg):
    cutoff = history.available_at.max() + pd.Timedelta(days=1)
    dc = DixonColes(cfg).fit(history, cutoff)
    elo = Elo(cfg)
    for row in history.sort_values("available_at").itertuples():
        elo.update(row)
    artifact = {
        "strategy_sha": digest(cfg),
        "dc": {"E0": {"teams": dc.teams, "theta": dc.theta.tolist()}},
        "elo": [[d, t, r] for (d, t), r in elo.ratings.items()],
        "blend_theta": [0.2, 0.1, 0.02, -0.01, -0.01],
    }
    artifact["artifact_sha"] = digest(artifact)
    prices = [2.2, 3.3, 3.6]
    values = {}
    for name, p in [
        ("dc", dc.predict("Team 0", "Team 1")),
        ("elo", elo.predict("E0", "Team 0", "Team 1")),
        ("market", devig(prices)),
    ]:
        values.update({name + "_" + s: p[i] for i, s in enumerate(SIDES)})
    blend = OffsetBlend(cfg["blend_ridge"])
    blend.theta = np.array(artifact["blend_theta"])
    expected = blend.predict(pd.DataFrame([values]))[0]
    np.testing.assert_allclose(predict(artifact, "E0", "Team 0", "Team 1", prices, cfg), expected)
    with pytest.raises(ValueError, match="Unknown team"):
        predict(artifact, "E0", "Unknown club", "Team 1", prices, cfg)
    artifact["blend_theta"][0] += 0.01
    with pytest.raises(ValueError, match="hash mismatch"):
        predict(artifact, "E0", "Team 0", "Team 1", prices, cfg)
