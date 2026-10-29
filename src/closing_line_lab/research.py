import heapq
import subprocess

import numpy as np
import pandas as pd

from .common import (
    REGISTRATION_TAG,
    ROOT,
    digest,
    file_sha,
    now_utc,
    read_json,
    strategy,
    write_json,
)
from .data import PROCESSED, load_matches, require_permission
from .metrics import block_ci, deflated_sharpe, devig, power_analysis, scores
from .models import SIDES, OffsetBlend, make_features, probability_matrix

TRIALS = ROOT / "results/trials.jsonl"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def register_trial(specification):
    import json

    record = {
        "registered_at": now_utc().isoformat(),
        "source_commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(git("status", "--porcelain")),
        **specification,
    }
    record["trial_id"] = digest(record)
    TRIALS.parent.mkdir(exist_ok=True)
    with TRIALS.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record["trial_id"]


def load_features(path):
    frame = pd.read_csv(path)
    for col in ["decision_at", "feature_max_available", "dc_fit_at"]:
        frame[col] = pd.to_datetime(frame[col], utc=True)
    return frame


def build_features(stage):
    if stage == "test":
        assert_frozen()
    require_permission(training=True)
    cfg, history = strategy(), load_matches()
    maximum = cfg["test_season"] - 1 if stage == "validation" else cfg["test_season"]
    history = history[history.season <= maximum]
    targets = history[(history.season >= cfg["first_season"] + 3) & history.outcome.notna()]
    if stage == "test":
        targets = history[history.season == cfg["test_season"]]
    features = make_features(history, targets, cfg)
    path = ROOT / f"data/processed/features_{stage}.csv.gz"
    features.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
    return {"rows": len(features), "sha256": file_sha(path), "path": str(path.relative_to(ROOT))}


def candidates(cfg):
    # Declared before validation. No league-, draw-, or lead-time selection on test outcomes.
    return [
        {"model": model, "min_edge": edge}
        for model in ["market", "dc", "elo", "blend"]
        for edge in [0.03, 0.05]
    ]


def joined_features(stage):
    cfg = strategy()
    history = load_matches()
    maximum = cfg["test_season"] - 1 if stage == "validation" else cfg["test_season"]
    history = history[history.season <= maximum]
    validation = load_features(ROOT / "data/processed/features_validation.csv.gz")
    if stage == "test":
        features = pd.concat(
            [validation, load_features(ROOT / "data/processed/features_test.csv.gz")]
        )
    else:
        features = validation
    return features.merge(history, on="match_id", how="inner", validate="one_to_one")


def walk_forward_probabilities(frame, cfg, model):
    pieces = []
    for season, group in frame.groupby("season", sort=True):
        if model == "blend":
            cutoff = pd.Timestamp(year=int(season), month=7, day=1, tz="UTC")
            past = frame[(frame.season < season) & (frame.available_at < cutoff)]
            if len(past) < cfg["blend_min_matches"]:
                continue
            fitted = OffsetBlend(cfg["blend_ridge"]).fit(past, cutoff)
            p = fitted.predict(group)
        else:
            p = probability_matrix(group, model)
        part = group.copy()
        part[["p" + s for s in SIDES]] = p
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def choose_bet(probabilities, prices, cfg):
    p, o = np.asarray(probabilities, float), np.asarray(prices, float)
    valid = np.isfinite(o) & (o >= cfg["min_odds"]) & (o <= cfg["max_odds"])
    edge = np.where(valid, p * o - 1, -np.inf)
    side = int(np.argmax(edge))
    if edge[side] < cfg["min_edge"]:
        return None
    stake_fraction = min(cfg["stake_cap"], cfg["kelly_fraction"] * edge[side] / (o[side] - 1))
    return {
        "side": SIDES[side],
        "side_index": side,
        "odds": float(o[side]),
        "edge": float(edge[side]),
        "stake_fraction": float(stake_fraction),
    }


