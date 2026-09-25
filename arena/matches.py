"""Paired offline matches, canonical JSONL traces, and action-based replay."""

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Literal

from .agents import AGENT_NAMES, Agent, create_agent
from .core import Game, InvalidMove, Outcome, Player, State
from .games import get_game

type Entrant = Literal["A", "B"]

TRACE_SCHEMA = "taa.trace.v1"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def hash_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def derive_agent_seed(seed: int, entrant: Entrant) -> int:
    if type(seed) is not int or seed < 0 or entrant not in ("A", "B"):
        raise ValueError("agent seeds require a non-negative match seed and entrant A or B")
    key = f"taa.agent.seed.v1:{seed}:{entrant}".encode("ascii")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


@dataclass(frozen=True, slots=True)
class Seat:
    entrant: Entrant
    name: str

    def __post_init__(self) -> None:
        if self.entrant not in ("A", "B") or not isinstance(self.name, str) or not self.name:
            raise ValueError("a seat needs entrant A or B and a nonempty agent name")


@dataclass(frozen=True, slots=True)
class MatchSpec:
    game: str
    seed: int
    x: Seat
    o: Seat

    def __post_init__(self) -> None:
        if self.game != get_game(self.game).id:
            raise ValueError("a match must use a versioned game id")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("match seed must be a non-negative integer")
        if {self.x.entrant, self.o.entrant} != {"A", "B"}:
            raise ValueError("each match must seat entrants A and B once")

    @property
    def id(self) -> str:
        seats = {
            "X": {"entrant": self.x.entrant, "agent": self.x.name},
            "O": {"entrant": self.o.entrant, "agent": self.o.name},
        }
        suffix = hash_json({"game": self.game, "seed": self.seed, "seats": seats})[:12]
        return f"{self.game}:{self.seed}:{self.x.entrant}-X:{suffix}"


def schedule(
    game_name: str,
    agent_names: tuple[str, str],
    seed: int,
    seeds: int = 1,
    swap_seats: bool = False,
) -> Iterator[MatchSpec]:
    game = get_game(game_name)
    if len(agent_names) != 2 or any(name not in AGENT_NAMES for name in agent_names):
        raise ValueError(f"choose two agents from {', '.join(AGENT_NAMES)}")
    if type(seed) is not int or seed < 0 or type(seeds) is not int or seeds < 1:
        raise ValueError("seed must be non-negative and seeds must be positive integers")

    a, b = Seat("A", agent_names[0]), Seat("B", agent_names[1])
    for match_seed in range(seed, seed + seeds):
        yield MatchSpec(game.id, match_seed, a, b)
        if swap_seats:
            yield MatchSpec(game.id, match_seed, b, a)


def _start_event(spec: MatchSpec, state: State) -> dict[str, object]:
    return {
        "schema": TRACE_SCHEMA,
        "type": "start",
        "match_id": spec.id,
        "game": spec.game,
        "seed": spec.seed,
        "seats": {
            "X": {
                "entrant": spec.x.entrant,
                "agent": spec.x.name,
                "seed": derive_agent_seed(spec.seed, spec.x.entrant),
            },
            "O": {
                "entrant": spec.o.entrant,
                "agent": spec.o.name,
                "seed": derive_agent_seed(spec.seed, spec.o.entrant),
            },
        },
        "state_hash": hash_json(state.as_dict()),
    }


def _turn_event(
    game: Game, spec: MatchSpec, state: State, actor: Player, attempted_action: object
) -> tuple[dict[str, object], State, Outcome]:
    observation = game.observe(state, actor).as_dict()
    try:
        next_state = game.step(state, actor, attempted_action)
    except InvalidMove as exc:
        next_state = state
        error: dict[str, str] | None = {"code": exc.code, "message": str(exc)}
        accepted_action = None
        outcome = Outcome("win", "O" if actor == "X" else "X", f"forfeit:{exc.code}")
    else:
        error = None
        accepted_action = attempted_action
        outcome = game.outcome(next_state)

    return (
        {
            "schema": TRACE_SCHEMA,
            "type": "turn",
            "match_id": spec.id,
            "ply": state.ply,
            "actor": actor,
            "observation": observation,
            "observation_hash": hash_json(observation),
            "attempted_action": attempted_action,
            "accepted_action": accepted_action,
            "error": error,
            "state_hash": hash_json(next_state.as_dict()),
            "outcome": outcome.as_dict(),
        },
        next_state,
        outcome,
    )


def _result_event(
    spec: MatchSpec, state: State, outcome: Outcome, turns: int
) -> dict[str, object]:
    return {
        "schema": TRACE_SCHEMA,
        "type": "result",
        "match_id": spec.id,
        "game": spec.game,
        "seed": spec.seed,
        "plies": state.ply,
        "turns": turns,
        "state_hash": hash_json(state.as_dict()),
        "outcome": outcome.as_dict(),
    }


