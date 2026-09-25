import json
import subprocess
import sys
import unittest

from arena import place
from arena.agents import RandomAgent
from arena.matches import (
    MatchSpec,
    Seat,
    TraceError,
    canonical_json,
    derive_agent_seed,
    hash_json,
    replay_jsonl,
    run_match,
    schedule,
)


class FixedAgent:
    def __init__(self, name: str, cell: str) -> None:
        self.name = name
        self.cell = cell

    def choose(self, observation):
        return place(self.cell)


def trace(spec):
    return [canonical_json(event) for event in run_match(spec)]


class MatchTests(unittest.TestCase):
    def test_schedule_swaps_entrants_but_preserves_their_seeds(self):
        specs = list(schedule("edgepaths-5", ("random", "tactical"), 42, seeds=2, swap_seats=True))
        self.assertEqual(len(specs), 4)
        self.assertEqual([(spec.seed, spec.x.entrant) for spec in specs], [
            (42, "A"), (42, "B"), (43, "A"), (43, "B")
        ])
        first = list(run_match(specs[0]))[0]
        swapped = list(run_match(specs[1]))[0]
        self.assertEqual(first["seats"]["X"]["seed"], swapped["seats"]["O"]["seed"])
        self.assertEqual(first["seats"]["O"]["seed"], swapped["seats"]["X"]["seed"])
        self.assertNotEqual(first["seats"]["X"]["seed"], first["seats"]["O"]["seed"])
        reversed_agents = next(schedule("edgepaths-5", ("tactical", "random"), 42))
        self.assertNotEqual(specs[0].id, reversed_agents.id)

    def test_recorded_actions_replay_deterministically_in_both_seat_orders(self):
        specs = list(schedule("edgepaths-5", ("random", "tactical"), 42, swap_seats=True))
        first = [line for spec in specs for line in trace(spec)]
        second = [line for spec in specs for line in trace(spec)]
        self.assertEqual(first, second)
        results = replay_jsonl(first)
        self.assertEqual(len(results), 2)
        self.assertEqual([event["type"] for event in map(json.loads, first)].count("start"), 2)
        for result in results:
            self.assertIn(result["outcome"]["status"], ("win", "draw"))
            self.assertLessEqual(result["plies"], 25)
            self.assertEqual(result["plies"], result["turns"])

    def test_an_occupied_move_is_a_recorded_forfeit_without_mutation(self):
        spec = MatchSpec("tic-tac-toe@1", 17, Seat("A", "fixed-x"), Seat("B", "fixed-o"))
        agents = {"X": FixedAgent("fixed-x", "A1"), "O": FixedAgent("fixed-o", "A1")}
        events = list(run_match(spec, agents))
        start, valid, invalid, result = events
        self.assertIsNone(valid["error"])
        self.assertEqual(valid["accepted_action"], place("A1"))
        self.assertEqual(invalid["error"]["code"], "occupied")
        self.assertEqual(invalid["attempted_action"], place("A1"))
        self.assertIsNone(invalid["accepted_action"])
        self.assertEqual(invalid["state_hash"], valid["state_hash"])
        self.assertNotEqual(invalid["state_hash"], start["state_hash"])
        self.assertEqual(result["outcome"], {
            "status": "win", "winner": "X", "reason": "forfeit:occupied"
        })
        self.assertEqual((result["plies"], result["turns"]), (1, 2))
        self.assertEqual(replay_jsonl(map(canonical_json, events)), [result])

    def test_a_malformed_json_action_forfeits_without_placement(self):
        spec = MatchSpec("tic-tac-toe@1", 17, Seat("A", "bad"), Seat("B", "random"))

        class BadAgent:
            name = "bad"

            def choose(self, observation):
                return {"schema": "taa.action.v1", "type": "place", "cell": "A1", "extra": True}

        agents = {
            "X": BadAgent(),
            "O": RandomAgent(derive_agent_seed(spec.seed, "B")),
        }
        events = list(run_match(spec, agents))
        self.assertEqual(len(events), 3)
        self.assertEqual(events[1]["error"]["code"], "malformed-action")
        self.assertEqual(events[1]["state_hash"], events[0]["state_hash"])
        self.assertEqual(events[2]["outcome"]["reason"], "forfeit:malformed-action")
        self.assertEqual(replay_jsonl(map(canonical_json, events)), [events[-1]])

    def test_tampered_or_incomplete_traces_are_rejected(self):
        spec = next(schedule("tic-tac-toe", ("random", "tactical"), 4))
        events = list(run_match(spec))
        changes = (
            (1, "actor", "O"),
            (1, "observation_hash", "0" * 64),
            (1, "state_hash", "0" * 64),
            (-1, "plies", False),
        )
        for index, field, replacement in changes:
            with self.subTest(field=field):
                tampered = json.loads(canonical_json(events))
                tampered[index][field] = replacement
                with self.assertRaises(TraceError):
                    replay_jsonl(map(canonical_json, tampered))

        with self.assertRaisesRegex(TraceError, "before a match result"):
            replay_jsonl(map(canonical_json, events[:-1]))
        with self.assertRaisesRegex(TraceError, "duplicate JSON key"):
            replay_jsonl(['{"type":"start","type":"start"}'])
        with self.assertRaisesRegex(TraceError, "not a JSON value"):
            replay_jsonl(['{"type":NaN}'])
        with self.assertRaises(TraceError):
            replay_jsonl(["not JSON"])

    def test_observation_hash_covers_only_the_player_view(self):
        spec = next(schedule("tic-tac-toe", ("random", "tactical"), 4))
        events = list(run_match(spec))
        first_turn = events[1]
        self.assertNotIn("seed", first_turn["observation"])
        self.assertNotIn("state", first_turn["observation"])
        self.assertEqual(first_turn["observation_hash"], hash_json(first_turn["observation"]))
        self.assertEqual(first_turn["observation"]["you"], "X")

    def test_module_cli_emits_valid_jsonl_and_replays_it(self):
        match = subprocess.run(
            [
                sys.executable, "-m", "arena.cli", "match", "--game", "tic-tac-toe",
                "--agents", "random,tactical", "--seed", "42", "--swap-seats",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        replay = subprocess.run(
            [sys.executable, "-m", "arena.cli", "replay", "-"],
            input=match.stdout,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(replay.stderr, "")
        self.assertEqual(len(replay.stdout.splitlines()), 2)
        self.assertEqual(
            [json.loads(line) for line in replay.stdout.splitlines()],
            replay_jsonl(match.stdout.splitlines()),
        )


if __name__ == "__main__":
    unittest.main()