def simulate(frame, cfg):
    cash, pending, bets = 100.0, [], []
    for row in frame.sort_values(["decision_at", "match_id"]).itertuples():
        while pending and pending[0][0] < row.decision_at:
            _, _, stake, won, odds = heapq.heappop(pending)
            cash += stake * odds if won else 0
        p = np.array([getattr(row, "p" + s) for s in SIDES])
        prices = np.array([getattr(row, cfg["odds_source"] + s) for s in SIDES])
        bet = choose_bet(p, prices, cfg)
        if bet is None:
            continue
        exposure = sum(item[2] for item in pending)
        equity = cash + exposure
        stake = min(
            bet["stake_fraction"] * equity,
            max(0, cfg["open_exposure_cap"] * equity - exposure),
            cash,
        )
        if stake <= 1e-10:
            continue
        side = bet["side"]
        closing = getattr(row, cfg["closing_source"] + side)
        if not np.isfinite(closing) or closing <= 1:
            # Missing future prices do not affect selection or portfolio stakes.
            closing = np.nan
        won = row.outcome == bet["side_index"]
        cash -= stake
        heapq.heappush(pending, (row.available_at, row.match_id, stake, won, bet["odds"]))
        close_prices = np.array([getattr(row, cfg["closing_source"] + s) for s in SIDES])
        fair = (
            devig(close_prices)[bet["side_index"]]
            if np.isfinite(close_prices).all() and (close_prices > 1).all()
            else np.nan
        )
        paired_close = getattr(row, "B365C" + side)
        bets.append(
            {
                "match_id": row.match_id,
                "league": row.div,
                "decision_at": row.decision_at.isoformat(),
                "kickoff_utc": row.kickoff_utc.isoformat(),
                "settled_at": row.available_at.isoformat(),
                **bet,
                "stake_units": stake,
                "profit_units": float(stake * (bet["odds"] - 1) if won else -stake),
                "log_clv": float(np.log(bet["odds"] / closing)) if np.isfinite(closing) else None,
                "fair_log_clv": float(np.log(bet["odds"] * fair)) if np.isfinite(fair) else None,
                "same_book_log_clv": float(np.log(bet["odds"] / paired_close))
                if np.isfinite(paired_close) and paired_close > 1
                else None,
                "block": row.kickoff_utc.date().isoformat(),
                "side_won": bool(won),
            }
        )
    return pd.DataFrame(bets)


def daily_returns(bets, start=None, end=None):
    if bets.empty:
        return (
            pd.Series(0.0, index=pd.date_range(start, end, freq="D"))
            if start is not None
            else pd.Series(dtype=float)
        )
    daily = bets.groupby(pd.to_datetime(bets.settled_at, utc=True).dt.floor("D")).profit_units.sum()
    daily = daily.reindex(
        pd.date_range(start or daily.index.min(), end or daily.index.max(), freq="D"),
        fill_value=0,
    )
    start_equity = 100 + daily.cumsum().shift(1, fill_value=0)
    return daily / start_equity


def summarize_bets(bets, cfg):
    if bets.empty:
        return {
            "bets": 0,
            "clv": block_ci([], []),
            "profit_units": 0,
            "roi": None,
            "power": power_analysis([], []),
        }
    valid = bets[bets.log_clv.notna()]
    return {
        "bets": len(bets),
        "clv_missing": int(bets.log_clv.isna().sum()),
        "clv": block_ci(valid.log_clv, valid.block, cfg["bootstrap_samples"], cfg["seed"]),
        "profit_units": float(bets.profit_units.sum()),
        "stake_units": float(bets.stake_units.sum()),
        "roi": float(bets.profit_units.sum() / bets.stake_units.sum()),
        "fair_log_clv": float(bets.fair_log_clv.mean())
        if bets.fair_log_clv.notna().any()
        else None,
        "same_book_log_clv": float(bets.same_book_log_clv.mean())
        if bets.same_book_log_clv.notna().any()
        else None,
        "power": power_analysis(valid.log_clv, valid.block),
    }


def evaluate(frame, cfg):
    closes = frame[[cfg["closing_source"] + s for s in SIDES]].to_numpy(float)
    eligible = np.isfinite(closes).all(1) & (closes > 1).all(1) & frame.outcome.notna()
    comparable = frame[eligible]
    if comparable.empty:
        raise ValueError("No complete closing-price triples for evaluation")
    closing_p = devig(closes[eligible])
    predicted = comparable[["p" + s for s in SIDES]].to_numpy(float)
    report = {
        "forecast_rows": len(frame),
        "missing_closing_triples": int((~eligible).sum()),
        "model": scores(predicted, comparable.outcome, closing_p),
        "closing_baseline": scores(closing_p, comparable.outcome, closing_p),
    }
    report["log_loss_gap"] = report["model"]["log_loss"] - report["closing_baseline"]["log_loss"]
    bets = simulate(frame, cfg)
    report.update(summarize_bets(bets, cfg))
    report["by_league"] = (
        {league: summarize_bets(group, cfg) for league, group in bets.groupby("league")}
        if not bets.empty
        else {}
    )
    report["by_side"] = (
        {side: summarize_bets(group, cfg) for side, group in bets.groupby("side")}
        if not bets.empty
        else {}
    )
    return report, bets


