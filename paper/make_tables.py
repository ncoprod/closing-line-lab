"""Build paper tables, macros and figures exclusively from committed aggregate artifacts."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper/generated"
SOURCES = {}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def read(path):
    payload = git("show", f"HEAD:{path}")
    SOURCES[path] = hashlib.sha256(payload).hexdigest()
    return json.loads(payload)


def number(x, digits=6):
    return "---" if x is None else f"{x:.{digits}f}"


def table(name, columns, header, rows):
    body = "\\begin{tabular}{" + columns + "}\n\\toprule\n"
    body += " & ".join(header) + " \\\\\n\\midrule\n"
    body += "\n".join(" & ".join(row) + " \\\\" for row in rows)
    body += "\n\\bottomrule\n\\end{tabular}\n"
    (OUT / f"{name}.tex").write_text(body)


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    corrected = read("results/review_corrections.json")
    validation = corrected["validation"]["reports"]
    test = corrected["test"]["reports"][0]
    selected = validation[-1]
    historical = read("results/historical_analysis.json")["stages"]
    quality = read("results/data_quality.json")
    forward = read("results/forward.json")
    nulls = [
        read("results/null_calibration_candidate1.json"),
        read("results/null_calibration.json"),
    ]
    power = read("results/power_analysis.json")
    read("config/strategy.json")
    forward_cfg = read("config/forward.json")
    evidence = read("results/actions_evidence.json")
    engineering = read("results/engineering.json")
    manifest = git("show", "HEAD:data/manifest.jsonl")
    SOURCES["data/manifest.jsonl"] = hashlib.sha256(manifest).hexdigest()
    macros = {
        "researchRows": str(quality["matches"]),
        "rawFiles": str(len(manifest.splitlines())),
        "valMatches": str(selected["model"]["matches"]),
        "testMatches": str(test["model"]["matches"]),
        "valBets": str(selected["bets"]),
        "testBets": str(test["bets"]),
        "testLoss": number(test["model"]["log_loss"]),
        "closingLoss": number(test["closing_baseline"]["log_loss"]),
        "testGap": number(test["log_loss_gap"]),
        "testClv": number(test["clv"]["mean"]),
        "testProfit": number(test["profit_units"]),
        "valClv": number(selected["clv"]["mean"]),
        "forwardForecasts": str(forward["forecasts"]),
        "forwardBets": str(forward["paper_bets"]),
        "settledForwardBets": str(forward["settled_bets"]),
        "scheduledRuns": str(evidence["successful_scheduled_runs"]),
        "testNonzeroDays": str(test["deflated_sharpe"]["nonzero_days"]),
        "testCalendarDays": str(test["deflated_sharpe"]["days"]),
        "powerTen": str(power["selected_validation"]["required_bets"]["10"]),
        "replayError": f"{corrected['maximum_prediction_deviation']:.3g}",
        "testsPassed": str(engineering["tests"]),
        "sourceCommit": git("rev-parse", "HEAD").decode().strip(),
        "registrationCommit": git("rev-parse", "forward-v1.3^{}").decode().strip(),
        "originalCommit": git("rev-parse", "forward-v1^{}").decode().strip(),
        "replayCommit": corrected["source_commit"],
        "effectThreshold": number(selected["candidate"]["min_edge"], 2),
        "creditCap": str(forward_cfg["monthly_credit_cap"]),
        "creditReserve": str(forward_cfg["provider_reserve"]),
        "oldNullRate": number(nulls[1]["old_two_date_exact_null_rate"], 2),
        "candidateOneUpper": number(max(r["wilson95_upper"] for r in nulls[0]["scenarios"])),
        "candidateTwoUpper": number(max(r["wilson95_upper"] for r in nulls[1]["scenarios"])),
    }
    (OUT / "macros.tex").write_text(
        "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()) + "\n"
    )
    names = {"dc": "Dixon--Coles", "elo": "Elo", "market": "Market", "blend": "Blend"}
    table(
        "validation",
        "lrrrr",
        ["Model", "Edge", "Log loss", "Bets", "Mean log CLV"],
        [
            [
                names[r["candidate"]["model"]],
                number(r["candidate"]["min_edge"], 2),
                number(r["model"]["log_loss"]),
                str(r["bets"]),
                number(r["clv"]["mean"]),
            ]
            for r in validation
        ],
    )
    rows = []
    for label, r in [("Validation", selected), ("Test", test)]:
        for model, field in [("blend", "model"), ("close", "closing_baseline")]:
            rows.append(
                [
                    f"{label}: {model}",
                    str(r[field]["matches"]),
                    number(r[field]["log_loss"]),
                    number(r[field]["brier"]),
                ]
            )
    table("scores", "lrrr", ["Population / forecast", "Matches", "Log loss", "Brier"], rows)
    rows = []
    for label, field in [("Settled bets", "bets"), ("Pending bets", "pending_bets")]:
        rows.append([label, str(selected[field]), str(test[field])])
    for label, fn in [
        ("Mean log CLV", lambda r: r["clv"]["mean"]),
        ("Bootstrap 2.5\\% quantile", lambda r: r["clv"]["ci95"][0]),
        ("Bootstrap 97.5\\% quantile", lambda r: r["clv"]["ci95"][1]),
        ("Paper profit (units)", lambda r: r["profit_units"]),
        ("ROI on settled stakes", lambda r: r["roi"]),
    ]:
        rows.append([label, number(fn(selected)), number(fn(test))])
    rows.append(
        [
            "Nonzero return days",
            str(selected["deflated_sharpe"]["nonzero_days"]),
            str(test["deflated_sharpe"]["nonzero_days"]),
        ]
    )
    rows.append(["DSR inference", "Not estimable", "Not estimable"])
    table("bets", "lrr", ["Selected-rule quantity", "Validation", "Test"], rows)
    table(
        "nulls",
        "lrrrrl",
        ["Candidate", "Min. weeks", "Critical parameter", "Max. FPR", "Upper bound", "Screen"],
        [
            [
                str(i),
                str(r["policy"]["min_weeks"]),
                number(r["policy"]["confidence_parameter"], 3),
                number(max(s["false_positive_rate"] for s in r["scenarios"])),
                number(max(s["wilson95_upper"] for s in r["scenarios"])),
                r["status"],
            ]
            for i, r in enumerate(nulls, 1)
        ],
    )
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), layout="constrained")
    for stage, axis in zip(["validation", "test"], axes, strict=True):
        bins = historical[stage]["calibration_bins"]
        for side, marker in zip(["Home", "Draw", "Away"], ["o", "s", "^"], strict=True):
            points = [r for r in bins if r["side"] == side]
            axis.plot(
                [r["predicted"] for r in points],
                [r["observed"] for r in points],
                marker + "-",
                label=side,
                markersize=4,
            )
        axis.plot([0, 1], [0, 1], "--", color="gray", linewidth=0.8)
        axis.set(
            xlim=(0, 1),
            ylim=(0, 1),
            xlabel="Predicted probability",
            ylabel="Observed frequency",
            title=stage.capitalize(),
        )
        axis.legend(fontsize=8)
    fig.savefig(OUT / "calibration.png", dpi=180)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(7.8, 3.1), layout="constrained")
    x = np.arange(len(nulls[0]["scenarios"]))
    for i, result in enumerate(nulls):
        axis.plot(
            x,
            [r["wilson95_upper"] for r in result["scenarios"]],
            "o-",
            markersize=3,
            label=f"Candidate {i + 1}",
        )
    axis.axhline(0.05, color="black", linestyle="--", label="Screen threshold")
    axis.set(
        xlabel="Synthetic null scenario (ordered by weeks, shock family, AR coefficient)",
        ylabel="Wilson upper FPR bound",
        ylim=(0, 0.15),
    )
    axis.legend(fontsize=8)
    fig.savefig(OUT / "null_screen.png", dpi=180)
    plt.close(fig)
    (OUT / "provenance.json").write_text(
        json.dumps(
            {
                "input_commit": macros["sourceCommit"],
                "sha256": SOURCES,
                "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "display": "Round to nearest, six decimals unless units require otherwise",
            },
            indent=2,
        )
        + "\n"
    )
    print("Generated paper assets from committed artifacts at", macros["sourceCommit"])


if __name__ == "__main__":
    main()
