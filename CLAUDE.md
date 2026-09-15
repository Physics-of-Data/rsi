# RSI Toy Example — repo notes for Claude Code

## What this project is

A Recursive Self-Improvement (RSI) toy experiment: a search loop discovers ODE integrators for the simple harmonic oscillator (SHO) from generic primitives, never from named methods. Read in this order before making changes:

1. `docs/What is Recursive Self Improvement.md` — original design conversation/transcript.
2. `docs/RSI Toy Example - Preparation.md` — the design doc (primitives, candidate problems, epsilon/plateau logic, checkpoint schema).
3. `docs/rsi-1st-attempt.md` — session report: what was built, four real bugs found and fixed with evidence, and the discovered solver's math.
4. `docs/next-steps.md` — the actionable checklist: tactical tuning items, and the strategic track (a stated auto-keep/auto-revert acceptance rule, a hyperparameter genome, automated stagnation remediation) needed to make this loop genuinely self-improving instead of person-in-the-loop.

Read `docs/rsi-1st-attempt.md` fully before touching `python/` — it explains *why* the code looks the way it does (the refine-burst, the fitness cap, the simulated-annealing acceptance, the negative-weight seeding range are all fixes for specific observed failures, not arbitrary choices).

## The one rule that must never be violated

**Never give the search a named solver, its known coefficients, or a hint that a named solver exists.** `python/genome.py`'s mutation primitives may only add/remove structure, perturb numbers, or switch between the two families — nothing may special-case "this configuration is RK4" or similar. The only place named solvers may appear is `java/` (the ground-truth/answer-key tool) and comments explaining *why* a primitive exists (e.g. "negative weights needed because Suzuki/Sanz-Serna..." is fine; seeding toward a specific known tableau is not).

## Directory conventions

- `baseline/FixedStepErrorLogEjsApp/` — a copy of an existing OSP/EJS app at `/storage/develop/opensourcephysics/06-cheerpJ/FixedStepErrorLogEjsApp`. That external original must never be modified — it's the user's own separate project. This copy exists so the RSI project is self-contained; treat it as a read-only reference unless the user asks otherwise.
- `java/` — self-contained (bundles `lib/osp.jar`, no dependency outside this directory). If you add new Java tools here, keep them self-contained the same way — copy any new OSP classes/jars in, don't reach into `baseline/` or the external OSP install path.
- `python/` — standard library only, no external dependencies (deliberate; keeps `make python-run` reproducible with a bare `python3`). If you're tempted to add numpy or similar, ask first — nothing so far has needed it, and the checkpoint JSON format assumes plain lists/floats.
- `python/checkpoints/`, `python/logs/`, `results/` — run artifacts. Safe to delete and regenerate (`make python-fresh`), but a given `checkpoint.json` plus its `fitness_log.jsonl` together are the evidence for a specific claimed discovery — don't overwrite one without the other.

## Known gotchas (discovered the hard way — see `docs/rsi-1st-attempt.md` §4 for the full evidence)

- SHO is linear, so distinct same-order/same-stage-count RK tableaux can be numerically indistinguishable on it (confirmed: EulerRichardson and Ralston2 give bit-identical results). Don't be surprised if two structurally different plain-family candidates score identically — it's not a bug.
- A strict greedy hill-climber gets permanently stuck; the loop uses simulated annealing (`python/loop.py`, `TEMP0`/`COOL_RATE`/`TEMP_MIN`) to escape. If you change the acceptance rule, re-verify it can still leave a local optimum (rerun `make python-fresh` and watch for `cur_fit` dropping below `best_ever` in the log, then recovering — that's the escape mechanism working).
- A freshly structurally-mutated candidate (`add_stage`, `remove_stage`, `switch_family`, `enable_dual_output`) is untuned and will lose an unfair one-shot comparison against an already-refined rival. `local_refine()` in `loop.py` gives it a short coefficient-only burst before judging — don't remove this without expecting growth to stall again.
- Fitness sums two `-log10(error)` terms; each is capped (`FITNESS_CAP` in `evaluate.py`) so a term that's already near the floating-point floor can't keep dominating the objective while another term is still large.
- A candidate's coefficients are only evaluated at one fixed `(dt=0.1, T=18, x0=1, v0=0)`. This is known to let the search over-fit to that exact condition (see the non-monotonic energy-error result in `docs/rsi-1st-attempt.md` §6) — a real next step is evaluating across multiple `(dt, IC)` pairs, not yet done.

## Running things

See `README.md`. Short version: `make java-build && make java-run` for the ground truth, `make python-fresh` for a clean RSI run.

## When extending the search

New primitives are welcome (the preparation doc and session report both suggest concrete ones: a `symmetrize` primitive, a gradient-informed polish mutation, multi-condition evaluation, cyclic annealing, multiple lineages) — but each new primitive should encode a piece of *general mathematical structure* (e.g. "reflect the sequence to be time-symmetric"), never a shortcut toward a specific known method's coefficients. If you're unsure whether a proposed primitive crosses that line, ask.
