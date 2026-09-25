import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from arena import get_game, place

ROOT = Path(__file__).resolve().parents[1]


class BoardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_board = False
        self.board_parts: list[str] = []
        self.svg_attributes: dict[str, str | None] = {}
        self.svg_title = False
        self.svg_description = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "pre" and attributes.get("id") == "board-ascii":
            self.in_board = True
        if tag == "svg":
            self.svg_attributes = attributes
        if tag == "title" and attributes.get("id") == "svg-title":
            self.svg_title = True
        if tag == "desc" and attributes.get("id") == "svg-desc":
            self.svg_description = True

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_board = False

    def handle_data(self, data):
        if self.in_board:
            self.board_parts.append(data)


class PresentationTests(unittest.TestCase):
    def test_scripted_ascii_board_matches_the_engine(self):
        html = (ROOT / "docs/illustrative-replay.html").read_text(encoding="utf-8")
        parser = BoardParser()
        parser.feed(html)
        game = get_game("edgepaths-5")
        state = game.initial(0)
        for cell in ("A1", "B3", "A2", "C3", "A3"):
            player = game.current_player(state)
            self.assertIsNotNone(player)
            state = game.step(state, player, place(cell))

        observation = game.observe(state, "O")
        self.assertEqual("".join(parser.board_parts), observation.render_ascii())
        self.assertIn("A4", observation.legal)
        self.assertIn("D3", observation.legal)
        self.assertEqual(parser.svg_attributes["role"], "img")
        self.assertEqual(parser.svg_attributes["aria-labelledby"], "svg-title svg-desc")
        self.assertTrue(parser.svg_title)
        self.assertTrue(parser.svg_description)
        self.assertIn("prefers-reduced-motion: reduce", html)

    def test_versioned_action_and_observation_schemas_match_outputs(self):
        game = get_game("tic-tac-toe")
        observation = game.observe(game.initial(0), "X").as_dict()
        for filename, value in (
            ("observation-v1.json", observation),
            ("action-v1.json", place("A1")),
        ):
            with self.subTest(filename=filename):
                schema = json.loads((ROOT / "schemas" / filename).read_text())
                self.assertEqual(set(value), set(schema["required"]))
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(value["schema"], schema["properties"]["schema"]["const"])
                self.assertTrue(schema["$schema"].endswith("2020-12/schema"))

    def test_proposal_length_and_original_rights_note(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        prose = re.sub(r"```.*?```", "", readme, flags=re.DOTALL)
        self.assertLessEqual(len(prose.split()), 500)
        self.assertGreaterEqual(len(prose.split()), 350)
        self.assertIn("Illustrative position, scripted", readme)
        self.assertIn("docs/rights.md", readme)


if __name__ == "__main__":
    unittest.main()
