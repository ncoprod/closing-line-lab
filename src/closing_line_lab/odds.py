"""Small v4 client. Credential-bearing URLs never enter logs or manifests."""

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from .common import ROOT, canonical, now_utc, read_json, timestamp, write_json

API = "https://api.the-odds-api.com/v4/sports"
USAGE = ROOT / "data/api_usage.json"
MANIFEST = ROOT / "data/api_manifest.jsonl"


def forward_config():
    return read_json(ROOT / "config/forward.json")


class BudgetExhausted(RuntimeError):
    pass


class OddsClient:
    def __init__(self):
        self.credential = os.environ.get("ODDS_API_KEY")
        if not self.credential:
            raise RuntimeError("ODDS_API_KEY is absent")
        self.cfg = forward_config()
        self.usage = read_json(USAGE) if USAGE.exists() else {"months": {}}

    def get(self, sport, endpoint, **params):
        if sport not in self.cfg["sports"] or endpoint not in ("events", "odds", "scores"):
            raise ValueError("Endpoint outside the registered research scope")
        expected = {"events": 0, "odds": 1, "scores": 2}[endpoint]
        if endpoint == "odds":
            params.update(regions="eu", markets="h2h", oddsFormat="decimal")
        if endpoint == "scores":
            params.update(daysFrom=3)
        safe_url = f"{API}/{sport}/{endpoint}"
        for attempt in range(3):
            month = now_utc().strftime("%Y-%m")
            charged = self.usage["months"].get(month, 0)
            remaining = self.usage.get("remaining", self.cfg["provider_monthly_credits"])
            if expected and (
                charged + expected > self.cfg["monthly_credit_cap"]
                or remaining - expected < self.cfg["provider_reserve"]
            ):
                raise BudgetExhausted("Credit cap/reserve reached; no paid request made")
            # Reserve before transmission: failed/ambiguous calls also consume the local budget.
            self.usage["months"][month] = charged + expected
            write_json(USAGE, self.usage)
            query = urllib.parse.urlencode({**params, "apiKey": self.credential})
            request = urllib.request.Request(safe_url + "?" + query)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = response.read()
                    headers = dict(response.headers)
                break
            except (urllib.error.URLError, TimeoutError) as error:
                code = getattr(error, "code", None)
                if attempt == 2 or (code is not None and code != 429 and code < 500):
                    raise RuntimeError(
                        f"Odds API request failed; HTTP {code or 'network'}"
                    ) from None
                time.sleep(2 ** (attempt + 1))
        headers = {k.lower(): v for k, v in headers.items()}
        required = ["x-requests-remaining", "x-requests-used", "x-requests-last"]
        if any(k not in headers for k in required):
            raise RuntimeError("Quota headers missing; stop instead of guessing usage")
        remaining, used, last = [int(headers[k]) for k in required]
        self.usage.update(remaining=remaining, provider_used=used)
        self.usage["months"][month] += max(0, last - expected)
        write_json(USAGE, self.usage)
        data = json.loads(payload)
        if not isinstance(data, list):
            raise ValueError("Unexpected API response schema")
        sha = hashlib.sha256(payload).hexdigest()
        path = ROOT / "data/api_raw" / f"{sha}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        entry = {
            "url": safe_url,
            "parameters": params,
            "retrieved_at": now_utc().isoformat(),
            "sha256": sha,
            "bytes": len(payload),
            "credits_remaining": remaining,
            "credits_used": used,
            "credits_last": last,
        }
        MANIFEST.parent.mkdir(exist_ok=True)
        with MANIFEST.open("a") as handle:
            handle.write(canonical(entry) + "\n")
        return data, entry


def quote(event, priority, retrieved_at, cfg):
    """Pick a predeclared book, never the best price across books."""
    observed = timestamp(retrieved_at)
    if timestamp(event["commence_time"]) <= observed:
        return None
    books = {b["key"]: b for b in event.get("bookmakers", [])}
    for book in priority:
        if book not in books:
            continue
        for market in books[book].get("markets", []):
            if market["key"] != "h2h":
                continue
            updated = timestamp(market.get("last_update", books[book]["last_update"]))
            age = (observed - updated).total_seconds() / 60
            if not -cfg["max_clock_skew_seconds"] / 60 <= age <= cfg["quote_max_age_minutes"]:
                continue
            prices = {o["name"]: o["price"] for o in market["outcomes"]}
            names = [event["home_team"], "Draw", event["away_team"]]
            if not all(name in prices for name in names):
                continue
            raw = np.array([prices[name] for name in names], float)
            if not np.isfinite(raw).all() or (raw <= 1).any():
                continue
            # Apply a fixed, conservative exchange commission to net winnings.
            effective = (
                1 + (raw - 1) * (1 - cfg["exchange_commission"])
                if book.startswith("betfair_ex")
                else raw
            )
            return {
                "bookmaker": book,
                "prices": raw.tolist(),
                "effective_prices": effective.tolist(),
                "raw_prices": raw.tolist(),
                "updated_at": updated.isoformat(),
                "retrieved_at": retrieved_at,
                "commission": cfg["exchange_commission"] if book.startswith("betfair_ex") else 0,
            }
    return None
