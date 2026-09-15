---
date: 2026-09-15
tags: [rsi, recursive-self-improvement, ode-solvers, sho, symplectic, session-report]
---

# RSI First Attempt — Session Report

This is a faithful record of the session that took the preparation document (`RSI Toy Example - Preparation.md`) and turned it into a working, self-modifying search that discovers ODE integrators from calculus primitives — plus what it actually found, why it stalled where it did, and what would need to change to make it genuinely autonomous.

## 1. Starting point

The goal, carried over from the preparation document: build a small evolutionary loop that discovers ODE solvers for the simple harmonic oscillator (SHO, `x''=-kx`) starting only from generic primitives (evaluate a derivative, combine evaluations, optionally split position/velocity updates) — never handing the search a named method (Euler, RK4, Verlet, Euler-Cromer...). Those named methods exist only as an "answer key" to grade discoveries against, never as a menu.

Two open questions carried into this session:
1. Java (reusing the existing OSP baseline) or Python for the search loop itself?
2. Should we run the SHO problem through every named OSP solver first, to calibrate the search's epsilon thresholds against real numbers, before writing any search code?

Both were resolved quickly: **Python for the search loop** (fast iteration on the discovery mechanism, no GUI dependency), but shaped so a winning candidate could later drop into a new `ODESolver` implementation in the existing Java/OSP app; and **yes, run the ground truth first** — calibrating against guessed epsilon values would have been building on sand.

## 2. Ground-truth baseline (Java)

A small headless tool (`java/SHOSolverComparison.java`) was built using the real OSP `numerics` library classes — not reimplementations — so the "answer key" is authoritative:

- `SHO.java` implements OSP's `ODE` interface (`x'=v`, `v'=-kx`).
- `CountingODE.java` wraps the ODE to count derivative-oracle calls exactly, giving a real `num_f_evals` cost metric per solver.
- `EulerCromer.java` was hand-written (semi-implicit Euler) since it isn't bundled in `osp.jar`'s numerics package.
- `SHOSolverComparison.java` runs Euler, EulerCromer, EulerRichardson, Ralston2, Heun3, RK4, Verlet, LeapFrog, Butcher5, and Fehlberg8 across `dt ∈ {0.1, 0.05, 0.01}`, `T=18`, `x0=1, v0=0, k=1`, and scores each against the closed-form analytic solution `x(t)=cos(t)`, `E=0.5` — the same error-table methodology as your existing `FixedStepErrorLogEjsApp` baseline app (which was copied into `baseline/` as a reference; the original at `/storage/develop/opensourcephysics/06-cheerpJ/FixedStepErrorLogEjsApp` was left untouched).

**Findings from the ground truth, before any search code ran:**

