import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import poisson

from .metrics import devig

SIDES = "HDA"


def as_of(history, cutoff):
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError("Cutoff must be timezone aware")
    return history[
        (history.available_at < cutoff) & (history.kickoff_utc < cutoff) & history.outcome.notna()
    ].copy()


class DixonColes:
    def __init__(self, cfg):
        self.cfg = cfg

    def fit(self, history, cutoff):
        frame = as_of(history, cutoff)
        age = (pd.Timestamp(cutoff) - frame.kickoff_utc).dt.total_seconds() / 86400
        frame, age = frame[age < self.cfg["dc_window_days"]], age[age < self.cfg["dc_window_days"]]
        if len(frame) < 100:
            raise ValueError("Dixon-Coles needs at least 100 past matches")
        self.teams = {name: i for i, name in enumerate(sorted(set(frame.home) | set(frame.away)))}
        n = len(self.teams)
        h, a = frame.home.map(self.teams).to_numpy(), frame.away.map(self.teams).to_numpy()
        x, y = frame.hg.to_numpy(float), frame.ag.to_numpy(float)
        weights = np.exp(-np.log(2) * age.to_numpy() / self.cfg["dc_half_life_days"])
        weights /= weights.sum()
        ridge = self.cfg["dc_ridge"]

        def objective(theta):
            attack, defence = theta[:n], theta[n : 2 * n]
            ah, da = attack[h] - attack.mean(), defence[a] - defence.mean()
            aa, dh = attack[a] - attack.mean(), defence[h] - defence.mean()
            log_l, log_m = theta[-3] + theta[-2] + ah + da, theta[-3] + aa + dh
            lam, mu = np.exp(np.clip(log_l, -2, 2)), np.exp(np.clip(log_m, -2, 2))
            rho = theta[-1]
            tau = np.ones(len(frame))
            dl, dm, dr = np.zeros(len(frame)), np.zeros(len(frame)), np.zeros(len(frame))
            z00, z01, z10, z11 = (
                (x == 0) & (y == 0),
                (x == 0) & (y == 1),
                (x == 1) & (y == 0),
                (x == 1) & (y == 1),
            )
            tau[z00], dl[z00], dm[z00], dr[z00] = (
                1 - lam[z00] * mu[z00] * rho,
                -mu[z00] * rho,
                -lam[z00] * rho,
                -lam[z00] * mu[z00],
            )
            tau[z01], dl[z01], dr[z01] = 1 + lam[z01] * rho, rho, lam[z01]
            tau[z10], dm[z10], dr[z10] = 1 + mu[z10] * rho, rho, mu[z10]
            tau[z11], dr[z11] = 1 - rho, -1
            loss = np.sum(weights * (lam - x * np.log(lam) + mu - y * np.log(mu) - np.log(tau)))
            loss += ridge * (np.square(attack).sum() + np.square(defence).sum())
            gl = weights * (lam - x - dl * lam / tau) * ((log_l > -2) & (log_l < 2))
            gm = weights * (mu - y - dm * mu / tau) * ((log_m > -2) & (log_m < 2))
            ga = np.bincount(h, gl, minlength=n) + np.bincount(a, gm, minlength=n)
            gd = np.bincount(a, gl, minlength=n) + np.bincount(h, gm, minlength=n)
            grad = np.r_[
                ga - ga.mean() + 2 * ridge * attack,
                gd - gd.mean() + 2 * ridge * defence,
                (gl + gm).sum(),
                gl.sum(),
                -(weights * dr / tau).sum(),
            ]
            return loss, grad

        initial = np.r_[np.zeros(2 * n), np.log(max(frame.ag.mean(), 0.5)), 0.2, -0.05]
        fitted = minimize(
            objective,
            initial,
            jac=True,
            method="L-BFGS-B",
            bounds=[(-1.5, 1.5)] * (2 * n) + [(-1, 1), (-0.5, 0.8), (-0.1, 0)],
            options={"maxiter": 300, "ftol": 1e-10},
        )
        if not fitted.success:
            raise RuntimeError(f"Dixon-Coles optimizer failed: {fitted.message}")
        self.theta = fitted.x
        self.train_max_available = frame.available_at.max()
        self.diagnostics = {
            "matches": len(frame),
            "iterations": int(fitted.nit),
            "rho": float(fitted.x[-1]),
            "converged": True,
        }
        return self

    def predict(self, home, away):
        n = len(self.teams)
        attack, defence = self.theta[:n], self.theta[n : 2 * n]

        def strength(values, team):
            return values[self.teams[team]] - values.mean() if team in self.teams else 0.0

        lam = np.exp(
            np.clip(
                self.theta[-3] + self.theta[-2] + strength(attack, home) + strength(defence, away),
                -2,
                2,
            )
        )
        mu = np.exp(
            np.clip(self.theta[-3] + strength(attack, away) + strength(defence, home), -2, 2)
        )
        matrix = np.outer(poisson.pmf(np.arange(31), lam), poisson.pmf(np.arange(31), mu))
        rho = self.theta[-1]
        matrix[0, 0] *= 1 - lam * mu * rho
        matrix[0, 1] *= 1 + lam * rho
        matrix[1, 0] *= 1 + mu * rho
        matrix[1, 1] *= 1 - rho
        p = np.array([np.tril(matrix, -1).sum(), np.trace(matrix), np.triu(matrix, 1).sum()])
        return p / p.sum()


