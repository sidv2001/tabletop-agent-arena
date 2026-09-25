# Research and positioning

General game interfaces, text observations, and agent comparisons have deep
prior art. This starter's narrower contribution is an original two-game
implementation whose player view, engine-checked action, paired seats, and
replay can be inspected together. These sources informed the design; no code,
rulebook text, cards, artwork, or datasets were imported from them.

| Source | Relevant precedent |
| --- | --- |
| [GGP Base](https://github.com/ggp-org/ggp-base) and the [GDL specification](http://ggp.stanford.edu/readings/gdl_spec.pdf) | Initial state, roles, legal moves, next state, terminal status, and goals are established concepts. |
| [OpenSpiel](https://github.com/google-deepmind/open_spiel/blob/master/docs/concepts.md) | Separates games from states, chance from player turns, and a player's observation from an information state. This matters before adding hidden cards. |
| [PettingZoo](https://github.com/Farama-Foundation/PettingZoo/blob/main/docs/api/aec.md) | Turn-taking agent/environment interactions and explicit legal-action masks provide useful interface comparisons. |
| [RLCard](https://github.com/datamllab/rlcard/blob/master/rlcard/envs/limitholdem.py) | Its acting-player observation and separate perfect-information view underline why future card agents must not receive internal state. |
| [GameBench](https://github.com/Joshuaclymer/GameBench) and its [paper](https://arxiv.org/abs/2406.06613) | Already evaluates agents across games with text/image observations, legal choices, match data, and ratings. Fixed paired seats here are an audit choice, not a new benchmark technique. |
| [TextArena](https://github.com/TextArena/TextArena) | Text-based games and agent matches exist at much larger scale. Its game catalog is research context, not an asset library for this repository. |
| [BALROG](https://github.com/balrog-ai/BALROG/blob/main/balrog/evaluator.py) | Seeded trajectories, outcomes, and usage records are established evaluation practices. |
| [Ludii](https://github.com/Ludeme/Ludii) | A mature general-game system; its CC BY-NC-ND source is not incorporated into this MIT project. |

The [U.S. Copyright Office's games guidance](https://www.copyright.gov/register/tx-games.html)
distinguishes game methods from protected written and graphic expression.
That distinction guides original rules wording and visuals, but it does not
grant rights to a commercial card catalog, branded artwork, or another
project's implementation. See the [rights policy](rights.md).

Both included games are deterministic, turn-taking, and perfect-information.
Tic-tac-toe is a rules sanity check; Edgepaths-5 permits up to 25 placements.
Neither game supplies evidence about performance in private-information or
longer, more complex strategy settings. Replay hashes detect inconsistencies
within a trace, not who authored it or whether a recorded agent used outside
information. The [evaluation plan](evaluation.md) defines what to measure
before interpreting comparisons.
