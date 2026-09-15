---
date: 2026-09-15
tags: [rsi, next-steps, checklist]
---

# RSI Next Steps

Two separate tracks, pulled out of the analysis in `docs/rsi-1st-attempt.md` §8-9 into something that can actually be worked through item by item. **Track 1** pushes the current search toward RK4-level accuracy. **Track 2** is the more important one: it's what would let the loop find and apply fixes like the five in `docs/rsi-1st-attempt.md` §4 *itself*, instead of a human reading the log and hand-editing code, which is what happened in the first attempt.

## Track 1 — Tuning toward higher-order accuracy (tactical)

Ordered by expected leverage relative to effort.

- [ ] **1. Add a `symmetrize` structural primitive.**
  *Where:* `python/genome.py`, alongside `_add_stage_partitioned` / `_perturb_partitioned`.
  *What:* a mutation that reflects the current step sequence into a palindrome (`w1...wn → w1...wn...w1`, time-reversal symmetric).
  *Why:* a known, free result (not something to tune toward) — a time-symmetric composition automatically cancels its leading odd-order error term. This is the same category of move as "add an intermediate evaluation point" from the original transcript: a primitive that encodes real mathematical structure, not an answer. Forest-Ruth/Yoshida-type 4th-order methods are exactly palindromic sequences, so this primitive would put the search's proposals structurally closer to where the 4th-order seam actually lives, rather than relying on isotropic noise to find it by chance.
  *Verify:* rerun `make python-fresh`; check whether `symmetrize` shows a rising success rate in `mutation_policy.success_rate` in the checkpoint, and whether the empirical convergence-order check (see `python/` snippet in `docs/rsi-1st-attempt.md` §6) creeps toward 3-4 instead of sitting at ~2.0.

