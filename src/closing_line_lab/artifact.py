"""Export fitted parameters, never historical training rows, for hosted inference."""

import numpy as np
import pandas as pd

from .common import ROOT, digest, file_sha, now_utc, read_json, strategy, write_json
from .data import PROCESSED, load_matches, require_permission
from .metrics import devig
from .models import SIDES, DixonColes, Elo, OffsetBlend, as_of, probability_matrix
from .research import assert_frozen, git, joined_features

ARTIFACT = ROOT / "config/fitted_model.json"


def prepare():
    selection = assert_frozen()
    require_permission(training=True)
    if ARTIFACT.exists():
        raise RuntimeError("Forward parameters already exported; do not refit during v1")
    if not (ROOT / "results/test.json").exists():
        raise RuntimeError("Evaluate the frozen test once before exporting forward parameters")
    cfg, cutoff = strategy(), pd.Timestamp(now_utc())
    history = as_of(load_matches(), cutoff)
    elo = Elo(cfg)
    for match in history.sort_values(["available_at", "match_id"]).itertuples():
        elo.update(match)
    leagues = read_json(ROOT / "config/forward.json")["sports"].values()
    dc = {}
    for league in leagues:
        fitted = DixonColes(cfg).fit(history[history["div"] == league], cutoff)
        dc[league] = {
            "teams": fitted.teams,
            "theta": fitted.theta.tolist(),
            "diagnostics": fitted.diagnostics,
        }
    # Reuse the pre-test expanding fit: no holdout labels choose or fit blend coefficients.
    training = joined_features("validation")
    blend = OffsetBlend(cfg["blend_ridge"]).fit(
        training, pd.Timestamp(year=cfg["test_season"], month=7, day=1, tz="UTC")
    )
    result = {
        "source_commit": git("rev-parse", "HEAD"),
        "registration_commit": git("rev-list", "-n", "1", "forward-v1"),
        "strategy_sha": digest(cfg),
        "candidate": selection["candidate"],
        "trained_at": cutoff.isoformat(),
        "feature_max_available": history.available_at.max().isoformat(),
        "private_training_sha": file_sha(PROCESSED),
        "dc": dc,
        "elo": [[div, team, rating] for (div, team), rating in sorted(elo.ratings.items())],
        "blend_theta": blend.theta.tolist(),
        "policy": "Fixed v1 parameters; historical refits differ from this forward snapshot",
    }
    result["artifact_sha"] = digest(result)
    write_json(ARTIFACT, result)
    return {k: result[k] for k in ["artifact_sha", "trained_at", "source_commit", "policy"]}


def predict(artifact, league, home, away, raw_prices, cfg):
    if artifact["strategy_sha"] != digest(strategy()):
        raise ValueError("Fitted parameters belong to a different strategy")
    unsigned = {k: v for k, v in artifact.items() if k != "artifact_sha"}
    if artifact["artifact_sha"] != digest(unsigned):
        raise ValueError("Fitted parameter hash mismatch")
    aliases = read_json(ROOT / "config/team_aliases.json")
    home, away = aliases.get(home, home), aliases.get(away, away)
    dc = DixonColes(cfg)
    dc.teams, dc.theta = artifact["dc"][league]["teams"], np.array(artifact["dc"][league]["theta"])
    elo = Elo(cfg)
    elo.ratings = {(d, team): r for d, team, r in artifact["elo"]}
    # Unknown names fail closed instead of silently predicting a neutral club.
    if home not in dc.teams or away not in dc.teams:
        raise ValueError("Unknown team alias; no forecast emitted")
    values = {}
    for name, p in [
        ("dc", dc.predict(home, away)),
        ("elo", elo.predict(league, home, away)),
        ("market", devig(raw_prices)),
    ]:
        values.update({name + "_" + side: x for side, x in zip(SIDES, p, strict=True)})
    features = pd.DataFrame([values])
    if cfg["model"] == "blend":
        fitted = OffsetBlend(cfg["blend_ridge"])
        fitted.theta = np.array(artifact["blend_theta"])
        return fitted.predict(features)[0]
    return probability_matrix(features, cfg["model"])[0]
