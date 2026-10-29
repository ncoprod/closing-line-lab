"""Local reviewer replay writes separate outputs and never reselects or overwrites a freeze."""

import numpy as np
import pandas as pd

from .common import ROOT, file_sha, read_json, strategy, write_json
from .data import PROCESSED, load_matches, require_permission
from .metrics import clv_inference, deflated_sharpe
from .models import make_features
from .research import (
    candidates,
    daily_returns,
    evaluate,
    git,
    load_features,
    walk_forward_probabilities,
)


def replay(output_dir, rebuild_features=False):
    output = output_dir.resolve()
    if output == ROOT / "results" or ROOT / "results" in output.parents:
        raise ValueError("Replay must use a separate output directory, outside registered results")
    require_permission(training=True)
    cfg, history = strategy(), load_matches()
    output.mkdir(parents=True, exist_ok=True)
    stages = {}
    for stage in ["validation", "test"]:
        if rebuild_features:
            path = output / f"features_{stage}.csv.gz"
            maximum = cfg["test_season"] - (stage == "validation")
            past = history[history.season <= maximum]
            targets = (
                past[(past.season >= cfg["first_season"] + 3) & past.outcome.notna()]
                if stage == "validation"
                else past[past.season == cfg["test_season"]]
            )
            features = make_features(past, targets, cfg)
            features.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
        else:
            path = ROOT / f"data/processed/features_{stage}.csv.gz"
        stages[stage] = load_features(path)
    frame = pd.concat(list(stages.values())).merge(history, on="match_id", validate="one_to_one")
    predictions = {}
    results = {}
    validation_sharpes = []
    maximum_deviation = 0.0
    for stage in ["validation", "test"]:
        original = read_json(ROOT / f"results/{stage}.json")
        specs = (
            candidates(cfg)
            if stage == "validation"
            else [read_json(ROOT / "results/selection.json")["candidate"]]
        )
        reports, returns = [], []
        for spec in specs:
            if spec["model"] not in predictions:
                predictions[spec["model"]] = walk_forward_probabilities(frame, cfg, spec["model"])
            predicted = predictions[spec["model"]]
            predicted = (
                predicted[predicted.season.isin(cfg["validation_seasons"])]
                if stage == "validation"
                else predicted[
                    (predicted.season == cfg["test_season"])
                    & ~predicted.match_id.isin(cfg["test_excluded_ids"])
                ]
            )
            result, bets = evaluate(predicted, {**cfg, **spec})
            result["candidate"] = spec
            settled = bets[bets.profit_units.notna()] if len(bets) else bets
            valid = settled[settled.log_clv.notna()] if len(settled) else settled
            result["primary_inference"] = (
                clv_inference(valid.log_clv, valid.block) if len(valid) else clv_inference([], [])
            )
            name = f"{stage}_{spec['model']}_{spec['min_edge']:.2f}"
            saved = ROOT / f"results/{name}_predictions.csv.gz"
            if saved.exists():
                old = pd.read_csv(saved).set_index("match_id")
                a = predicted.set_index("match_id").loc[old.index, ["pH", "pD", "pA"]].to_numpy()
                maximum_deviation = max(
                    maximum_deviation, float(np.abs(a - old[["pH", "pD", "pA"]].to_numpy()).max())
                )
            old_report = next(r for r in original["reports"] if r["candidate"] == spec)
            checks = {
                k: bool(np.isclose(result[k], old_report[k], rtol=0, atol=1e-12))
                for k in ["log_loss_gap", "bets", "profit_units"]
            }
            checks["clv_mean"] = result["clv"]["mean"] == old_report["clv"]["mean"] or (
                result["clv"]["mean"] is not None
                and old_report["clv"]["mean"] is not None
                and bool(
                    np.isclose(result["clv"]["mean"], old_report["clv"]["mean"], rtol=0, atol=1e-12)
                )
            )
            result["unchanged_original_headlines"] = checks
            reports.append(result)
            returns.append(
                daily_returns(
                    bets,
                    predicted.decision_at.min().floor("D"),
                    predicted.available_at.max().floor("D"),
                )
            )
            predicted.to_csv(
                output / f"{name}_predictions.csv.gz",
                index=False,
                compression={"method": "gzip", "mtime": 0},
            )
            bets.to_csv(output / f"{name}_bets.csv", index=False)
        if stage == "validation":
            validation_sharpes = [
                float(r.mean() / r.std(ddof=1)) for r in returns if len(r) > 2 and r.std(ddof=1) > 0
            ]
        for report, series in zip(reports, returns, strict=True):
            report["deflated_sharpe"] = deflated_sharpe(
                series, validation_sharpes, original["trial_count"]
            )
        results[stage] = {
            "reports": reports,
            "original_report_sha256": file_sha(ROOT / f"results/{stage}.json"),
            "original_trial_count": original["trial_count"],
        }
    result = {
        "source_commit": git("rev-parse", "HEAD"),
        "data_sha256": file_sha(PROCESSED),
        "implementation_sha256": {
            str(path.relative_to(ROOT)): file_sha(path)
            for path in sorted((ROOT / "src/closing_line_lab").glob("*.py"))
        },
        "rebuild_features": rebuild_features,
        "maximum_prediction_deviation": maximum_deviation,
        "original_outputs_unchanged": all(
            all(r["unchanged_original_headlines"].values())
            for stage in results.values()
            for r in stage["reports"]
        ),
        "interpretation": (
            "Corrected companion; original tags, selection and reports are preserved. "
            "Bootstrap endpoints are descriptive quantiles; no sparse CLV/DSR inference."
        ),
        **results,
    }
    write_json(output / "replay.json", result)
    return result
