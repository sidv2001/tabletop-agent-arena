# Evaluation plan and trace contract

## What runs now

`python3.12 -m arena.cli match --game edgepaths-5 --agents random,tactical --seed 42 --swap-seats`
plays one seed in both orders, with entrants A and B retaining their own
SHA-256-derived RNG seeds when seats switch. `--seeds 50` uses 50 consecutive
match seeds. Both offline agents consume only `taa.observation.v1` views; no
provider key or model call is involved. `python3.12 -m arena.cli replay -`
reads JSONL on standard input; pass a file path instead to replay a saved
transcript. A truncated or altered transcript fails explicitly.

Each match writes a `taa.trace.v1` **start**, one **turn** per attempted
placement, and a **result**. Start records the versioned game, match seed,
seat/entrant/agent labels, derived agent seeds, and initial state hash. Turn
records actor, complete player observation, observation hash, attempted
action, accepted action or explicit error, resulting state hash, and outcome.
Match IDs include the game version, seed, X entrant, and a short digest of
both seat/agent assignments.
Result records final outcome, accepted placements (`plies`), attempted turns,
and final state hash. Hashes are SHA-256 of UTF-8 JSON with sorted keys,
compact separators, ASCII escaping, and no NaN. An illegal action creates a
forfeit outcome without changing the engine state. Replay reconstructs the
game from the seed and recorded actions, checks every event, and never calls
an agent again. These unkeyed hashes are consistency checks, not
authentication or an attestation of how an agent made its choice.
Local Python agents must return JSON-serializable actions; an unsupported
Python object raises an error rather than producing a complete transcript.

## Measurements to add

A first comparison can run 50 seeds x two seat orders x two games = **200
matches** for random versus tactical. Report wins/draws/losses separately by
game and seat, paired score differences with uncertainty resampled over
**seed pairs**, game-length distribution, and invalid-action counts. Do not
pool these games into a general-reasoning score. Add a solved tic-tac-toe
reference before using it as a calibration matchup; this policy and a
reporting/uncertainty CLI are planned, not part of the starter.

An optional hosted-model pilot would use eight seeds x two orders x two games
= **32 matches** against tactical. At most 272 model decisions occur across
those complete pairs if every game reaches its 9- or 25-ply limit. A proposed
per-decision ceiling is 1,000 input tokens, 128 output tokens, and 15 seconds
(272,000 input and 34,816 output tokens in total). Before any such run:
authorize a provider-price-based spending cap, log the model/prompt version
and actual usage, and mark interrupted pairs incomplete. Future poker needs
explicit chance events, private-observation tests, and content-rights review.
