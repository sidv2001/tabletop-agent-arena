# Tabletop Agent Arena

I want to see what happens when an agent has to live with a decision. In a board
game, one move changes the choices available next turn; a promising route can
become a trap, and an unremarkable block can matter five moves later. Tabletop
Agent Arena is a small, inspectable place to explore those chains. I care about
the board an agent actually saw, the legal options it had, and the move it
chose, not only the final winner.

The first playable version has two games. Traditional **tic-tac-toe** gives the
rules and replay machinery a compact check. **Edgepaths-5** is an original
five-by-five placement game: X builds an orthogonal chain from the west edge to
the east edge; O connects north to south. Players alternate in empty cells,
with no passes or diagonal links. A connection wins immediately; a full board
without one is a draw. Its 25-placement ceiling gives a longer sequence to
inspect without making the rules hard to follow.

With Python 3.12, from this directory, run an offline pair and replay it:

```sh
python3.12 -m arena.cli match --game edgepaths-5 --agents random,tactical --seed 42 --swap-seats > match.jsonl
python3.12 -m arena.cli replay match.jsonl
python3.12 -m unittest discover -s tests -v
```

The first command plays the same seed in both seat orders. `--seeds 50` schedules
50 successive pairs. The seeded random policy chooses a legal cell; the
tactical policy takes an immediate win, occupies one cell that would give its
opponent a win next turn, or otherwise makes a seeded legal choice. Agents
receive a player-facing observation, not the engine's state. The engine checks
every placement. An invalid JSON action forfeits the match and leaves the
board unchanged.

**Illustrative position, scripted rather than played by an agent:** X places
A1, A2, and A3 while O places B3 and C3. O now has a choice: A4 interrupts X's
top-row route; D3 extends O's vertical chain. Neither option is presented as
a measured policy choice. The [accessible board preview](docs/illustrative-replay.html)
shows this position with an SVG, the same board in ASCII, and the full move
sequence.

Each JSONL turn records the observation and its hash, the attempted and
accepted action or error, and the resulting state hash. Replay applies recorded
actions again; it does not ask an agent to repeat a decision. The versioned
[observation](schemas/observation-v1.json) and [action](schemas/action-v1.json)
formats make that boundary visible.

Next I want paired, per-seat summaries with uncertainty over seeds, a solved
tic-tac-toe reference, and human-labeled branches from saved positions. Poker
or larger strategy games would need chance and private-view tests before they
join the arena. Hosted models would be opt-in with explicit budgets; this
starter makes no provider calls. The [evaluation plan](docs/evaluation.md)
explains that path, [research notes](docs/research.md) place this work beside
existing game arenas, and the [rights policy](docs/rights.md) covers new game
packs. Original code, prose, and artwork here are MIT-licensed; the existing
[LICENSE](LICENSE) is unchanged.
