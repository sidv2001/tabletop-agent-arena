"""Seeded offline policies that receive observations, never engine states."""

import random
from typing import Protocol

from .core import Board, Observation, Player, opponent, place
from .games import get_game

AGENT_NAMES = ("random", "tactical")


class Agent(Protocol):
    name: str

    def choose(self, observation: Observation) -> object: ...


class RandomAgent:
    name = "random"

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def choose(self, observation: Observation) -> dict[str, str]:
        if not observation.legal:
            raise ValueError("random agent needs an observation with legal actions")
        return place(self._rng.choice(observation.legal))


def _with_mark(board: Board, cell: str, player: Player) -> Board:
    row, column = ord(cell[0]) - 65, int(cell[1:]) - 1
    result = list(board)
    result[row] = result[row][:column] + player + result[row][column + 1 :]
    return tuple(result)


class TacticalAgent:
    name = "tactical"

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def choose(self, observation: Observation) -> dict[str, str]:
        if not observation.legal:
            raise ValueError("tactical agent needs an observation with legal actions")
        game = get_game(observation.game)
        winning = [
            cell
            for cell in observation.legal
            if game.wins(_with_mark(observation.board, cell, observation.you), observation.you)
        ]
        if winning:
            return place(self._rng.choice(winning))

        rival = opponent(observation.you)
        blocking = [
            cell
            for cell in observation.legal
            if game.wins(_with_mark(observation.board, cell, rival), rival)
        ]
        return place(self._rng.choice(blocking or observation.legal))


def create_agent(name: str, seed: int) -> Agent:
    if type(seed) is not int or seed < 0:
        raise ValueError("agent seed must be a non-negative integer")
    if name == "random":
        return RandomAgent(seed)
    if name == "tactical":
        return TacticalAgent(seed)
    raise ValueError(f"unknown agent {name!r}; choose from {', '.join(AGENT_NAMES)}")
