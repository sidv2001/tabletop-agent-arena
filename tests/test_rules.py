import unittest

from arena import InvalidMove, get_game, place
from arena.agents import RandomAgent, TacticalAgent


def play(game_name: str, cells: list[str]):
    game = get_game(game_name)
    state = game.initial(7)
    for cell in cells:
        player = game.current_player(state)
        if player is None:
            raise AssertionError("fixture tries to play after termination")
        state = game.step(state, player, place(cell))
    return game, state


class GameContractTests(unittest.TestCase):
    def test_initial_observations_are_player_filtered_and_immutable(self):
        for name, size in (("tic-tac-toe", 3), ("edgepaths-5", 5)):
            with self.subTest(game=name):
                game = get_game(name)
                state = game.initial(42)
                observation = game.observe(state, "X")
                self.assertEqual(game.current_player(state), "X")
                self.assertEqual(observation.board, tuple("." * size for _ in range(size)))
                self.assertEqual(len(observation.legal), size * size)
                self.assertEqual(observation.legal[0], "A1")
                self.assertEqual(observation.legal[-1], f"{chr(64 + size)}{size}")
                self.assertEqual(game.observe(state, "O").legal, ())
                self.assertEqual(observation.as_dict()["schema"], "taa.observation.v1")
                self.assertNotIn("seed", observation.as_dict())
                self.assertFalse(hasattr(observation, "state"))
                self.assertEqual(len(observation.render_ascii().splitlines()), size + 1)
                encoded = observation.as_dict()
                encoded["board"][0] = "X" * size
                self.assertEqual(state.board[0], "." * size)

    def test_invalid_placements_do_not_change_a_state(self):
        game = get_game("tic-tac-toe")
        state = game.initial(42)
        before = state.as_dict()
        invalid = (
            ({"schema": "taa.action.v1", "type": "place"}, "malformed-action"),
            ({"schema": "taa.action.v1", "type": "place", "cell": "A1", "extra": 1}, "malformed-action"),
            ({"schema": "taa.action.v2", "type": "place", "cell": "A1"}, "malformed-action"),
            ("A1", "malformed-action"),
            (place("a1"), "invalid-cell"),
            (place("D1"), "invalid-cell"),
            (place("A0"), "invalid-cell"),
        )
        for action, code in invalid:
            with self.subTest(action=action):
                with self.assertRaises(InvalidMove) as caught:
                    game.step(state, "X", action)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(state.as_dict(), before)
                self.assertEqual(game.current_player(state), "X")

        with self.assertRaises(InvalidMove) as caught:
            game.step(state, "O", place("A1"))
        self.assertEqual(caught.exception.code, "out-of-turn")
        self.assertEqual(state.as_dict(), before)

        next_state = game.step(state, "X", place("A1"))
        self.assertEqual(state.as_dict(), before)
        self.assertEqual(next_state.board[0], "X..")
        with self.assertRaises(InvalidMove) as caught:
            game.step(next_state, "O", place("A1"))
        self.assertEqual(caught.exception.code, "occupied")
        self.assertEqual(next_state.board[0], "X..")

    def test_tic_tac_toe_wins_draws_and_terminal_rejection(self):
        for moves, status, winner in (
            (["A1", "B1", "A2", "B2", "A3"], "win", "X"),
            (["B1", "A1", "B2", "A2", "C3", "A3"], "win", "O"),
            (["A1", "A2", "A3", "B1", "B3", "B2", "C1", "C3", "C2"], "draw", None),
        ):
            with self.subTest(moves=moves):
                game, state = play("tic-tac-toe", moves)
                self.assertEqual((game.outcome(state).status, game.outcome(state).winner), (status, winner))
                self.assertIsNone(game.current_player(state))
                self.assertEqual(game.legal_actions(state, "X"), ())
                with self.assertRaises(InvalidMove) as caught:
                    game.step(state, "X", place("A1"))
                self.assertEqual(caught.exception.code, "terminal")
                self.assertEqual(state.ply, len(moves))

    def test_edgepaths_requires_orthogonal_connections(self):
        game, state = play(
            "edgepaths-5",
            ["A1", "B1", "A2", "B2", "A3", "B3", "A4", "B4", "A5"],
        )
        self.assertEqual(game.outcome(state).winner, "X")
        self.assertEqual(game.outcome(state).reason, "connected-edges")
        self.assertEqual(state.ply, 9)

        game, state = play(
            "edgepaths-5",
            ["A2", "A1", "B2", "B1", "C2", "C1", "D2", "D1", "E2", "E1"],
        )
        self.assertEqual(game.outcome(state).winner, "O")
        self.assertEqual(state.ply, 10)

        diagonal = ("X....", ".X...", "..X..", "...X.", "....X")
        self.assertFalse(game.wins(diagonal, "X"))

    def test_edgepaths_can_fill_without_a_connection(self):
        game = get_game("edgepaths-5")
        state = game.initial(0)
        x_cells = [
            f"{chr(65 + row)}{column + 1}"
            for row in range(5)
            for column in range(5)
            if (row + column) % 2 == 0
        ]
        o_cells = [
            f"{chr(65 + row)}{column + 1}"
            for row in range(5)
            for column in range(5)
            if (row + column) % 2 == 1
        ]
        for x_cell, o_cell in zip(x_cells, o_cells):
            state = game.step(state, "X", place(x_cell))
            state = game.step(state, "O", place(o_cell))
        state = game.step(state, "X", place(x_cells[-1]))
        self.assertEqual(state.ply, 25)
        self.assertEqual(game.outcome(state).status, "draw")
        self.assertEqual(game.outcome(state).reason, "board-full")
        self.assertIsNone(game.current_player(state))

    def test_both_games_terminate_in_seeded_random_play(self):
        for name in ("tic-tac-toe", "edgepaths-5"):
            game = get_game(name)
            for seed in range(20):
                with self.subTest(game=name, seed=seed):
                    agent = RandomAgent(seed)
                    state = game.initial(seed)
                    while (player := game.current_player(state)) is not None:
                        action = agent.choose(game.observe(state, player))
                        state = game.step(state, player, action)
                        self.assertLessEqual(state.ply, game.size * game.size)
                    self.assertIn(game.outcome(state).status, ("win", "draw"))

    def test_tactical_agent_takes_a_win_then_blocks_one(self):
        game, state = play("tic-tac-toe", ["A1", "B1", "A2", "B2"])
        self.assertEqual(TacticalAgent(1).choose(game.observe(state, "X")), place("A3"))

        game, state = play("tic-tac-toe", ["A1", "B1", "C3", "B2"])
        self.assertEqual(TacticalAgent(1).choose(game.observe(state, "X")), place("B3"))

        game, state = play(
            "edgepaths-5",
            ["A2", "A1", "B2", "B1", "C2", "C1", "D2", "D1", "E2"],
        )
        self.assertEqual(TacticalAgent(1).choose(game.observe(state, "O")), place("E1"))

    def test_all_reachable_tic_tac_toe_states_finish_by_ply_nine(self):
        game = get_game("tic-tac-toe")
        pending = [game.initial(0)]
        seen = set()
        while pending:
            state = pending.pop()
            if state in seen:
                continue
            seen.add(state)
            self.assertLessEqual(state.ply, 9)
            player = game.current_player(state)
            if player is None:
                self.assertIn(game.outcome(state).status, ("win", "draw"))
                self.assertEqual(game.legal_actions(state, "X"), ())
                self.assertEqual(game.legal_actions(state, "O"), ())
            else:
                self.assertTrue(game.legal_actions(state, player))
                pending.extend(
                    game.step(state, player, place(cell))
                    for cell in game.legal_actions(state, player)
                )
        self.assertGreater(len(seen), 1000)


if __name__ == "__main__":
    unittest.main()
