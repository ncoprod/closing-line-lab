import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve

from .common import REGISTRATION_TAG, ROOT, now_utc, read_json, strategy, write_json
from .ledger import read_ledger, replay_account
from .metrics import block_ci, clv_inference, deflated_sharpe, power_analysis, scores
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
                    "fair_log_clv": row.get("fair_log_clv"),
                    "same_book_log_clv": row.get("same_book_log_clv"),
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


def dashboard(bets, summary):
    from matplotlib.dates import AutoDateLocator, ConciseDateFormatter

    fig = plt.figure(figsize=(11, 6.6), layout="constrained")
    grid = fig.add_gridspec(3, 2, height_ratios=[0.7, 2.5, 0.65])
    header = fig.add_subplot(grid[0, :])
    header.set_axis_off()
    mean = summary["clv"]["mean"]
    metrics = [
        ("Forecasts", str(summary["forecasts"])),
        ("Paper bets", str(summary["paper_bets"])),
        ("CLV sample (settled + close)", str(summary["clv"]["observations"])),
        ("Mean log CLV", "Not estimable" if mean is None else f"{mean:.5f}"),
    ]
    for x, (label, value) in zip([0.02, 0.26, 0.50, 0.77], metrics, strict=True):
        header.text(x, 0.82, label, fontsize=11, transform=header.transAxes)
        header.text(x, 0.20, value, fontsize=19, weight="bold", transform=header.transAxes)
    axes = [fig.add_subplot(grid[1, i]) for i in range(2)]
    for axis, field, title, color in zip(
        axes,
        ["log_clv", "profit_units"],
        ["Cumulative log CLV", "Cumulative paper profit (units)"],
        ["#235789", "#975D17"],
        strict=True,
    ):
        frame = bets.loc[bets[field].notna()].copy() if not bets.empty else bets
        axis.set_title(title, loc="left", fontsize=12, pad=15)
        if frame.empty:
            axis.text(
                0.5,
                0.52,
                "No eligible settled bets",
                transform=axis.transAxes,
                ha="center",
                va="center",
                fontsize=13,
            )
            axis.text(
                0.5,
                0.38,
                "No performance estimate yet",
                transform=axis.transAxes,
                ha="center",
                va="center",
                fontsize=11,
                color="#555555",
            )
            axis.set_xticks([])
            axis.set_yticks([])
        else:
            frame = frame.sort_values(["recorded_at", "match_id"])
            axis.plot(
                pd.to_datetime(frame.recorded_at, utc=True),
                frame[field].cumsum(),
                color=color,
                marker="o",
                linewidth=1.6,
            )
            axis.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
            locator = AutoDateLocator(minticks=2, maxticks=4)
            axis.xaxis.set_major_locator(locator)
            axis.xaxis.set_major_formatter(ConciseDateFormatter(locator))
            axis.set_xlabel("Settlement recorded (UTC)")
    footer = fig.add_subplot(grid[2, :])
    footer.set_axis_off()
    captured = (summary.get("latest_capture") or {}).get("checked_at", "not recorded")
    note = (
        f"Capture: {captured}\n"
        f"Pending forecasts: {summary['pending_forecasts']} | "
        f"Settled bets: {summary['settled_bets']} | "
        f"Settled bets missing a close: {summary['clv_missing']}"
    )
    usage, limits = summary.get("api_budget"), summary.get("api_budget_limits")
    if usage and limits:
        month = summary["checked_at"][:7]
        note += (
            f"\nCredits {month}: {usage['months'].get(month, 0)}/"
            f"{limits['monthly_credit_cap']} charged | "
            f"{usage['remaining']} provider balance | {limits['provider_reserve']} reserved"
        )
    footer.text(0.01, 0.95, note, va="top", fontsize=10, linespacing=1.6)
    fig.suptitle("Forward paper test | registered strategy", fontsize=15, weight="bold")
    fig.savefig(ROOT / "results/forward_dashboard.png", dpi=160)
    plt.close(fig)


