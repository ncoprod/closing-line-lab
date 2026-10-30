"""Install the hourly runner in a separate checkout, without storing a key in its plist."""

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

LABEL = "com.ncoprod.closing-line-lab"
ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = Path.home() / "Library/Application Support/closing-line-lab/checkout"
PLIST = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"


def configuration(checkout, uv):
    return {
        "Label": LABEL,
        "ProgramArguments": [
            uv,
            "run",
            "--frozen",
            "python",
            "ops/run_cycle.py",
            "--runner",
            "launchd",
        ],
        "WorkingDirectory": str(checkout),
        "StartCalendarInterval": {"Minute": 5},
        "RunAtLoad": True,
        "EnvironmentVariables": {
            "PATH": f"{Path(uv).parent}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        },
        "StandardOutPath": str(checkout / "runs/launchd.log"),
        "StandardErrorPath": str(checkout / "runs/launchd-error.log"),
    }


def main():
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required")
    if os.environ.get("ODDS_API_KEY"):
        subprocess.run(["/usr/bin/swift", str(ROOT / "ops/store_keychain.swift")], check=True)
    if not CHECKOUT.exists():
        CHECKOUT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["gh", "repo", "clone", "ncoprod/closing-line-lab", str(CHECKOUT)], check=True
        )
    subprocess.run([uv, "sync", "--frozen"], cwd=CHECKOUT, check=True)
    (CHECKOUT / "runs").mkdir(exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(configuration(CHECKOUT, uv)))
    target = f"gui/{os.getuid()}"
    # Refuse to interrupt a running instance. Reinstallation is an explicit unload/install.
    found = subprocess.run(["launchctl", "print", f"{target}/{LABEL}"], capture_output=True)
    if found.returncode == 0:
        raise RuntimeError("Agent already loaded; unload it while idle before reinstalling")
    subprocess.run(["launchctl", "bootstrap", target, str(PLIST)], check=True)
    print(f"Installed {LABEL}; RunAtLoad starts one real cycle. Logs: {CHECKOUT / 'runs'}")


if __name__ == "__main__":
    main()