class Elo:
    def __init__(self, cfg):
        self.cfg, self.ratings = cfg, {}

    def predict(self, div, home, away):
        rh, ra = self.ratings.get((div, home), 1500), self.ratings.get((div, away), 1500)
        q = 10 ** ((rh + self.cfg["elo_home_advantage"] - ra) / 400)
        probabilities = np.array([q, self.cfg["elo_draw_strength"] * np.sqrt(q), 1.0])
        return probabilities / probabilities.sum()

    def update(self, match):
        p = self.predict(match.div, match.home, match.away)
        actual = 1 if match.hg > match.ag else 0.5 if match.hg == match.ag else 0
        change = self.cfg["elo_k"] * (actual - p[0] - 0.5 * p[1])
        for team, delta in [(match.home, change), (match.away, -change)]:
            key = (match.div, team)
            self.ratings[key] = self.ratings.get(key, 1500) + delta


def make_features(history, targets, cfg):
    """Market columns are explicitly whitelisted; closing odds cannot enter this function."""
    targets = targets.copy()
    if "decision_at" not in targets:
        targets["decision_at"] = targets.kickoff_utc - pd.Timedelta(hours=24)
    targets = targets.sort_values(["decision_at", "match_id"])
    events = list(
        history[history.outcome.notna()].sort_values(["available_at", "match_id"]).itertuples()
    )
    elo, cursor, last_available = Elo(cfg), 0, None
    dc_cache, records = {}, []
    for row in targets.itertuples():
        cutoff = pd.Timestamp(row.decision_at)
        while cursor < len(events) and events[cursor].available_at < cutoff:
            event = events[cursor]
            elo.update(event)
            last_available = event.available_at
            cursor += 1
        month = cutoff.normalize().replace(day=1)
        key = (row.div, month)
        if key not in dc_cache:
            past = as_of(history[history["div"] == row.div], month)
            if len(past) < 100:
                dc_cache[key] = None
            else:
                dc_cache[key] = DixonColes(cfg).fit(past, month)
        dc = dc_cache[key]
        prices = np.array([getattr(row, cfg["odds_source"] + s) for s in SIDES], dtype=float)
        if dc is None or not np.isfinite(prices).all() or (prices <= 1).any():
            continue
        p_dc, p_elo, p_open = (
            dc.predict(row.home, row.away),
            elo.predict(row.div, row.home, row.away),
            devig(prices),
        )
        maximum = max(x for x in [last_available, dc.train_max_available] if x is not None)
        if maximum >= cutoff:
            raise AssertionError("Feature used a result not available before the decision")
        record = {
            "match_id": row.match_id,
            "decision_at": cutoff,
            "feature_max_available": maximum,
            "dc_fit_at": month,
        }
        for name, probabilities in [("dc", p_dc), ("elo", p_elo), ("market", p_open)]:
            record.update(
                {name + "_" + s: float(p) for s, p in zip(SIDES, probabilities, strict=True)}
            )
        records.append(record)
    return pd.DataFrame(records)


def probability_matrix(features, name):
    return features[[name + "_" + s for s in SIDES]].to_numpy(float)


class OffsetBlend:
    """Multinomial logistic residuals anchored to the pre-closing market."""

    def __init__(self, ridge=10):
        self.ridge = ridge
        self.theta = np.zeros(5)

    def _design(self, frame):
        market = np.log(probability_matrix(frame, "market"))
        dc = np.log(probability_matrix(frame, "dc")) - market
        elo = np.log(probability_matrix(frame, "elo")) - market
        return market, dc, elo

    def fit(self, frame, cutoff):
        past = frame[(frame.available_at < cutoff) & frame.outcome.notna()]
        if past.empty:
            raise ValueError("No as-of blend training labels")
        market, dc, elo = self._design(past)
        y = np.eye(3)[past.outcome.to_numpy(int)]

        def objective(theta):
            logits = market + theta[0] * dc + theta[1] * elo + theta[2:]
            logp = logits - logsumexp(logits, axis=1, keepdims=True)
            error = np.exp(logp) - y
            loss = -(y * logp).sum() + self.ridge * np.square(theta).sum() / 2
            gradient = (
                np.r_[(error * dc).sum(), (error * elo).sum(), error.sum(axis=0)]
                + self.ridge * theta
            )
            return loss, gradient

        fitted = minimize(
            objective,
            self.theta,
            jac=True,
            method="L-BFGS-B",
            bounds=[(-1, 1)] * 5,
            options={"maxiter": 300},
        )
        if not fitted.success:
            raise RuntimeError(f"Blend optimizer failed: {fitted.message}")
        self.theta = fitted.x
        self.train_max_available = past.available_at.max()
        return self

    def predict(self, frame):
        market, dc, elo = self._design(frame)
        logits = market + self.theta[0] * dc + self.theta[1] * elo + self.theta[2:]
        return np.exp(logits - logsumexp(logits, axis=1, keepdims=True))
