# RSI Toy Example — Preparation Document: Discovering ODE Solvers from Calculus Primitives

## Context

The source transcript (`What is Recursive Self Improvement.md`) sketches an RSI toy example: instead of handing a search process a menu of named integrators, give it the *primitive operations* integrators are built from and let a fitness-driven loop discover integrator-shaped solutions on its own — with the self-improving part being that the *mutation policy itself* gets rewritten based on what has been paying off, not just the integrator coefficients.

The user asked for four preparation items before any code is written. This document is that preparation, refined through several rounds of discussion:

- **Primary test problem: Simple Harmonic Oscillator (SHO).** Confirmed by an existing working baseline the user already has (see below) — resolved after an initial heat-equation pick turned out to be incompatible with the target solver list (a dissipative PDE has no symplectic structure for Verlet/Euler-Cromer to exploit).
- **Discovery targets (never given to the search — used only to grade what it finds):** Euler, Euler-Richardson, Euler-Cromer, Verlet, RK4.
- **Existing baseline app:** `/storage/develop/opensourcephysics/06-cheerpJ/FixedStepErrorLogEjsApp` (OSP/EJS, Java) — already implements SHO with exactly the right validation methodology: position error vs. time, energy error vs. time, and an error table (`x_numeric`, `x_analytic`, `E_numeric`, `E_analytic`, `|Δx|`, `|ΔE|`, relative errors), plus a solver dropdown (Euler, EulerRichardson, Verlet, Ralston2, Heun3, RK4, Fehlberg8, Butcher5) backed by OSP's `org.opensourcephysics.numerics` library. **Do not modify this app** — the user said to copy it into the RSI project if a working reference is needed. Its named solvers are exactly the "answer key" this RSI search should never see, and its error-metric methodology is what the Python prototype should mirror so a later Java port slots back into this same app/framework.
- **Build scope:** full scope — adaptive step-size discovery *and* a structural-preservation constraint, from generation 1.
- **Tooling path:** Python (numpy/scipy/matplotlib) for the proof of concept; port to Java/OSP (into the baseline app above) only once the Python version is validated.

**Key technical correction made during preparation:** Verlet and Euler-Cromer are not reachable from a plain Runge–Kutta tableau — they require a *partitioned* update on a separable system (`x' = v`, `v' = f(x)`), where one sub-state is updated using the other's *already-updated* value within the same step. SHO is exactly this kind of separable, conservative (Hamiltonian) system, so — unlike the earlier heat-equation attempt — the genome below can genuinely reach the whole target list without being told any of their forms.

---

## 1. Primitives — what tools the search is allowed to build solvers from

**Given tools (fixed harness, not searched):**

