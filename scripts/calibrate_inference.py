"""Null-only validation: no market observations, forecast selection or outcome tuning."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.stats import norm, t

from closing_line_lab.metrics import CLV_CONFIDENCE, CLV_HAC_LAGS, CLV_MIN_BETS, CLV_MIN_WEEKS

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="results/null_calibration.json")
parser.add_argument("--min-weeks", type=int, default=CLV_MIN_WEEKS)
parser.add_argument("--critical-coverage", type=float, default=CLV_CONFIDENCE)
args = parser.parse_args()
rng = np.random.default_rng(20261029)
reps = 10000
reports = []
for weeks in [30, 60, 120]:
    for distribution in ["normal", "student_t5", "negative_lognormal"]:
        for rho in [0.0, 0.3, 0.6]:
            shape = (reps, weeks + 100)
            if distribution == "normal":
                innovations = rng.normal(size=shape)
            elif distribution == "student_t5":
                innovations = rng.standard_t(5, size=shape) / np.sqrt(5 / 3)
            else:
                z = rng.normal(size=shape)
                innovations = -(np.exp(z) - np.exp(0.5)) / np.sqrt((np.e - 1) * np.e)
            shock = np.zeros(reps)
            series = []
            for step in range(weeks + 100):
                shock = rho * shock + np.sqrt(1 - rho**2) * innovations[:, step]
                if step >= 100:
                    series.append(shock.copy())
            shock = np.array(series).T
            counts = rng.integers(4, 11, size=(reps, weeks))
            sums = counts * shock + np.sqrt(counts) * 0.3 * rng.normal(size=counts.shape)
            n = counts.sum(axis=1)
            means = sums.sum(axis=1) / n
            residuals = sums - means[:, None] * counts
            meat = np.square(residuals).sum(axis=1)
            for lag in range(1, CLV_HAC_LAGS + 1):
                meat += (
                    2
                    * (1 - lag / (CLV_HAC_LAGS + 1))
                    * (residuals[:, lag:] * residuals[:, :-lag]).sum(axis=1)
                )
            se = np.sqrt(np.maximum(0, weeks / (weeks - 1) * meat)) / n
            reject = means - t.ppf((1 + args.critical_coverage) / 2, weeks - 1) * se > 0
            reject &= (weeks >= args.min_weeks) & (n >= CLV_MIN_BETS)
            k = int(reject.sum())
            rate = k / reps
            z = norm.ppf(0.975)
            upper = (
                rate
                + z * z / (2 * reps)
                + z * np.sqrt(rate * (1 - rate) / reps + z * z / (4 * reps * reps))
            ) / (1 + z * z / reps)
            reports.append(
                {
                    "weeks": weeks,
                    "distribution": distribution,
                    "weekly_ar1": rho,
                    "replications": reps,
                    "false_positive_rate": rate,
                    "wilson95_upper": float(upper),
                }
            )
            print(reports[-1], flush=True)
old = rng.normal(size=(200000, 2))
result = {
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "implementation_sha256": {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path("src/closing_line_lab/metrics.py")]
    },
    "seed": 20261029,
    "data": "SYNTHETIC_NULL_ONLY",
    "policy": {
        "min_weeks": args.min_weeks,
        "min_bets": CLV_MIN_BETS,
        "confidence_parameter": args.critical_coverage,
        "hac_lags": CLV_HAC_LAGS,
    },
    "old_two_date_false_positive_rate": float((old.min(axis=1) > 0).mean()),
    "old_two_date_exact_null_rate": 0.25,
    "old_two_date_exact_coverage": 0.5,
    "new_two_date_status": "INSUFFICIENT_INFORMATION",
    "scenarios": reports,
    "validation_rule": "Every scenario's Wilson 95% upper false-positive bound must be <= 0.05",
    "status": "PASS" if max(r["wilson95_upper"] for r in reports) <= 0.05 else "FAIL",
    "limitations": (
        "Finite scenarios do not prove universal coverage; stronger dependence/heavier "
        "tails may invalidate inference. This pilot cannot attain the week threshold."
    ),
}
Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
