import argparse
import json
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config
from .logging_utils import configure_logging
from .pipeline.runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rlpd", description="Public peptide search and evaluation pipeline")
    parser.add_argument("--version", action="version", version=f"rlpd {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    for name in ("run", "demo"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--config", required=True)
        subparser.add_argument("--no-resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        config = load_config(args.config)
    except (ConfigError, TypeError) as exc:
        parser.error(str(exc))
    configure_logging(path=Path(config.work_root) / "run.log")
    result = run(config, resume=not args.no_resume)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
