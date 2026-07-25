from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta

from dotenv import load_dotenv

from .newsletter import send_weekly_newsletter
from .pipeline import run_pipeline
from .repository import create_repository


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="imarsinyal")
    command.add_argument("--log-level", default="INFO")
    subcommands = command.add_subparsers(dest="command", required=True)

    nightly = subcommands.add_parser("nightly")
    nightly.add_argument("--force", action="store_true")
    nightly.add_argument("--skip-council", action="store_true")

    backfill = subcommands.add_parser("backfill")
    backfill.add_argument("--from-date", default="2026-01-01")
    backfill.add_argument("--force", action="store_true")

    subcommands.add_parser("newsletter")
    return command


def main() -> None:
    load_dotenv()
    args = parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    repository = create_repository()
    if args.command == "newsletter":
        result = send_weekly_newsletter(repository)
    else:
        from_date = (
            date.fromisoformat(args.from_date)
            if args.command == "backfill"
            else date.today() - timedelta(days=90)
        )
        result = run_pipeline(
            repository=repository,
            council_from=from_date,
            include_council=not getattr(args, "skip_council", False),
            force=args.force,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
