"""Immutable game states and the public turn-taking contract."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal

type Player = Literal["X", "O"]
type Status = Literal["ongoing", "win", "draw"]
type Board = tuple[str, ...]

ACTION_SCHEMA = "taa.action.v1"
OBSERVATION_SCHEMA = "taa.observation.v1"
STATE_SCHEMA = "taa.state.v1"


def opponent(player: Player) -> Player:
    return "O" if player == "X" else "X"


def place(cell: str) -> dict[str, str]:
    return {"schema": ACTION_SCHEMA, "type": "place", "cell": cell}


class InvalidMove(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class State:
    game: str
    board: Board
    to_move: Player
    ply: int
    seed: int

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": STATE_SCHEMA,
            "game": self.game,
            "board": list(self.board),
            "to_move": self.to_move,
            "ply": self.ply,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class Observation:
    game: str
    ply: int
    you: Player
    board: Board
    goal: str
    legal: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": OBSERVATION_SCHEMA,
            "game": self.game,
            "ply": self.ply,
            "you": self.you,
            "board": list(self.board),
            "goal": self.goal,
            "legal": list(self.legal),
        }

    def render_ascii(self) -> str:
        heading = "    " + " ".join(str(column) for column in range(1, len(self.board) + 1))
        rows = [
            f"{chr(65 + index)}   " + " ".join(row)
            for index, row in enumerate(self.board)
        ]
        return "\n".join((heading, *rows))


@dataclass(frozen=True, slots=True)
class Outcome:
    status: Status
    winner: Player | None
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {"status": self.status, "winner": self.winner, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class Game:
    id: str
    size: int
    goal_x: str
    goal_o: str
    win_reason: str
    _wins: Callable[[Board, Player], bool] = field(repr=False, compare=False)

    def _check_state(self, state: State) -> None:
        if state.game != self.id:
            raise ValueError(f"state belongs to {state.game}, not {self.id}")

    def initial(self, seed: int) -> State:
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        return State(self.id, tuple("." * self.size for _ in range(self.size)), "X", 0, seed)

    def wins(self, board: Board, player: Player) -> bool:
        if player not in ("X", "O"):
            raise ValueError("player must be X or O")
        return self._wins(board, player)

    def outcome(self, state: State) -> Outcome:
        self._check_state(state)
        x_wins = self.wins(state.board, "X")
        o_wins = self.wins(state.board, "O")
        if x_wins and o_wins:
            raise ValueError("state has two winners")
        if x_wins:
            return Outcome("win", "X", self.win_reason)
        if o_wins:
            return Outcome("win", "O", self.win_reason)
        if state.ply == self.size * self.size:
            return Outcome("draw", None, "board-full")
        return Outcome("ongoing", None, "not-terminal")

    def current_player(self, state: State) -> Player | None:
        return state.to_move if self.outcome(state).status == "ongoing" else None

    def legal_actions(self, state: State, player: Player) -> tuple[str, ...]:
        self._check_state(state)
        if player not in ("X", "O"):
            raise ValueError("player must be X or O")
        if self.current_player(state) != player:
            return ()
        return tuple(
            f"{chr(65 + row)}{column + 1}"
            for row, cells in enumerate(state.board)
            for column, mark in enumerate(cells)
            if mark == "."
        )

    def observe(self, state: State, player: Player) -> Observation:
        self._check_state(state)
        if player not in ("X", "O"):
            raise ValueError("player must be X or O")
        return Observation(
            game=self.id,
            ply=state.ply,
            you=player,
            board=state.board,
            goal=self.goal_x if player == "X" else self.goal_o,
            legal=self.legal_actions(state, player),
        )

    def step(self, state: State, player: Player, action: object) -> State:
        self._check_state(state)
        if self.current_player(state) is None:
            raise InvalidMove("terminal", "no placements are allowed after the game ends")
        if player != state.to_move:
            raise InvalidMove("out-of-turn", f"{state.to_move} must move next")
        if (
            type(action) is not dict
            or action.keys() != {"schema", "type", "cell"}
            or action["schema"] != ACTION_SCHEMA
            or action["type"] != "place"
            or not isinstance(action["cell"], str)
        ):
            raise InvalidMove("malformed-action", "expected a versioned place action with one cell")

        cell = action["cell"]
        if cell not in {
            f"{chr(65 + row)}{column + 1}"
            for row in range(self.size)
            for column in range(self.size)
        }:
            raise InvalidMove("invalid-cell", f"{cell!r} is not a cell on this board")
        row, column = ord(cell[0]) - 65, int(cell[1:]) - 1
        if state.board[row][column] != ".":
            raise InvalidMove("occupied", f"{cell} is already occupied")

        board = list(state.board)
        board[row] = board[row][:column] + player + board[row][column + 1 :]
        return replace(state, board=tuple(board), to_move=opponent(player), ply=state.ply + 1)
