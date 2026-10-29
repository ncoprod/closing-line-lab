import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

from .common import ROOT, now_utc, read_json, strategy, write_json
from .ledger import read_ledger, replay_account
from .metrics import block_ci, deflated_sharpe, power_analysis, scores
from .research import TRIALS, daily_returns, git


def forward_tables(records):
    forecasts = {r["match_id"]: r for r in records if r["kind"] == "forecast"}
    bets, resolved = [], []
    for row in records:
        if row["kind"] != "settlement" or row["status"] != "SETTLED":
            continue
        forecast = forecasts[row["match_id"]]
        if row["closing_prices"] is not None:
            resolved.append(
                {
                    "p": forecast["probabilities"],
                    "outcome": row["outcome"],
                    "closing": row["closing_prices"],
                }
            )
        if forecast["bet"] is not None:
            bets.append(
                {
                    "match_id": row["match_id"],
                    "kickoff_utc": forecast["kickoff_utc"],
                    "block": forecast["kickoff_utc"][:10],
                    "recorded_at": row["recorded_at"],
                    "settled_at": row["recorded_at"],
                    "log_clv": row["log_clv"],
                    "profit_units": row["profit_units"],
                    "stake_units": forecast["bet"]["stake_units"],
                }
            )
    return pd.DataFrame(bets), resolved


def figures(bets, resolved):
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), layout="constrained")
    if bets.empty:
        for axis, label in zip(axes, ["Cumulative log CLV", "Paper profit (units)"], strict=True):
            axis.set_ylabel(label)
            axis.text(
                0.5,
                0.5,
                "No settled forward paper bets",
                transform=axis.transAxes,
                ha="center",
                va="center",
            )
            axis.set_xticks([])
            axis.set_yticks([])
    else:
        plotted = bets.sort_values(["recorded_at", "match_id"])
        x = pd.to_datetime(plotted.recorded_at, utc=True)
        axes[0].plot(x, plotted.log_clv.cumsum(), color="#235789")
        axes[1].plot(x, plotted.profit_units.cumsum(), color="#975D17")
        axes[0].set_ylabel("Cumulative log CLV")
        axes[1].set_ylabel("Paper profit (units)")
        axes[1].set_xlabel("Settlement recorded (UTC)")
        for axis in axes:
            axis.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
    fig.suptitle("Forward paper observations")
    fig.savefig(ROOT / "results/forward.png", dpi=150)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(6, 5), layout="constrained")
    axis.plot([0, 1], [0, 1], "--", color="#555555", label="Perfect calibration")
    if resolved:
        probabilities = np.array([r["p"] for r in resolved])
        outcomes = np.array([r["outcome"] for r in resolved])
        for side, label, color, marker in zip(
            range(3),
            ["Home", "Draw", "Away"],
            ["#235789", "#975D17", "#A94D83"],
            ["o", "s", "^"],
            strict=True,
        ):
            observed, predicted = calibration_curve(
                outcomes == side, probabilities[:, side], n_bins=8, strategy="quantile"
            )
            axis.plot(predicted, observed, marker=marker, color=color, label=label)
    else:
        axis.text(
            0.5,
            0.3,
            "No settled forward forecasts",
            ha="center",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 4},
        )
    axis.set(
        xlim=(0, 1),
        ylim=(0, 1),
        xlabel="Predicted probability",
        ylabel="Observed frequency",
        title="Forward calibration (descriptive; quantile bins)",
    )
    axis.legend()
    fig.savefig(ROOT / "results/calibration.png", dpi=150)
    plt.close(fig)