- **Euler-Cromer dramatically outperforms plain Euler** at the same step size (position error ~20× smaller) despite being the same formal order — the textbook symplectic signature: bounded energy error instead of runaway growth.
- **EulerRichardson and Ralston2 produce bit-identical numbers.** Both are 2-stage, order-2 explicit RK methods, and for a *linear* ODE the stability function is fully determined by (stages, order) regardless of the free tableau coefficient — that coefficient only matters on nonlinear problems. Implication for the search: SHO can validate that it found the right *order/family*, but can't uniquely identify tableau coefficients within an order.
- **Verlet vs. LeapFrog**: identical position error, but LeapFrog uses about half the derivative evaluations (it reuses the previous step's force) — a clean real example of a cost/efficiency tradeoff between two structurally-related methods.
- **Fehlberg8 hits the floating-point noise floor (~1e-14) even at dt=0.1** — the empirical basis for the `~1e-10` "stop, we've hit machine precision" threshold used later.

Full table: `results/sho_solver_comparison.csv`.

## 3. Python RSI loop — design

`python/genome.py` defines two candidate "families," chosen by the search itself and never named to it:

- **Plain family**: a variable-size explicit Runge-Kutta tableau (`A`, `b`, `c`, optional embedded `b*`). The minimal member (1 stage, weight 1) happens to be forward Euler — reached because it's the smallest thing expressible in the grammar, not because it was seeded as "Euler."
- **Partitioned family**: a sequence of `kick` (`v += α·h·f_v(x)`) and `drift` (`x += α·h·f_x(v)`) sub-steps. The minimal member (one kick, one drift) happens to be Euler-Cromer, reached the same way.

Mutation primitives: `add_stage`, `remove_stage`, `perturb_coefficient`, `enable_dual_output` (embedded error-estimate pair), `switch_family` (jump between the two families), and the hard rule `normalize_consistency` (`Σb=1`, or `Σkicks=1` and `Σdrifts=1` separately) applied before any candidate is scored — without it a method wouldn't converge to the right answer at all.

`python/evaluate.py` scores a candidate by running it on SHO at fixed `dt=0.1` out to `T=18` and computing:
```
fitness = pos_term + w_E * energy_term - λ_cost * log10(num_f_evals)
```
where `pos_term`/`energy_term` are (capped) `-log10(rms error)` against the closed-form solution.

`python/policy.py` is where the actually-recursive part lives: an exponential moving average of each mutation type's success rate, with proposals sampled proportional to that success rate (plus an exploration floor so nothing is ever permanently foreclosed) — the loop's own strategy for proposing changes gets rewritten by what has been paying off, not just the coefficients.

`python/loop.py` is the generational driver: `propose → evaluate → accept/reject → update policy → checkpoint`, with atomic JSON checkpointing every generation, a named snapshot every 100 generations, and an append-only JSONL fitness log — all per the preparation document's schema.

**Scope cut made explicit up front:** adaptive step-size *control* (using the embedded `b*` pair to vary `h` mid-run) was not implemented in v1 — `enable_dual_output` is a real, scoreable mutation, but its error estimate isn't wired to change `h`. Fixed `dt=0.1` throughout. This was a deliberate MVP cut, not an oversight, to keep the first working loop small.

## 4. Four real problems found and fixed, in order, each from observed evidence

### 4.1 Global-plateau counter counted the wrong thing

First run: the search discovered a genuine 4-stage partitioned method by generation 50, then hard-stopped at generation 183. Cause: the "give up" counter only incremented on *structural* mutation failures (add/remove stage, switch family), so it could exhaust its patience and halt the whole run even while ordinary coefficient tuning was still improving things elsewhere. **Fix:** the counter now increments/resets on the same "meaningful improvement" signal used everywhere else, regardless of mutation type — it become a generic patience counter, not a structural-only one.

### 4.2 One-shot judging of structural mutations was unfair

Even after the counter fix, growth stalled: a freshly-added stage or a just-switched family starts *untuned* and will almost always lose a single head-to-head comparison against an already-refined smaller candidate — not because the new structure is worse, but because it hasn't had a chance yet. **Fix:** `local_refine()` gives any structural mutation (`add_stage`, `remove_stage`, `switch_family`, `enable_dual_output`) a short (30-iteration) coefficient-only hill-climb burst before it's judged against the current best.

With just these two fixes, the search found a 6-stage plain RK tableau and drove `rms_dE` from `2.9e-5` down to `1.5e-7` — but `rms_dx` stayed frozen at `2.67e-3` the entire time (RK4 achieves `~1.2e-5` with only 4 stages, so this was a poor use of 6 stages).

### 4.3 The fitness function let one term dominate once it was already small

`fitness = -log10(rms_dx) - log10(rms_dE) - ...` — once `rms_dE` was already tiny, squeezing it further kept paying off in log-space out of proportion to how much it actually mattered, while `rms_dx` — stuck, and needing a much less obvious coefficient change to improve — got no attention. **Fix applied:** cap each term's contribution at 10 (corresponding to the `~1e-10` floating-point floor), so neither term can keep dominating once it's already effectively perfect. (Diagnostic note: in the specific run that exposed this, the cap turned out not to be the active constraint — see 4.4 — but the cap is still correct and load-bearing in general, and is now permanent.)

### 4.4 Plain hill-climbing has no way out of a local optimum

The real mechanism keeping `rms_dx` stuck at `2.67e-3` wasn't the fitness cap — it's that once `rms_dE` is already very small, random coefficient perturbations produce large *relative* swings in it almost for free, while nudging `rms_dx` even slightly requires a much more specific, correlated coefficient change that a single random Gaussian rarely finds. A strict greedy hill-climber (accept only if fitness improves) has no mechanism to walk away from that trap. **Fix:** simulated annealing — accept a worse candidate with probability `exp(delta/T)`, `T` cooling geometrically (`T *= 0.999` per generation, floor `1e-3`) from `T0=1.0`. Genuine improvements are still always accepted; this only changes what happens to a worse proposal. `best_ever` (separate from the actively-wandering lineage) is what gets reported, so the run can never lose a good find to its own exploration.

Effect: fitness climbed from a hard ceiling of `8.9` to `10.2+`, with the log now visibly showing the lineage exploring 3–8 stage topologies before resettling — direct evidence the trap was actually escaped, not just moved.

### 4.5 A structural bias blocked the region containing higher-order methods

Even with annealing, the partitioned-family search kept resettling around `rms_dx ≈ 1.5e-3`. Hypothesis, stated *before* testing it: `add_stage` for the partitioned family only ever seeded new kick/drift weights from `uniform(0.1, 0.5)` — always positive. There is a classical result (Suzuki / Sanz-Serna) that any time-symmetric composition method beyond 2nd order must contain at least one negative sub-step coefficient. If true, the search could never seed its way into that region; it would have to stumble into negative territory purely via `perturb_coefficient`'s unbounded Gaussian drift, which is slow.

**Fix:** widened the seeding range to `uniform(-0.5, 0.5)`. **Result, confirming the hypothesis:** the best-ever candidate found afterward genuinely contains negative weights (`kick=-0.063`, `drift=-0.119`), and `rms_dx` improved from `1.55e-3` to `8.68e-4` (~1.8×).

## 5. Final result of this session

Best-ever candidate found (checkpoint generation 2705, `dt=0.1`, `T=18`):

```
family: partitioned (kick/drift splitting)
sequence: D(0.10637) K(0.38165) D(0.76731) K(-0.06348) D(-0.11871) K(0.68184) D(0.24503)
fitness = 9.490
rms_dx  = 8.684e-4
rms_dE  = 1.278e-7
num_f_evals = 1260 (for 180 steps at dt=0.1)
```

## 6. B1 — Mathematical form of the discovered solver

Writing the two primitive operators explicitly, for state `(x, v)` and the SHO right-hand side `f_x(v)=v`, `f_v(x)=-kx`:

- **Kick**, weight `α`: `K_α: v ← v + α h (-k x)`  (updates velocity using the *current* position; a shear parallel to the `v`-axis)
- **Drift**, weight `α`: `D_α: x ← x + α h v`  (updates position using the *current* velocity; a shear parallel to the `x`-axis)

The discovered method — call it provisionally **RSI-7** (a 4-drift/3-kick asymmetric splitting integrator; genuinely unnamed, rename it however you like) — is the composition, applied left to right over one step of size `h`:

```
(x,v) → D(0.10637) → K(0.38165) → D(0.76731) → K(-0.06348) → D(-0.11871) → K(0.68184) → D(0.24503) → (x', v')
```

or, in operator-product notation (right-to-left composition, as is conventional for operator products):

```
Φ_h = D_{0.24503} ∘ K_{0.68184} ∘ D_{-0.11871} ∘ K_{-0.06348} ∘ D_{0.76731} ∘ K_{0.38165} ∘ D_{0.10637}
```

with the consistency constraints `Σ(kick weights) = 1` and `Σ(drift weights) = 1` holding by construction (enforced by `normalize_consistency` every generation).

**Empirically measured order of accuracy** (re-evaluated the saved candidate at `dt ∈ {0.2, 0.1, 0.05, 0.025, 0.0125}` and fit the convergence slope — this was checked, not assumed):

| dt | rms_dx | empirical order vs. previous |
|---|---|---|
| 0.2 | 3.457e-3 | — |
| 0.1 | 8.684e-4 | 1.993 |
| 0.05 | 2.189e-4 | 1.988 |
| 0.025 | 5.553e-5 | 1.979 |
| 0.0125 | 1.428e-5 | 1.960 |

**RSI-7 is a genuine 2nd-order symplectic method** — a materially better-tuned one than the built-in Verlet (compare `rms_dx=8.7e-4` at `dt=0.1` here against Verlet's `abs_dx=5.6e-3` at the same `dt` in the ground-truth table), but order 2, not order 4. One honest caveat surfaced by this same check: `rms_dE` was *not* monotonic across step sizes (`0.2→2.1e-5`, `0.1→1.3e-7`, `0.05→1.3e-6`, ...) — the near-machine-precision energy conservation seen at `dt=0.1` looks partly like a coincidental resonance for that exact `(dt, T)` pair the search was tuned against, not a robust property of the method at other step sizes. This is itself a finding (see §7 and §8).

## 7. B2 — Geometrically, what's keeping RSI-7 from RK4-level accuracy

Both `Kick` and `Drift` are **shear maps** in `(x, v)` phase space: each has Jacobian determinant exactly 1, so *any* composition of them is exactly area-preserving (symplectic) regardless of the coefficients — this is a free, structural guarantee, which is why energy behaves so much better than plain Euler without needing any tuning for it. That's the whole reason the search found the partitioned family rewarding at all.

But area-preservation only buys you 1st-order accuracy for free. Getting to 2nd order (which RSI-7 clearly reaches — the measured slope is right on 2.0) requires the leading error term in the Baker-Campbell-Hausdorff expansion of the composed operators to vanish, which happens automatically for a large, easy-to-find family of coefficient choices (roughly: enough symmetry/balance between kicks and drifts) — that's a big, easy-to-hit basin, which is why *any* reasonable random search finds a 2nd-order method quickly.

Reaching 4th order (what RK4 achieves) requires the *next* commutator term to also vanish — and unlike the 2nd-order condition, that's satisfied only by a thin, specific, lower-dimensional set of coefficient relationships (this is exactly what the classical Forest-Ruth / Yoshida coefficients are: solutions to that specific cancellation, which is why they involve one deliberately negative sub-step). Geometrically: the 2nd-order-good region is a wide, gently-sloped basin; the 4th-order region is a thin ridge or seam running through a corner of it. A local search (Gaussian coefficient perturbation, even with annealing) does a good job finding *a* wide basin, but has a very low chance of an isotropic random step landing exactly on a thin, lower-dimensional seam — it needs *several specific* coefficients to move together, in a *particular relative* pattern, which uncorrelated single-coefficient noise essentially never produces by chance. The 1.8× improvement from allowing negative weights shows the search inching toward that seam, not reaching it.

## 8. B3 — Concrete next tuning steps

In rough order of expected leverage relative to effort:

1. **Add a `symmetrize` structural primitive.** Reflecting a step sequence to be palindromic (`w1...wn → w1...wn...w1`, time-reversal symmetric) is a *known, free* way to guarantee the leading odd-order error term cancels — this is the same category of insight as "add an intermediate evaluation point" from the original transcript: a primitive that encodes a piece of real structure, not an answer. This alone could reliably push generic 2-stage-symmetric compositions to true 2nd order (already true here) and make the 4th-order seam much easier to find by search, since palindromic sequences are exactly where Forest-Ruth/Yoshida-type solutions live.
2. **Add a gradient-informed "polish" mutation**, alongside blind Gaussian `perturb_coefficient`: estimate the fitness gradient by finite differences and take a few steps of gradient ascent. Isotropic noise is bad at finding thin ridges; a gradient step, once *near* the ridge, would follow it far more efficiently than continued random perturbation.
3. **Evaluate against multiple `(dt, initial condition)` pairs**, not just the single fixed `(dt=0.1, T=18, x0=1, v0=0)`. The non-monotonic energy-error result in §6 is a symptom of overfitting to one exact evaluation condition — a candidate that's merely lucky at `dt=0.1` should not score as well as one that's robustly good across a range of step sizes.
4. **Cyclic (reheating) annealing** instead of monotonic cooling, so the search doesn't permanently lose its escape mechanism once `T` hits its floor partway through a long run.
5. **Multiple independent lineages (basin hopping)**, periodically comparing bests — cheap to add given how fast each generation already runs (thousands of generations in seconds), and directly increases the odds of one lineage stumbling onto the thin high-order seam.

## 9. B4 — What would make this *fully* recursive (and stop needing a human to notice problems)

Every fix in §4 followed the same pattern: the loop ran, a human (this session) read the log, diagnosed *why* it stalled, and hand-wrote a specific code change. That diagnostic step is exactly the part that isn't yet self-improving — the solver-discovery loop improves its *coefficients* and *mutation policy*, but a person is still the one improving the *loop itself*. Closing that gap is what "recursive" actually requires:

- **A second, slower-timescale genome, over the loop's own hyperparameters** — `sigma` bounds, cooling rate, `K_local`/`K_global`, the refine-burst iteration count, even the fitness function's weights — mutated and scored the same way solver coefficients are, using "did the inner loop's fitness trajectory improve faster under this configuration" as the fitness signal. This is the direct RSI move: apply the exact same propose→evaluate→keep-if-better rule one level up, instead of a human picking `TEMP0=1.0` and `COOL_RATE=0.999` by hand as happened tonight.
- **Automated stagnation diagnosis**, not just detection. The loop already detects a plateau (`plateau_counters`); a fully autonomous version would, on detecting one, automatically try a registered menu of remediations (reheat, widen a seeding range, add a new mutation primitive, evaluate against a harder test condition) *without asking*, log which one it tried and whether it helped, and keep going — replacing this session's "here's what I found, what should I do" with "here's what I found, here's what I tried, here's what worked."
- **Self-modifying code, with guardrails, closer to a Darwin Gödel Machine.** Everything in §4 was me editing `genome.py`/`evaluate.py`/`loop.py` by hand based on reading the log. The fully-recursive version has an agent do that same read-log → diagnose → patch → sandboxed-test → keep-or-revert cycle unsupervised, bounded by a hard resource ceiling and a pre-agreed, no-exceptions acceptance rule (a patch is kept only if it improves a held-out metric beyond a noise threshold within a fixed compute budget; otherwise it's automatically reverted) — set once, in advance, by a human, so no single self-modification needs a human to bless it in the moment.
- **A pre-agreed acceptance policy is what actually removes the "stop and ask" pattern from tonight**, not any particular algorithm. Tonight, every fork in the road (fitness shaping, escape mechanism, negative-weight seeding) surfaced as a question because there was no standing rule for what counts as "good enough to just try." A single, explicit rule stated once up front — e.g. "any change to loop hyperparameters or code that improves best-ever fitness by more than `X` within `Y` generations is auto-kept; anything else is auto-reverted; no result is ever discarded, only superseded" — turns the same four fixes made tonight into something the loop could have discovered and applied to itself, in the background, without this conversation.

## 10. Files produced this session

```
RSI Toy Example - Preparation.md      preparation document (prior turn)
baseline/FixedStepErrorLogEjsApp/     copy of the existing OSP/EJS SHO app (reference only, untouched original elsewhere)
java/src/*.java                       headless ground-truth comparison tool (self-contained, see java/README.md)
java/lib/osp.jar                      OSP library dependency, bundled
results/sho_solver_comparison.csv     ground-truth error table across all named solvers
python/sho.py                         fixed physics harness (rhs, analytic solution, energy)
python/genome.py                      candidate representation + mutation primitives
python/evaluate.py                    fitness scoring
python/policy.py                      mutation-type success-rate tracking (the self-improving part)
python/loop.py                        the generational RSI loop, with checkpointing
python/checkpoints/, python/logs/     run evidence from tonight's session
docs/rsi-1st-attempt.md               this report
```