- [ ] **2. Add a gradient-informed "polish" mutation.**
  *Where:* `python/genome.py` (new mutation type) + `python/evaluate.py` (needs a way to perturb one coefficient and re-evaluate cheaply).
  *What:* estimate `∂fitness/∂coefficient` by finite differences on a few coefficients, take a small step in that direction, instead of (or interleaved with) blind Gaussian `perturb_coefficient`.
  *Why:* isotropic random noise is bad at following a thin ridge in coefficient space (see §7's geometric explanation); a gradient step, once near the ridge, follows it directly.
  *Verify:* compare generations-to-plateau against Track 1 item 1 alone; a real gradient step should reach a given `rms_dx` in fewer generations than random perturbation alone.

- [ ] **3. Evaluate against multiple `(dt, initial condition)` pairs, not just one.**
  *Where:* `python/evaluate.py::evaluate()` — currently hardcodes a single run at `dt=0.1, T=18.0` from `sho.X0, sho.V0`.
  *What:* average (or take the worst of) fitness across e.g. `dt ∈ {0.05, 0.1, 0.2}` and 2-3 different `(x0, v0)` pairs.
  *Why:* `docs/rsi-1st-attempt.md` §6 found the discovered candidate's energy error is *non-monotonic* across step sizes — direct evidence it's overfit to the one condition it was scored on. A candidate that's robustly good across conditions should outscore one that's merely lucky at `dt=0.1`.
  *Verify:* re-run the multi-`dt` convergence check from §6 on a new discovery; the non-monotonic energy-error artifact should shrink or disappear.

- [ ] **4. Cyclic (reheating) annealing.**
  *Where:* `python/loop.py` — `TEMP0`, `COOL_RATE`, `TEMP_MIN`, currently monotonic decay.
  *What:* periodically reset `state["temperature"]` back up (e.g. every 500 generations without a global-plateau reset), instead of letting it decay to `TEMP_MIN` and stay there.
  *Why:* once `T` hits its floor, the escape mechanism from §4.4 is permanently gone for the rest of a long run — a second, later trap can't be escaped the same way the first one was.
  *Verify:* in a long run (10k+ generations), check the temperature curve in `fitness_log.jsonl` shows multiple reheats, and that `best_ever` improves after at least one of them.

- [ ] **5. Multiple independent lineages (basin hopping).**
  *Where:* `python/loop.py::run()` — currently a single `state["best"]` lineage.
  *What:* run N independent lineages (different RNG seeds) for the same generation budget, periodically compare `best_ever` across them, keep the global best.
  *Why:* cheap to add given how fast generations already run (thousands per second); directly multiplies the odds that *some* lineage stumbles onto the thin high-order seam described in §7.
  *Verify:* compare best-of-N-lineages fitness against a single lineage run N× as long — if basin hopping is paying off, N parallel short runs should beat one long run.

## Track 2 — Toward full autonomy (strategic — the actual point of "RSI")

Every fix in `docs/rsi-1st-attempt.md` §4 followed the same pattern: the loop ran, a human read the log, diagnosed why, hand-wrote a fix, and asked before applying anything non-trivial. That's the part that isn't yet self-improving. This track closes that gap, in order:

- [ ] **A. State the acceptance rule explicitly, once, up front.** This is the actual unlock — every other item in this track depends on it existing first. Something concrete enough to implement, e.g.:

  > A candidate change — to a solver's coefficients, to a loop hyperparameter (`sigma` bounds, `COOL_RATE`, `K_local`/`K_global`, fitness weights), or to a mutation primitive's code — is **auto-kept** if it improves `state["best_ever"]["fitness"]` by more than a stated margin within a stated compute budget (e.g. `+0.01` within 500 generations), measured against the current `best_ever`. Otherwise it is **auto-reverted** to the prior `best_ever` and logged as a rejected attempt. No result is ever silently discarded — every attempt, kept or reverted, stays in `fitness_log.jsonl`/`checkpoints/`.

  Once this rule is written down and agreed, items B-D below become things the loop applies to itself under that rule, not things a human blesses one at a time.

- [ ] **B. A second-order genome over the loop's own hyperparameters.** Currently `TEMP0=1.0`, `COOL_RATE=0.999`, `K_LOCAL=30`, `K_GLOBAL=100`, `EPS_COEF`, `EPS_STRUCTURAL`, `REFINE_ITERS`, and the fitness weights (`W_ENERGY`, `LAMBDA_COST`, `FITNESS_CAP`) in `python/loop.py`/`python/evaluate.py` were all picked by hand tonight. Wrap them in their own small genome, mutate them the same way solver coefficients are mutated, and score a configuration by *how fast the inner loop's fitness trajectory improves under it* — then apply rule A to keep or revert configuration changes exactly like solver changes.

- [ ] **C. Automated stagnation remediation, not just detection.** `plateau_counters` already detects a stall. On hitting `K_global`, instead of stopping (or asking), the loop should automatically try a registered menu of remediations in turn — reheat (Track 1.4), widen a seeding range (the same class of fix as §4.5's negative-weight change), add a new mutation primitive from a pre-approved pool, or switch to a harder evaluation condition (Track 1.3) — log which one it tried and whether rule A kept it, and continue. This is what turns "here's what I found, what should I do" into "here's what I found, here's what I tried, here's what worked."

- [ ] **D. Self-modifying code, with guardrails (Darwin Gödel Machine-style).** The furthest step: an agent that reads `fitness_log.jsonl`, diagnoses *why* the loop stalled (as this session did by hand in §4), drafts an actual patch to `genome.py`/`evaluate.py`/`loop.py`, runs it in a sandboxed copy against a held-out evaluation condition, and applies rule A to keep or discard the patch — unsupervised, bounded by a hard wall-clock/generation ceiling independent of the acceptance rule itself (so a runaway loop can't spin forever even if rule A keeps saying yes). This is the piece that would have let tonight's five fixes happen without this conversation.

## Note on scope

Track 1 makes the *existing* search better at the *same* problem (SHO). Track 2 is what makes the whole exercise actually "recursive" rather than "a search loop a person kept improving by hand" — it's worth treating as the higher-priority track even though it's more work, since it's the difference between this being an RSI *demonstration* and an RSI *system*.
