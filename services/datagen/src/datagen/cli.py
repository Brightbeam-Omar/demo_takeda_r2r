"""``python -m datagen``: generate the source data, export the legacy workbook."""

import argparse
import sys
from pathlib import Path

from r2r_core.profile import load_profile

from datagen.params import load_params


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
    print(f"datagen {args.command}: profile={args.profile} seed={seed} stages={len(params.open_stage_mix)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