def generate():
    records, cfg = read_ledger(), strategy()
    bets, resolved = forward_tables(records)
    forecasts = [r for r in records if r["kind"] == "forecast"]
    settlements = [r for r in records if r["kind"] == "settlement"]
    report = {
        "source_commit": git("rev-parse", "HEAD"),
        "checked_at": now_utc().isoformat(),
        "forecasts": len(forecasts),
        "paper_bets": sum(r["bet"] is not None for r in forecasts),
        "settled_bets": len(bets),
        "settled_forecasts": sum(r["status"] == "SETTLED" for r in settlements),
        "scored_forecasts": len(resolved),
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
    eligible = bets[bets.log_clv.notna()] if not bets.empty else bets
    report["primary_inference"] = (
        clv_inference(eligible.log_clv, eligible.block) if len(eligible) else clv_inference([], [])
    )
    corrections = ROOT / "results/review_corrections.json"
    corrected = read_json(corrections) if corrections.exists() else {}
    for metric in ["fair_log_clv", "same_book_log_clv"]:
        eligible = bets[bets[metric].notna()] if not bets.empty else bets
        report[metric] = (
            block_ci(eligible[metric], eligible.block) if len(eligible) else block_ci([], [])
        )
    closes = [r for r in records if r["kind"] == "closing_snapshot"]
    report["closing_snapshots"] = len(closes)
    report["closing_benchmark_counts"] = {
        book: sum(r["bookmaker"] == book for r in closes)
        for book in sorted({r["bookmaker"] for r in closes})
    }
    report["closing_gap_minutes"] = (
        {
            "min": min(r["snapshot_gap_minutes"] for r in closes),
            "max": max(r["snapshot_gap_minutes"] for r in closes),
            "mean": float(np.mean([r["snapshot_gap_minutes"] for r in closes])),
        }
        if closes
        else None
    )
    usage = ROOT / "data/api_usage.json"
    report["api_budget"] = (
        {k: read_json(usage)[k] for k in ("months", "remaining", "provider_used")}
        if usage.exists()
        else None
    )
    limits = ROOT / "config/forward.json"
    report["api_budget_limits"] = (
        {k: read_json(limits)[k] for k in ("monthly_credit_cap", "provider_reserve")}
        if limits.exists()
        else None
    )
    capture = ROOT / "results/latest_forward_run.json"
    report["latest_capture"] = read_json(capture) if capture.exists() else None
    if resolved:
        from .metrics import devig

        closing = devig([r["closing"] for r in resolved])
        outcomes = [r["outcome"] for r in resolved]
        report["scores"] = scores([r["p"] for r in resolved], outcomes, closing)
        report["closing_baseline"] = scores(closing, outcomes, closing)
        report["log_loss_gap"] = (
            report["scores"]["log_loss"] - report["closing_baseline"]["log_loss"]
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
    dashboard(bets, report)
    enabled = (ROOT / "config/fitted_model.json").exists() and bool(
        git("tag", "-l", REGISTRATION_TAG)
    )
    test_path = ROOT / "results/test.json"
    validation_path = ROOT / "results/validation.json"
    write_json(
        ROOT / "results/comparison.json",
        {
            "source_commit": report["source_commit"],
            "test": corrected.get("test", read_json(test_path))["reports"][0]
            if test_path.exists()
            else None,
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
                    "primary_inference",
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
        f"| CLV denominator (settled bets with closing prices) | {report['clv']['observations']} |",
        f"| Descriptive date-bootstrap quantiles | {report['clv']['ci95'] or 'NOT_ESTIMABLE'} |",
        f"| CLV inference (disabled for this pilot) | {report['primary_inference']['status']} |",
        f"| Paper profit (initial account 100 units) | {report['profit_units']} |",
        f"| Pending / void forecasts | {report['pending_forecasts']} / "
        f"{report['void_forecasts']} |",
        "",
    ]
    if validation_path.exists():
        selection = read_json(ROOT / "results/selection.json")["candidate"]
        validation = corrected.get("validation", read_json(validation_path))
        selected = next(r for r in validation["reports"] if r["candidate"] == selection)
        lines += [
            f"Validation selected **{selection['model']} / {selection['min_edge']} minimum edge**: "
            f"{selected['model']['matches']} scored matches, log loss "
            f"{selected['model']['log_loss']} versus closing "
            f"{selected['closing_baseline']['log_loss']} "
            f"(gap {selected['log_loss_gap']}).",
            f"Only {selected['bets']} paper bets; mean log CLV {selected['clv']['mean']}, "
            f"descriptive date-bootstrap quantiles {selected['clv']['ci95']}. "
            "These are not calibrated confidence limits. "
            "The selected rule's sparse bets severely limit forward power.",
            "",
            "| Validation model | Minimum edge | Log loss | Paper bets | Mean log CLV |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {r['candidate']['model']} | {r['candidate']['min_edge']} | "
                f"{r['model']['log_loss']} | {r['bets']} | {r['clv']['mean']} |"
                for r in validation["reports"]
            ],
            "",
        ]
    if test_path.exists():
        test = corrected.get("test", read_json(test_path))["reports"][0]
        lines += [
            f"Held-out test: {test['model']['matches']} scored matches; "
            f"log-loss gap to closing {test['log_loss_gap']}; "
            f"{test['bets']} paper bets; mean log CLV {test['clv']['mean']}, "
            f"descriptive bootstrap quantiles {test['clv']['ci95']}. "
            f"Paper P&L {test['profit_units']} units; ROI {test['roi']}.",
            f"Test DSR: {test['deflated_sharpe'].get('status', 'NOT_ESTIMABLE')} "
            f"({test['deflated_sharpe'].get('nonzero_days', 2)} nonzero return days). "
            "Power planning (one-sided 5%, 80%): "
            f"{test['power'].get('required_bets', 'NOT_ESTIMABLE')} "
            "bets by log-CLV basis-point effect; sparse-sample estimates are unstable.",
            "",
        ]
    lines += [
        "Sources: [status](results/status.json), [validation](results/validation.json), "
        "[original test](results/test.json), "
        "[corrected replay](results/review_corrections.json), [forward](results/forward.json).",
        "![Forward-test dashboard: counts, CLV denominator, paper profit and credit budget]"
        "(results/forward_dashboard.png)",
        "![Forward calibration](results/calibration.png)",
    ]
    readme = ROOT / "README.md"
    text = readme.read_text()
    start, rest = text.split("<!-- RESULTS:START -->", 1)
    _, end = rest.split("<!-- RESULTS:END -->", 1)
    text = start + "<!-- RESULTS:START -->\n" + "\n".join(lines) + "\n<!-- RESULTS:END -->" + end
    evidence_path = ROOT / "results/actions_evidence.json"
    if evidence_path.exists():
        evidence = read_json(evidence_path)
        operations = (
            f"GitHub: **{evidence['successful_scheduled_runs']} successful scheduled runs**, "
            f"checked {evidence['checked_at']}. "
            "[Live evidence](results/actions_evidence.json) lists every schedule event, "
            "separately from manual runs."
        )
        local_path = ROOT / "results/local_runner.json"
        health_path = ROOT / "results/forward_health.json"
        if health_path.exists():
            health = read_json(health_path)
            launchd, publication, budget = (health[k] for k in ("launchd", "publication", "budget"))
            operations += (
                f" Mac log: **{launchd['completed_cycles']} completed hourly cycles**; "
                f"{publication['receipted_forecasts']}/{publication['forecasts']} forecasts "
                f"have pre-kickoff receipts. Credits charged: {budget['charged']}/{budget['cap']}; "
                f"provider balance {budget['remaining']}, reserve {budget['reserve']}. "
                f"Health checked {health['checked_at']}. "
                "[Health evidence](results/forward_health.json); refresh with `make health`."
            )
        elif local_path.exists():
            local = read_json(local_path)
            operations += (
                f" Mac launchd: **{local['verified_runs']} verified real run**, "
                f"exit code {local['exit_code']}, checked {local['checked_at']}. "
                "[Installation/run evidence](results/local_runner.json)."
            )
        if test_path.exists():
            tldr = (
                f"**TL;DR:** Held-out blend log loss {test['model']['log_loss']:.6f}; "
                f"closing benchmark {test['closing_baseline']['log_loss']:.6f}.\n"
                f"{test['bets']} historical paper bets; mean log CLV {test['clv']['mean']:.6f}; "
                "no demonstrated edge.\n"
                f"Forward: {report['forecasts']} forecasts, {report['paper_bets']} paper bets; "
                f"CLV n={report['clv']['observations']} "
                f"({'not estimable' if report['clv']['mean'] is None else report['clv']['mean']}). "
                "[Sources](results/review_corrections.json) · "
                "[Forward](results/forward.json) · [Operations](results/actions_evidence.json)."
            )
            text = replace_block(text, "TLDR", tldr)
        text = replace_block(text, "OPERATIONS", operations)
    readme.write_text(text)
    return status


def replace_block(text, marker, content):
    begin, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    if begin not in text:
        return text
    before, rest = text.split(begin, 1)
    _, after = rest.split(end, 1)
    return before + begin + "\n" + content + "\n" + end + after


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
    pages = json.loads(
        subprocess.check_output(
            [
                "gh",
                "api",
                "--paginate",
                "--slurp",
                f"repos/{REPO}/actions/workflows/paper.yml/runs?event=schedule&per_page=100",
            ],
            text=True,
        )
    )
    scheduled = [
        {
            k: r[k]
            for k in ("id", "event", "head_sha", "created_at", "status", "conclusion", "html_url")
        }
        for page in pages
        for r in page["workflow_runs"]
        if r["head_branch"] == "main"
    ]
    evidence = {
        "checked_at": now_utc().isoformat(),
        "runs": runs,
        "scheduled_runs": scheduled,
        "successful_scheduled_runs": sum(r["conclusion"] == "success" for r in scheduled),
        "note": (
            "All main-branch paper.yml schedule events are paginated separately from the "
            "latest 50 general runs. Run success alone is not proof of an on-time "
            "forecast; see ledger verification and actual forecast counts."
        ),
    }
    write_json(ROOT / "results/actions_evidence.json", evidence)
    return evidence


def research_report():
    """Publish aggregate bins and monthly paths; historical rows remain local."""
    from .metrics import devig

    selection = read_json(ROOT / "results/selection.json")["candidate"]
    summaries = {}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
    path_fig, path_axes = plt.subplots(2, 1, figsize=(9, 6), layout="constrained")
    for stage, axis in zip(["validation", "test"], axes, strict=True):
        name = f"{stage}_{selection['model']}_{selection['min_edge']:.2f}"
        path = ROOT / f"results/{name}_predictions.csv.gz"
        if not path.exists():
            axis.text(0.5, 0.5, f"{stage}: not evaluated", transform=axis.transAxes, ha="center")
            continue
        frame = pd.read_csv(path)
        close = frame[["AvgC" + s for s in "HDA"]].to_numpy(float)
        mask = np.isfinite(close).all(1) & (close > 1).all(1) & frame.outcome.notna()
        frame, close = frame[mask], close[mask]
        probabilities = frame[["p" + s for s in "HDA"]].to_numpy(float)
        closing = devig(close)
        labels = frame.outcome.to_numpy(int)
        bins = []
        for side, label, color in zip(
            range(3), ["Home", "Draw", "Away"], ["#235789", "#975D17", "#A94D83"], strict=True
        ):
            groups = pd.qcut(probabilities[:, side], q=8, duplicates="drop")
            data = pd.DataFrame(
                {"predicted": probabilities[:, side], "observed": labels == side, "bin": groups}
            )
            grouped = data.groupby("bin", observed=True).agg(
                predicted=("predicted", "mean"),
                observed=("observed", "mean"),
                count=("observed", "size"),
            )
            axis.plot(grouped.predicted, grouped.observed, "o-", color=color, label=label)
            bins += [{"side": label, **r} for r in grouped.to_dict("records")]
        axis.plot([0, 1], [0, 1], "--", color="#666666", linewidth=0.8)
        axis.set(
            xlim=(0, 1),
            ylim=(0, 1),
            xlabel="Predicted probability",
            ylabel="Observed frequency",
            title=f"{stage.capitalize()} calibration; quantile bins",
        )
        axis.legend()
        per_match_gap = -np.log(probabilities[np.arange(len(labels)), labels]) + np.log(
            closing[np.arange(len(labels)), labels]
        )
        summaries[stage] = {
            "calibration_bins": bins,
            "scored_matches": len(frame),
            "log_loss_gap_ci": block_ci(per_match_gap, frame.kickoff_utc.str[:10]),
        }
        bets = pd.read_csv(ROOT / f"results/{name}_bets.csv")
        if bets.empty:
            continue
        monthly = (
            bets.assign(month=bets.kickoff_utc.str[:7])
            .groupby("month")
            .agg(
                bets=("log_clv", "size"), clv_sum=("log_clv", "sum"), profit=("profit_units", "sum")
            )
        )
        summaries[stage]["monthly_bets"] = monthly.reset_index().to_dict("records")
        x = pd.to_datetime(monthly.index + "-01")
        path_axes[0].plot(x, monthly.clv_sum.cumsum(), "o-", label=stage)
        path_axes[1].plot(x, monthly.profit.cumsum(), "o-", label=stage)
    fig.savefig(ROOT / "results/historical_calibration.png", dpi=150)
    plt.close(fig)
    path_axes[0].set_ylabel("Cumulative log CLV")
    path_axes[1].set_ylabel("Paper profit (units)")
    path_axes[1].set_xlabel("Kickoff month (UTC); months with bets")
    for axis in path_axes:
        axis.axhline(0, color="#666666", linewidth=0.8)
        axis.legend()
    path_fig.suptitle("Selected strategy: historical snapshot proxies")
    path_fig.savefig(ROOT / "results/historical_paths.png", dpi=150)
    plt.close(path_fig)
    result = {
        "source_commit": git("rev-parse", "HEAD"),
        "candidate": selection,
        "stages": summaries,
        "warning": "Historical timing proxies; sparse bets limit inference",
    }
    write_json(ROOT / "results/historical_analysis.json", result)
    return result