def run_backtest(stage):
    cfg = strategy()
    output = ROOT / f"results/{stage}.json"
    if stage == "test":
        assert_frozen()
        if output.exists():
            raise RuntimeError("Held-out test already opened; replay saved predictions instead")
    require_permission(training=True)
    specifications = (
        candidates(cfg)
        if stage == "validation"
        else [read_json(ROOT / "results/selection.json")["candidate"]]
    )
    frame = joined_features(stage)
    predictions = {}
    reports, daily = [], []
    for specification in specifications:
        trial_id = register_trial(
            {
                "kind": "strategy",
                "stage": stage,
                "candidate": specification,
                "strategy_sha": digest(cfg),
                "status": "REGISTERED",
            }
        )
        local = {**cfg, **specification}
        model = specification["model"]
        if model not in predictions:
            predictions[model] = walk_forward_probabilities(frame, cfg, model)
        predicted = predictions[model]
        predicted = (
            predicted[predicted.season.isin(cfg["validation_seasons"])]
            if stage == "validation"
            else predicted[predicted.season == cfg["test_season"]]
        )
        if stage == "test":
            predicted = predicted[~predicted.match_id.isin(cfg["test_excluded_ids"])]
        report, bets = evaluate(predicted, local)
        report.update({"trial_id": trial_id, "candidate": specification})
        reports.append(report)
        daily.append(
            daily_returns(
                bets,
                predicted.decision_at.min().floor("D"),
                predicted.available_at.max().floor("D"),
            )
        )
        name = f"{stage}_{model}_{specification['min_edge']:.2f}"
        predicted.to_csv(
            ROOT / f"results/{name}_predictions.csv.gz",
            index=False,
            compression={"method": "gzip", "mtime": 0},
        )
        bets.to_csv(ROOT / f"results/{name}_bets.csv", index=False)
    trial_count = len(TRIALS.read_text().splitlines())
    sharpes = [float(x.mean() / x.std(ddof=1)) for x in daily if len(x) > 2 and x.std(ddof=1) > 0]
    if stage == "test":
        sharpes = [
            report["deflated_sharpe"]["daily_sharpe"]
            for report in read_json(ROOT / "results/validation.json")["reports"]
            if "daily_sharpe" in report["deflated_sharpe"]
        ]
    for report, returns in zip(reports, daily, strict=True):
        report["deflated_sharpe"] = deflated_sharpe(returns, sharpes, trial_count)
    result = {
        "status": "COMPLETE",
        "stage": stage,
        "strategy_sha": digest(cfg),
        "source_commit": git("rev-parse", "HEAD"),
        "data_sha": file_sha(PROCESSED),
        "trial_count": trial_count,
        "predeclared_test_excluded_ids": cfg["test_excluded_ids"] if stage == "test" else [],
        "reports": reports,
        "warning": "Historical quote timing and availability are proxies, not execution proof",
    }
    write_json(output, result)
    return result


def select():
    if git("tag", "-l", "forward-v1"):
        raise RuntimeError("Forward strategy already frozen; no reselection")
    validation = read_json(ROOT / "results/validation.json")
    # Select calibration first; CLV and P&L never determine the winning candidate.
    winner = min(
        validation["reports"], key=lambda r: (r["log_loss_gap"], -r["candidate"]["min_edge"])
    )
    result = {
        "status": "SELECTED",
        "candidate": winner["candidate"],
        "strategy_sha": digest(strategy()),
        "validation_sha": file_sha(ROOT / "results/validation.json"),
        "selection_rule": "lowest validation outcome log loss; ties choose higher edge threshold",
    }
    write_json(ROOT / "results/selection.json", result)
    return result


def assert_frozen():
    cfg = strategy()
    selection = read_json(ROOT / "results/selection.json")
    frozen_config = git("show", f"{REGISTRATION_TAG}:config/strategy.json")
    frozen_selection = git("show", f"{REGISTRATION_TAG}:results/selection.json")
    import json

    if (
        digest(json.loads(frozen_config)) != digest(cfg)
        or json.loads(frozen_selection) != selection
    ):
        raise RuntimeError("Configuration/selection differs from registered tag")
    if selection["strategy_sha"] != digest(cfg):
        raise RuntimeError("Selection was made under a different strategy")
    if selection["validation_sha"] != file_sha(ROOT / "results/validation.json"):
        raise RuntimeError("Validation artifact differs from the frozen selection")
    # Implementation files are frozen too; a post-tag model edit requires a new protocol.
    changed = git(
        "diff",
        REGISTRATION_TAG,
        "--",
        *[
            str(path.relative_to(ROOT))
            for path in (ROOT / "src/closing_line_lab").glob("*.py")
            if path.name not in ("report.py", "cli.py")
        ],
        "config/strategy.json",
        "config/forward.json",
        "config/team_aliases.json",
        "config/fitted_model.json",
    )
    if changed:
        raise RuntimeError("Model or bet rule changed since pre-registration")
    return selection
