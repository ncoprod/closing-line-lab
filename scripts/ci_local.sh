#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")/.."

# Mirrors ci.yml and audit.yml; skip GitHub checkout/setup/upload actions.
# Ledger verification uses local gh authentication if it needs hosted receipts.
# Skip paper.yml's provider/publishing cycle: launchd owns the local schedule;
# the existing scheduled Action remains an unchanged fallback.
# Use --no-sync after the explicit sync to keep the tested environment fixed.
python3 - <<'PY'
import datetime
import json
import platform
import subprocess
import time
from pathlib import Path

commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
short_sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"]))
steps = [
    ("sync", "uv sync --frozen"),
    ("lint", "uv run --no-sync ruff check ."),
    ("format", "uv run --no-sync ruff format --check ."),
    ("tests", "uv run --no-sync pytest -q"),
    ("ledger audit", "uv run --no-sync cll verify"),
]
receipt = {
    "commit": commit,
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
    "working_tree_dirty": dirty,
    "steps": [],
    "overall": "PASS",
}
for name, command in steps:
    print(f"ci_local: {name}", flush=True)
    started = time.monotonic()
    result = subprocess.run(["/bin/bash", "-c", command])
    receipt["steps"].append({
        "name": name,
        "exit_code": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
    })
    if result.returncode:
        receipt["overall"] = "FAIL"
        break

path = Path("results/ci_local") / f"{short_sha}.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(receipt, indent=2) + "\n")
print(f"ci_local: {receipt['overall']} ({path})", flush=True)
raise SystemExit(0 if receipt["overall"] == "PASS" else 1)
PY
