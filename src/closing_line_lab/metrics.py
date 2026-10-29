import numpy as np
from scipy.stats import kurtosis, norm, skew


def devig(odds):
    odds = np.asarray(odds, dtype=float)
    if not np.isfinite(odds).all() or (odds <= 1).any():
        raise ValueError("Decimal odds must be finite and greater than one")
    inverse = 1 / odds
    return inverse / inverse.sum(axis=-1, keepdims=True)


def clv(taken, closing):
    if taken <= 1 or closing <= 1 or not np.isfinite([taken, closing]).all():
        raise ValueError("Invalid odds")
    return float(np.log(taken / closing))


def scores(probabilities, outcomes, closing_probabilities):
    p = np.clip(np.asarray(probabilities), 1e-12, 1)
    y = np.eye(3)[np.asarray(outcomes, dtype=int)]
    close = np.asarray(closing_probabilities)
    return {
        "matches": len(p),
        "log_loss": float(-(y * np.log(p)).sum(axis=1).mean()),
        "brier": float(((p - y) ** 2).sum(axis=1).mean()),
        "closing_cross_entropy": float(-(close * np.log(p)).sum(axis=1).mean()),
        "closing_probability_mse": float(((p - close) ** 2).sum(axis=1).mean()),
    }


def block_ci(values, blocks, samples=5000, seed=20261029):
    """Resample calendar dates, preserving within-date dependence and bet weighting."""
    values, blocks = np.asarray(values, dtype=float), np.asarray(blocks)
    if len(values) == 0:
        return {"mean": None, "ci95": None, "blocks": 0, "observations": 0}
    unique, inverse = np.unique(blocks, return_inverse=True)
    sums = np.bincount(inverse, weights=values)
    counts = np.bincount(inverse)
    rng = np.random.default_rng(seed)
    means = np.empty(samples)
    for i in range(samples):
        draw = rng.integers(0, len(unique), len(unique))
        means[i] = sums[draw].sum() / counts[draw].sum()
    return {
        "mean": float(values.mean()),
        "ci95": [float(x) for x in np.quantile(means, [0.025, 0.975])]
        if len(unique) >= 2
        else None,
        "blocks": len(unique),
        "observations": len(values),
    }


def deflated_sharpe(returns, trial_sharpes, trials):
    """Unannualized daily DSR; independent-trials approximation, not a CLV test."""
    r = np.asarray(returns, dtype=float)
    if len(r) < 3 or np.std(r, ddof=1) == 0:
        return {"probability": None, "trials": trials, "reason": "insufficient variation"}
    sr = float(r.mean() / r.std(ddof=1))
    trial_sharpes = np.asarray(trial_sharpes, dtype=float)
    # The null standard error prevents identical candidate returns implying no selection penalty.
    variance = max(
        float(np.var(trial_sharpes, ddof=1)) if len(trial_sharpes) > 1 else 0, 1 / (len(r) - 1)
    )
    gamma = np.euler_gamma
    benchmark = (
        0.0
        if trials <= 1
        else np.sqrt(variance)
        * ((1 - gamma) * norm.ppf(1 - 1 / trials) + gamma * norm.ppf(1 - 1 / (trials * np.e)))
    )
    denominator = (
        1 - skew(r, bias=False) * sr + (kurtosis(r, fisher=False, bias=False) - 1) * sr**2 / 4
    )
    return {
        "probability": float(
            norm.cdf((sr - benchmark) * np.sqrt(len(r) - 1) / np.sqrt(max(denominator, 1e-12)))
        ),
        "daily_sharpe": sr,
        "null_benchmark": float(benchmark),
        "trial_sharpe_variance": variance,
        "trials": trials,
        "days": len(r),
        "assumption": "independent trials and daily returns; descriptive under dependence",
    }


def power_analysis(values, blocks, effects_bp=(5, 10, 25, 50, 100)):
    x, blocks = np.asarray(values, dtype=float), np.asarray(blocks)
    if len(x) < 3 or len(np.unique(blocks)) < 2:
        return {"status": "NOT_ESTIMABLE", "reason": "Need observed CLV across multiple dates"}
    _, inverse = np.unique(blocks, return_inverse=True)
    residual_sums = np.bincount(inverse, weights=x - x.mean())
    groups = len(residual_sums)
    variance_mean = groups / (groups - 1) * np.square(residual_sums).sum() / len(x) ** 2
    iid_variance = x.var(ddof=1)
    design_effect = max(1.0, variance_mean * len(x) / iid_variance) if iid_variance else 1.0
    required = (norm.ppf(0.95) + norm.ppf(0.8)) ** 2 * iid_variance * design_effect
    return {
        "status": "ESTIMATED",
        "alpha_one_sided": 0.05,
        "power": 0.8,
        "clv_sd": float(np.sqrt(iid_variance)),
        "design_effect": float(design_effect),
        "required_bets": {str(bp): int(np.ceil(required / (bp / 10000) ** 2)) for bp in effects_bp},
        "assumption": "normal approximation; historical date clustering persists",
    }