def generate():
    records, cfg = read_ledger(), strategy()
    bets, resolved = forward_tables(records)
    forecasts = [r for r in records if r["kind"] == "forecast"]
    settlements = [r for r in records if r["kind"] == "settlement"]
    report = {
        "source_commit": git("rev-parse", "HEAD"),
        "forecasts": len(forecasts),
        "paper_bets": sum(r["bet"] is not None for r in forecasts),
        "settled_bets": len(bets),
        "settled_forecasts": len(resolved),
        "void_forecasts": sum(r["status"].startswith("VOID") for r in settlements),
        "pending_forecasts": len(forecasts) - len(settlements),
        "clv_missing": int(bets.log_clv.isna().sum()) if not bets.empty else 0,
        "clv": block_ci(
            bets.loc[bets.log_clv.notna(), "log_clv"],
            bets.loc[bets.log_clv.notna(), "block"],
            cfg["bootstrap_samples"],
            cfg["seed"],
        )
        if not bets.empty
        else block_ci([], []),
        "profit_units": float(bets.profit_units.sum()) if not bets.empty else 0.0,
        "roi": float(bets.profit_units.sum() / bets.stake_units.sum()) if not bets.empty else None,
        "account": replay_account(records),
        "power": power_analysis(
            bets.loc[bets.log_clv.notna(), "log_clv"], bets.loc[bets.log_clv.notna(), "block"]
        )
        if not bets.empty
        else power_analysis([], []),
    }
    if resolved:
        from .metrics import devig

        report["scores"] = scores(
            [r["p"] for r in resolved],
            [r["outcome"] for r in resolved],
            devig([r["closing"] for r in resolved]),
        )
    validation = ROOT / "results/validation.json"
    trial_sharpes = (
        [
            r["deflated_sharpe"]["daily_sharpe"]
            for r in read_json(validation)["reports"]
            if "daily_sharpe" in r["deflated_sharpe"]
        ]
        if validation.exists()
        else []
    )
    returns = (
        daily_returns(
            bets,
            pd.Timestamp(forecasts[0]["decision_at"]).floor("D"),
            pd.Timestamp(now_utc()).floor("D"),
        )
        if not bets.empty
        else []
    )
    trial_count = len(TRIALS.read_text().splitlines()) if TRIALS.exists() else 0
    report["deflated_sharpe"] = deflated_sharpe(returns, trial_sharpes, trial_count)
    write_json(ROOT / "results/forward.json", report)
    figures(bets, resolved)
    enabled = (ROOT / "config/fitted_model.json").exists() and bool(git("tag", "-l", "forward-v1"))
    test_path = ROOT / "results/test.json"
    validation_path = ROOT / "results/validation.json"
    write_json(
        ROOT / "results/comparison.json",
        {
            "source_commit": report["source_commit"],
            "test": read_json(test_path)["reports"][0] if test_path.exists() else None,
            "forward": {
                key: report[key]
                for key in [
                    "forecasts",
                    "paper_bets",
                    "settled_bets",
                    "clv",
                    "profit_units",
                    "roi",
                    "deflated_sharpe",
                    "power",
                ]
            },
            "status": "COMPARABLE"
            if test_path.exists() and not bets.empty
            else "NOT_COMPARABLE_YET",
            "caveat": "Snapshot quotes do not establish executable prices.",
        },
    )
    status = {
        "status": "FROZEN_MODEL_READY" if enabled else "PREPARING_MODEL",
        "real_data_matches": read_json(ROOT / "results/data_quality.json")["matches"]
        if (ROOT / "results/data_quality.json").exists()
        else 0,
        "forecasts": len(forecasts),
        "paper_bets": report["paper_bets"],
        "settled_bets": len(bets),
        "backtest": "COMPLETE" if validation_path.exists() else "NOT_RUN",
        "test_season": "EVALUATED_ONCE" if test_path.exists() else "UNEVALUATED",
        "reason": None
        if enabled
        else ("Local research authorized; forward model export/freeze not yet complete."),
    }
    write_json(ROOT / "results/status.json", status)
    lines = [
        f"**{status['real_data_matches']} research dataset rows; "
        f"{len(forecasts)} forward forecasts; "
        f"{report['paper_bets']} paper bets; {len(bets)} settled bets.**",
        f"Data status: **{status['status']}**. Validation: **{status['backtest']}**. "
        f"Test season: **{status['test_season']}**.",
        "",
        "| Forward metric | Observed value |",
        "|---|---:|",
        "| Mean log CLV | "
        f"{report['clv']['mean'] if report['clv']['mean'] is not None else 'NOT_ESTIMABLE'} |",
        f"| 95% date-block bootstrap CI | {report['clv']['ci95'] or 'NOT_ESTIMABLE'} |",
        f"| Paper profit (initial account 100 units) | {report['profit_units']} |",
        f"| Pending / void forecasts | {report['pending_forecasts']} / "
        f"{report['void_forecasts']} |",
        "",
    ]
    if test_path.exists():
        test = read_json(test_path)["reports"][0]
        lines += [
            f"Held-out test: {test['model']['matches']} scored matches; "
            f"log-loss gap to closing {test['log_loss_gap']}; "
            f"mean log CLV {test['clv']['mean']}, 95% CI {test['clv']['ci95']}.",
            "",
        ]
    lines += [
        "Source: [status](results/status.json), [forward results](results/forward.json).",
        "![Cumulative forward CLV and paper profit](results/forward.png)",
        "![Forward calibration](results/calibration.png)",
    ]
    readme = ROOT / "README.md"
    text = readme.read_text()
    start, rest = text.split("<!-- RESULTS:START -->", 1)
    _, end = rest.split("<!-- RESULTS:END -->", 1)
    readme.write_text(
        start + "<!-- RESULTS:START -->\n" + "\n".join(lines) + "\n<!-- RESULTS:END -->" + end
    )
    return status


def actions_evidence():
    import subprocess

    from .ledger import REPO

    output = subprocess.check_output(
        [
            "gh",
            "run",
            "list",
            "--repo",
            REPO,
            "--limit",
            "50",
            "--json",
            "databaseId,workflowName,event,headSha,createdAt,status,conclusion,url",
        ],
        text=True,
    )
    runs = json.loads(output)
    evidence = {
        "checked_at": now_utc().isoformat(),
        "runs": runs,
        "successful_scheduled_runs": sum(
            r["event"] == "schedule" and r["conclusion"] == "success" for r in runs
        ),
        "note": (
            "A readiness-gated schedule success proves scheduling only; "
            "no data forecast was executed."
        ),
    }
    write_json(ROOT / "results/actions_evidence.json", evidence)
    return evidence
