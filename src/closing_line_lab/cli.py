import argparse
import json
import sys

from .data import PermissionMissing


def main():
    parser = argparse.ArgumentParser(description="Paper-only football research")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in [
        "download",
        "select",
        "verify",
        "report",
        "forward",
        "score",
        "actions-evidence",
        "prepare-forward",
        "research-report",
    ]:
        sub.add_parser(name)
    for name in ["features", "backtest"]:
        command = sub.add_parser(name)
        command.add_argument("--stage", choices=["validation", "test"], default="validation")
    publish = sub.add_parser("publish")
    publish.add_argument("--settlements-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare-forward":
            from .artifact import prepare

            result = prepare()
        elif args.command == "download":
            from .data import download_history

            result = download_history()
        elif args.command in ("features", "backtest", "select"):
            from .research import build_features, run_backtest, select

            if args.command == "select":
                result = select()
            elif args.command == "features":
                result = build_features(args.stage)
            else:
                result = run_backtest(args.stage)
        elif args.command == "verify":
            from .ledger import verify

            result = verify()
        elif args.command == "research-report":
            from .report import research_report

            result = research_report()
        elif args.command in ("report", "actions-evidence"):
            from .report import actions_evidence, generate

            result = generate() if args.command == "report" else actions_evidence()
        else:
            from .forward import forecast, publish, settle

            if args.command == "publish":
                result = publish(args.settlements_only)
            else:
                result = forecast() if args.command == "forward" else settle()
    except PermissionMissing as error:
        if args.command == "backtest":
            from .research import register_trial

            register_trial(
                {
                    "kind": "iteration_attempt",
                    "stage": args.stage,
                    "status": "BLOCKED_DATA_PERMISSION",
                    "reason": str(error),
                }
            )
        print(json.dumps({"status": "BLOCKED_DATA_PERMISSION", "reason": str(error)}))
        sys.exit(2)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
