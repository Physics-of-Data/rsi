# RSI Toy Example: Discovering ODE Solvers from Calculus Primitives

A small Recursive Self-Improvement (RSI) experiment: a search loop that discovers ODE integrators for the simple harmonic oscillator (SHO) starting only from generic primitives (evaluate a derivative, combine evaluations, optionally split position/velocity updates) — never handed a named method (Euler, RK4, Verlet, Euler-Cromer...). Named methods exist only as a ground-truth "answer key" to grade discoveries against.

Background and design rationale: `docs/What is Recursive Self Improvement.md` (the original transcript) and `docs/RSI Toy Example - Preparation.md` (the design doc). What actually happened when it was run: `docs/rsi-1st-attempt.md`.

## Layout

```
baseline/FixedStepErrorLogEjsApp/   Reference copy of an existing OSP/EJS SHO app (Java GUI, do not need to run it)
java/                                Self-contained headless ground-truth tool (real OSP solvers vs. analytic solution)
python/                              The RSI search loop
results/                             Ground-truth comparison CSV
docs/                                Session report
```

## Requirements

- **Java**: JDK 11+ (developed/tested on OpenJDK 17). No Maven/Gradle — plain `javac`/`java`, dependency (`osp.jar`) is bundled in `java/lib/`.
- **Python**: 3.8+. No external packages — standard library only (`random`, `math`, `json`, `pickle`, `argparse`).

## Reproduce the ground truth (Java)

```
make java-build
make java-run
```

Runs Euler, EulerCromer, EulerRichardson, Ralston2, Heun3, RK4, Verlet, LeapFrog, Butcher5, Fehlberg8 on SHO (`x''=-kx`, `x0=1, v0=0, k=1`) at `dt ∈ {0.1, 0.05, 0.01}`, scores each against the closed-form solution `x(t)=cos(t)`, and writes `results/sho_solver_comparison.csv`. See `java/README.md` for details.

## Run the RSI search loop (Python)

```
make python-fresh     # ignore any existing checkpoint, start from a 1-stage seed
# or
make python-run       # resume from python/checkpoints/checkpoint.json if present
```

Or directly:

```
cd python
python3 loop.py --fresh --generations 5000
```

Progress prints every 50 generations (current fitness, best-ever fitness, family, stage count, errors, temperature, sigma). On stop, it prints the best-ever discovered candidate (its `(A,b,c)` tableau or kick/drift sequence) and its metrics.

**Outputs** (all under `python/`, gitignored contents regenerate on any run):
- `checkpoints/checkpoint.json` — latest full state, overwritten every generation.
- `checkpoints/checkpoint_genNNNNNN.json` — named snapshot every 100 generations, never overwritten.
- `logs/fitness_log.jsonl` — append-only, one JSON line per generation.

To inspect the best-ever candidate from a finished run:

```python
import json, evaluate
state = json.load(open("python/checkpoints/checkpoint.json"))
cand = state["best_ever"]["candidate"]
print(cand)
print(evaluate.evaluate(cand, dt=0.1, T=18.0))
```

## Design in one paragraph

Two candidate "families" (`python/genome.py`): a **plain** variable-stage explicit Runge-Kutta tableau, and a **partitioned** kick/drift sequence for the separable `x'=v, v'=-kx` system (needed because Verlet/Euler-Cromer aren't reachable from a plain RK tableau at all). Mutation primitives add/remove stages, perturb coefficients, enable an adaptive-style embedded pair, or switch families — `switch_family` is judged by the same success-rate policy as everything else, so nothing hints that the partitioned family is worth trying. See `docs/rsi-1st-attempt.md` for what was actually discovered, four real bugs found and fixed along the way, and what would need to change to make the loop genuinely self-improving rather than person-in-the-loop.

## Status

v1: discovers a genuine 2nd-order symplectic (kick/drift) method from scratch, empirically confirmed at 7 stages with one negative coefficient. Not yet reaching RK4-level (4th-order) accuracy — see `docs/rsi-1st-attempt.md` §7-8 for why, and the concrete next steps.
