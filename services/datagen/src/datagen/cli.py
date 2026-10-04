"""``python -m datagen``: generate the source data, export the legacy workbook."""

import argparse
import sys
from pathlib import Path

from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.exc import OperationalError, ProgrammingError

from datagen.executor import Databases
from datagen.generate import lot_numbers_from_db
from datagen.legacy_workbook import build_workbook, check_workbook
from datagen.oracle import oracle_rows
from datagen.params import Params, load_params
from datagen.planner import build_plan
from datagen.stats import compute_stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datagen", description="Seeded synthetic data generator (F05)")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="wipe the three source DBs and replay a site history")
    generate.add_argument("--profile", default="site_a", help="site profile name (default: site_a)")
    generate.add_argument("--seed", type=int, default=None, help="default: the profile's demo.seed")
    generate.add_argument("--artifacts", type=Path, default=Path("artifacts"), help="output directory")

    workbook = commands.add_parser("legacy-workbook", help="export the messy legacy tracker workbook")
    workbook.add_argument("--profile", default="site_a")
    workbook.add_argument("--seed", type=int, default=None, help="default: the profile's demo.seed")
    workbook.add_argument("--out", type=Path, default=Path("artifacts/legacy_tracker.xlsx"))
    workbook.add_argument(
        "--artifacts", type=Path, default=Path("artifacts"), help="holds expected_stages.csv"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = load_profile(args.profile)
    seed = profile.demo.seed if args.seed is None else args.seed
    params = load_params()
    if args.command == "legacy-workbook":
        return _legacy_workbook(profile, params, seed, args.out)
    print(f"datagen {args.command}: profile={args.profile} seed={seed}")
    return 0


def _legacy_workbook(profile: SiteProfile, params: Params, seed: int, out: Path) -> int:
    plan = build_plan(profile, params, seed)
    numbers: dict[str, str] = {}
    try:
        numbers = lot_numbers_from_db(plan, Databases.from_env().erp)
    except (OperationalError, ProgrammingError):
        print(
            "datagen: no generated ERP database reachable, using the plan's lot refs instead of lot numbers"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    build_workbook(plan, params, compute_stats(plan, profile), numbers).save(out)
    intended = {key: stage for key, stage, _ in oracle_rows(plan, None)}
    if numbers:
        intended = {
            f"{b.matnr}|{b.charg}|{numbers[lot.ref]}": lot.stage
            for b, lot in plan.lots()
            if lot.ref in numbers
        }
    rows, disagree = check_workbook(out, intended)
    print(f"datagen: wrote {out} ({rows} tracker rows, {disagree} typed statuses disagree with the source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
