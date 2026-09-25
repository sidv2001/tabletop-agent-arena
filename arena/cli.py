"""Run paired offline matches or check and replay their JSONL transcripts."""

import argparse
import sys
from pathlib import Path

from .agents import AGENT_NAMES
from .games import game_names
from .matches import TraceError, canonical_json, replay_jsonl, run_match, schedule


def _nonnegative(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a non-negative integer") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return number


def _positive(value: str) -> int:
    number = _nonnegative(value)
    if number == 0:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def _agent_pair(value: str) -> tuple[str, str]:
    names = tuple(value.split(","))
    if len(names) != 2 or any(name not in AGENT_NAMES for name in names):
        raise argparse.ArgumentTypeError(f"choose two comma-separated agents from {', '.join(AGENT_NAMES)}")
    return names[0], names[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    match = commands.add_parser("match", help="write reproducible match events as JSONL")
    match.add_argument("--game", choices=game_names(), required=True)
    match.add_argument("--agents", type=_agent_pair, required=True, metavar="A,B")
    match.add_argument("--seed", type=_nonnegative, default=42)
    match.add_argument("--seeds", type=_positive, default=1, help="number of successive match seeds")
    match.add_argument("--swap-seats", action="store_true", help="play each seed in both seat orders")

    replay = commands.add_parser("replay", help="verify recorded actions and emit final result(s)")
    replay.add_argument("trace", nargs="?", default="-", help="JSONL file, or - for standard input")

    args = parser.parse_args(argv)
    if args.command == "match":
        for spec in schedule(args.game, args.agents, args.seed, args.seeds, args.swap_seats):
            for event in run_match(spec):
                print(canonical_json(event))
        return 0

    try:
        if args.trace == "-":
            results = replay_jsonl(sys.stdin)
        else:
            with Path(args.trace).open(encoding="utf-8") as stream:
                results = replay_jsonl(stream)
    except (OSError, TraceError) as exc:
        parser.error(str(exc))
    for result in results:
        print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