def run_match(
    spec: MatchSpec, agents: Mapping[Player, Agent] | None = None
) -> Iterator[dict[str, object]]:
    game = get_game(spec.game)
    if agents is None:
        agents = {
            "X": create_agent(spec.x.name, derive_agent_seed(spec.seed, spec.x.entrant)),
            "O": create_agent(spec.o.name, derive_agent_seed(spec.seed, spec.o.entrant)),
        }
    if set(agents) != {"X", "O"} or agents["X"].name != spec.x.name or agents["O"].name != spec.o.name:
        raise ValueError("match agents must match the named X and O seats")

    state = game.initial(spec.seed)
    outcome = game.outcome(state)
    turns = 0
    yield _start_event(spec, state)
    while outcome.status == "ongoing":
        actor = game.current_player(state)
        if actor is None:
            raise RuntimeError("an ongoing game must have a current player")
        action = agents[actor].choose(game.observe(state, actor))
        try:
            canonical_json(action)
        except (TypeError, ValueError) as exc:
            raise TypeError("agent actions must be JSON-serializable values") from exc
        turn, state, outcome = _turn_event(game, spec, state, actor, action)
        turns += 1
        yield turn
    yield _result_event(spec, state, outcome, turns)


class TraceError(ValueError):
    """A JSONL transcript cannot be reproduced from its recorded actions."""


@dataclass(slots=True)
class _Replay:
    spec: MatchSpec
    game: Game
    state: State
    outcome: Outcome
    turns: int = 0


def _read_start(event: dict[str, object]) -> _Replay:
    game_id, seed, seats = event.get("game"), event.get("seed"), event.get("seats")
    if not isinstance(game_id, str) or type(seed) is not int or seed < 0:
        raise TraceError("start needs a versioned game id and non-negative integer seed")
    if not isinstance(seats, dict) or set(seats) != {"X", "O"}:
        raise TraceError("start needs X and O seat descriptions")

    parsed: list[Seat] = []
    for player in ("X", "O"):
        seat = seats[player]
        if not isinstance(seat, dict) or set(seat) != {"entrant", "agent", "seed"}:
            raise TraceError(f"{player} seat is missing an entrant, agent, or seed")
        entrant, name, agent_seed = seat["entrant"], seat["agent"], seat["seed"]
        if entrant not in ("A", "B") or not isinstance(name, str) or not name:
            raise TraceError(f"{player} seat has an invalid entrant or agent")
        if type(agent_seed) is not int or agent_seed != derive_agent_seed(seed, entrant):
            raise TraceError(f"{player} agent seed does not match the match seed")
        parsed.append(Seat(entrant, name))

    try:
        spec = MatchSpec(game_id, seed, parsed[0], parsed[1])
    except ValueError as exc:
        raise TraceError(str(exc)) from exc
    game = get_game(spec.game)
    state = game.initial(spec.seed)
    return _Replay(spec, game, state, game.outcome(state))


def _expect(event: dict[str, object], expected: dict[str, object], line: int) -> None:
    try:
        actual_json = canonical_json(event)
    except (TypeError, ValueError) as exc:
        raise TraceError(f"line {line}: event contains a non-JSON value") from exc
    if actual_json != canonical_json(expected):
        differing = next(
            key
            for key in sorted(event.keys() | expected.keys())
            if key not in event
            or key not in expected
            or canonical_json(event[key]) != canonical_json(expected[key])
        )
        raise TraceError(f"line {line}: {differing} differs from the replayed match")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TraceError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise TraceError(f"{value} is not a JSON value")


def replay_jsonl(lines: Iterable[str]) -> list[dict[str, object]]:
    active: _Replay | None = None
    results: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            event = json.loads(
                line, object_pairs_hook=_unique_keys, parse_constant=_reject_constant
            )
        except json.JSONDecodeError as exc:
            raise TraceError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        except TraceError as exc:
            raise TraceError(f"line {line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise TraceError(f"line {line_number}: expected a JSON object")

        if active is None:
            if event.get("type") != "start":
                raise TraceError(f"line {line_number}: expected a match start")
            active = _read_start(event)
            _expect(event, _start_event(active.spec, active.state), line_number)
        elif event.get("type") == "turn":
            if active.outcome.status != "ongoing":
                raise TraceError(f"line {line_number}: turn after the match ended")
            actor = active.game.current_player(active.state)
            if actor is None:
                raise TraceError(f"line {line_number}: ongoing game has no current player")
            expected, state, outcome = _turn_event(
                active.game, active.spec, active.state, actor, event.get("attempted_action")
            )
            _expect(event, expected, line_number)
            active.state, active.outcome = state, outcome
            active.turns += 1
        elif event.get("type") == "result":
            if active.outcome.status == "ongoing":
                raise TraceError(f"line {line_number}: result before a terminal turn")
            expected = _result_event(active.spec, active.state, active.outcome, active.turns)
            _expect(event, expected, line_number)
            results.append(expected)
            active = None
        else:
            raise TraceError(f"line {line_number}: expected a turn or result")

    if active is not None:
        raise TraceError("trace ends before a match result")
    if not results:
        raise TraceError("trace has no matches")
    return results