- `rhs(t, x, v)` — the derivative oracle: `f_x(v) = v`, `f_v(x) = -k·x` (`k = ω²`, matching the baseline app's own `k` parameter). Exposed to the genome as two independently-callable pieces *because* SHO is separable — this is what makes the partitioned family possible without hinting at Verlet's structure.
- `analytic(t)` — closed-form `x(t) = A cos(ωt+φ)`, `v(t) = -Aω sin(ωt+φ)`, `E = ½v² + ½k x²` — used only for scoring, mirroring the baseline app's error-table columns exactly (`x_numeric` vs `x_analytic`, `E_numeric` vs `E_analytic`, `|Δx|`, `|ΔE|`, relative errors).

**The genome (what gets mutated) — two families, chosen by the search itself, never handed a name:**

- **Plain family:** a variable-size Runge–Kutta tableau on the combined state `y=[x,v]`: matrix `A` (strictly lower-triangular, explicit), node vector `c`, output-weight vector `b`, and an optional second output vector `b*` (embedded lower-order estimate, enabling adaptive step size). Reachable targets: Euler (1 stage), Euler-Richardson/Heun (2 stages), RK4 (4 stages), and — with more stages — Ralston2/Heun3/Fehlberg8/Butcher5-shaped methods, all present in the baseline app's dropdown as recognition checkpoints.
- **Partitioned family:** two small staggered update rules, one for `x` one for `v`, where a stage may reference the *other* sub-state's value from earlier in the *same* step rather than only the previous step's value. Reachable targets: Euler-Cromer (1-stage symplectic Euler: update `v` from old `x`, then update `x` from the *new* `v`), Verlet/leapfrog (kick-drift-kick, half-step velocity updates).

**Mutation primitives (operations available to the search):**

1. `add_stage(c_i, a_i,:)` — append a stage (node + weights on prior-stage derivatives).
2. `remove_stage` — delete a stage, shrink the tableau.
3. `perturb_coefficient` — Gaussian nudge on one entry of `A`, `b`, `b*`, or `c`.
4. `enable_dual_output` — turn on the embedded `b*` vector for adaptive step-size control (`h_new = h·safety·(rtol/err_est)^{1/(p+1)}`, `rtol` fixed at `1e-6`, not evolved).
5. `switch_family` — the structural move that lets the search try the partitioned family instead of plain RK (or vice versa). This is the single primitive that makes Euler-Cromer/Verlet reachable, and — critically — it is just one more entry in the same mutation-type success-rate tracking as everything else (§4), so the mutation *policy* is what learns to favor it once SHO's energy-conservation term starts rewarding it. Nothing hints that this move leads anywhere good.
6. `normalize_consistency` (hard rule, not a scored choice) — project so `Σb_i = 1` (and `Σb*_i=1` once enabled) before a candidate is even evaluated; without it a method doesn't converge to the right answer at all.

**Structural fitness term (real symplectic-ness, since SHO is conservative — no substitute needed here):** long-run energy drift, `|E_numeric(T) − E_analytic|`, exactly the baseline app's own "Energy Error vs. Time" plot. This rewards phase-space-volume-preserving (symplectic) candidates without ever naming "symplectic" or "Verlet" to the search.

**Explicitly excluded from this genome:** implicit stages (`a_ii≠0`, needing a linear/Newton solve). Not needed for SHO's target list; named here only as a future extension boundary.

---

## 2. Candidate physics problems (five, as originally requested) — selected: SHO

| # | Problem | Analytical solution | Status |
|---|---|---|---|
| 1 | **Simple harmonic oscillator** | `x''+ω²x=0` ⇒ `x(t)=A cos(ωt+φ)` | **SELECTED.** Confirmed by existing working baseline app (see Context). Separable + conservative → reaches the entire target list (Euler, Euler-Richardson, Euler-Cromer, Verlet, RK4) without being told any of their forms. |
| 2 | Kepler two-body orbit | Closed form via eccentric anomaly; conserves energy + angular momentum | Alternate / Phase-2 stress test — same partitioned-genome idea, richer vector state, costlier per evaluation. |
| 3 | Damped harmonic oscillator | `x''+2ζωx'+ω²x=0`, full closed form for under/critical/overdamped | Alternate — adds a non-conservative term; useful for checking the search doesn't force symplectic structure where it no longer helps. |
| 4 | Radioactive/exponential decay | `y'=-ky` ⇒ `y0 e^{-kt}` | Alternate — trivial scalar smoke test, too simple to reward multi-stage or partitioned methods. |
| 5 | 1D heat equation | Single-mode separation of variables, `u(x,t)=sin(πx/L)e^{-α(π/L)²t}` | **Ruled out as primary.** Dissipative/parabolic — no symplectic structure, so Euler-Cromer/Verlet can never emerge from it. Documented here only so the reasoning for excluding it isn't lost. |

---

## 3. Epsilon / plateau conditions — when each solving mechanism hands off to the next

**Fitness function** (mirrors the baseline app's own error columns):

```
fitness = -log10(|Δx|_rms over T) - w_E·log10(|ΔE|(T)) - λ_cost·log10(num_f_evals)
```

- `|Δx|_rms`: RMS position error vs. `analytic(t)` over several sample times up to horizon `T`.
- `|ΔE|(T)`: energy drift at final time (rewards symplectic/partitioned structure — see §1).
- `num_f_evals`: total derivative-oracle calls (fixed-step: `stages × steps`; adaptive: accumulated over accepted + rejected steps) — keeps the search from just adding stages forever.

**Epsilon definitions:**

| Name | Role | Suggested value |
|---|---|---|
| `ε_coef` | Minimum fitness gain for a `perturb_coefficient` move to be accepted (below this = numerical noise) | `1e-6` relative fitness gain |
| `K_local` | Consecutive generations under `ε_coef` before the current regime is declared plateaued | 30 generations |
| `ε_structural` | Minimum fitness gain for `add_stage`/`remove_stage`/`switch_family` to be worth its added cost | `1e-4` relative fitness gain |
| `K_global` | Consecutive plateaued structural attempts before the loop stops entirely | 100 generations |
| Adaptive-controller `rtol` | Fixed tool parameter, not evolved | `1e-6` |

**Regime hand-off:**

- **Phase A — fixed-step, plain family, single output.** `add_stage`/`remove_stage`/`perturb_coefficient` only; `switch_family` and `enable_dual_output` available but initially untried/low-success in the policy. Expect Euler → Euler-Richardson-shaped → RK4-shaped emergence here, purely from the accuracy term.
- **Phase B — adaptive embedded pair.** Triggered when Phase A plateaus (`K_local` under `ε_coef`, and `add_stage`/`remove_stage` both fail `ε_structural`): `enable_dual_output` gets tried more (policy reweights toward it), discovering a Fehlberg/RK45-shaped embedded pair.
- **Family exploration (parallel, not strictly sequenced):** `switch_family` is available throughout; the energy-drift fitness term should make partitioned candidates start winning once plain-family accuracy plateaus — this is where Euler-Cromer and Verlet are expected to emerge, and it's the clearest test of whether the *mutation policy itself* learned to reweight toward a previously-untried structural move, which is the actual RSI claim (not just hill-climbing coefficients).
- **Phase C — implicit/stiff-aware (future, out of scope).** Named only so the plateau logic has a documented next step if the problem set later includes something stiff (e.g. candidate #5).

**Stop condition:** error below floating-point noise floor (`~1e-10`) **or** `K_global` reached **or** a wall-clock/generation cap — whichever first.

---

## 4. Checkpoint / state-evolution schema

Written every generation, atomically (temp file + rename).

```
state = {
  "generation": int,
  "phase": "A" | "B",
  "problem": {"id": "sho", "k": float, "x0": float, "v0": float},
  "best_tableau": {"family": "plain" | "partitioned",
                    "A": [[...]], "b": [...], "b_star": [...] | null, "c": [...]},
  "best_fitness": float,
  "best_ever": { ...same shape..., "fitness": float, "generation_found": int },  # elitism guard
  "fitness_history": [ {"generation": int, "fitness": float, "dx_rms": float, "dE": float,
                         "num_f_evals": int, "stage_count": int, "family": str,
                         "mutation_type": str, "accepted": bool} , ... ],
  "mutation_policy": {
     "success_rate": {"perturb_coefficient": float, "add_stage": float, "remove_stage": float,
                       "enable_dual_output": float, "switch_family": float},
     "sigma": float   # current coefficient-perturbation step size, itself adapted
  },
  "plateau_counters": {"local": int, "global": int},
  "rng_state": "..."
}
```

- **Per-generation log** (append-only JSONL): mirrors `fitness_history` — lets you plot the accuracy-order ladder climb and diff discovered coefficients against the baseline app's known tableaux (Euler/EulerRichardson/Verlet/RK4/...).
- **Named snapshots** every 100 generations, never overwritten, for post-hoc inspection of the family switch (plain → partitioned) if/when it happens.
- `best_ever` tracked separately from the current candidate so a bad `switch_family` or `remove_stage` attempt can never lose the best solution found so far.

---

## Next steps (separate task, not part of this preparation)

1. Copy the baseline app (`FixedStepErrorLogEjsApp`) into the RSI project as a reference (original left untouched).
2. Build the Python prototype: `loop.py` implementing `propose_mutations → evaluate → select_best → update_policy → save_checkpoint`, wired to the SHO harness (§1), epsilon/phase logic (§3), and state schema (§4).
3. Validate against the baseline's own metrics (position error, energy error) so results are directly comparable to the OSP dropdown's named solvers.
4. Port to Java/OSP, slotting back into the baseline app's framework, only once Python runs show at least one genuine Phase A→B hand-off and (ideally) a `switch_family` win.
