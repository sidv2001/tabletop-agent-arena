"""Original rules for two public-domain/original-mechanics games."""

from collections import deque

from .core import Board, Game, Player


def _three_in_a_row(board: Board, player: Player) -> bool:
    return (
        any(all(board[row][column] == player for column in range(3)) for row in range(3))
        or any(all(board[row][column] == player for row in range(3)) for column in range(3))
        or all(board[index][index] == player for index in range(3))
        or all(board[index][2 - index] == player for index in range(3))
    )


def _connected_edges(board: Board, player: Player) -> bool:
    size = len(board)
    if player == "X":
        starts = [(row, 0) for row in range(size) if board[row][0] == player]
    else:
        starts = [(0, column) for column in range(size) if board[0][column] == player]

    frontier = deque(starts)
    visited = set(starts)
    while frontier:
        row, column = frontier.popleft()
        if (player == "X" and column == size - 1) or (
            player == "O" and row == size - 1
        ):
            return True
        for next_row, next_column in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            neighbor = (next_row, next_column)
            if (
                0 <= next_row < size
                and 0 <= next_column < size
                and neighbor not in visited
                and board[next_row][next_column] == player
            ):
                visited.add(neighbor)
                frontier.append(neighbor)
    return False


_GAMES = {
    "tic-tac-toe": Game(
        id="tic-tac-toe@1",
        size=3,
        goal_x="make three X marks in one row, column, or diagonal",
        goal_o="make three O marks in one row, column, or diagonal",
        win_reason="three-in-a-row",
        _wins=_three_in_a_row,
    ),
    "edgepaths-5": Game(
        id="edgepaths-5@1",
        size=5,
        goal_x="connect west to east with orthogonally adjacent X marks",
        goal_o="connect north to south with orthogonally adjacent O marks",
        win_reason="connected-edges",
        _wins=_connected_edges,
    ),
}


def game_names() -> tuple[str, ...]:
    return tuple(_GAMES)


def get_game(name: str) -> Game:
    for short_name, game in _GAMES.items():
        if name == short_name or name == game.id:
            return game
    raise ValueError(f"unknown game {name!r}; choose from {', '.join(game_names())}")
