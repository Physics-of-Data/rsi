"""The RSI loop skeleton, following the transcript's design:

    state = load_checkpoint() or init_state()
    while not stop_condition(state):
        candidate = propose_mutation(state)
        result = evaluate(candidate)
        if result improves on state.best: state.best = candidate
        state.mutation_policy = update_policy(state.mutation_policy, result)
        save_checkpoint(state)

Scope note (v1): adaptive step-size *control* (using the embedded b* pair
to vary h during a run) is not implemented -- enable_dual_output is a real,
scoreable mutation, but its b* is only used to compute an error-estimate
side metric here, not to drive step-size changes. Fixed dt=0.1 throughout.
This keeps the first working loop small; adaptive stepping is an additive
follow-up, not a redesign, once Phase A/family-switch behavior is verified.
"""
import argparse
import json
import math
import os
import pickle
import random
import sys
import time

import genome
import evaluate
import policy as policy_mod

DT = 0.1
T_HORIZON = 18.0

EPS_COEF = 1e-6
EPS_STRUCTURAL = 1e-4
K_LOCAL = 30
K_GLOBAL = 100
MAX_GENERATIONS = 5000

# Simulated-annealing escape hatch: a strict greedy hill-climber (accept
# only if fitness improves) gets permanently trapped the moment every
# reachable neighbor is worse, even if that neighbor is only worse because
# the objective is temporarily lopsided (see the fitness-cap discussion).
# Occasionally accepting a worse candidate -- with probability that shrinks
# as the run cools -- lets the lineage walk out of such traps. Genuine
# improvements (delta>0) are still always accepted; this only changes what
# happens to a worse proposal.
TEMP0 = 1.0
COOL_RATE = 0.999
TEMP_MIN = 1e-3

STRUCTURAL_TYPES = {"add_stage", "remove_stage", "switch_family"}
NEEDS_REFINE = STRUCTURAL_TYPES | {"enable_dual_output"}
REFINE_ITERS = 30
REFINE_SIGMA = 0.1

CKPT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "fitness_log.jsonl")
CHECKPOINT_PATH = os.path.join(CKPT_DIR, "checkpoint.json")


def init_state(seed=42):
    rng = random.Random(seed)
    cand = genome.seed_plain()
    metrics = evaluate.evaluate(cand, dt=DT, T=T_HORIZON)
    return {
        "generation": 0,
        "phase": "A",
        "best": cand,
        "best_fitness": metrics["fitness"],
        "best_metrics": metrics,
        "best_ever": {"candidate": genome.clone(cand), "fitness": metrics["fitness"],
                      "metrics": metrics, "generation_found": 0},
        "mutation_policy": policy_mod.init_policy(),
        "plateau_counters": {"local": 0, "global": 0},
        "temperature": TEMP0,
        "rng_state": pickle.dumps(rng.getstate()).hex(),
    }


def load_checkpoint():
    if not os.path.exists(CHECKPOINT_PATH):
        return None
    with open(CHECKPOINT_PATH) as f:
        return json.load(f)


def save_checkpoint(state):
    os.makedirs(CKPT_DIR, exist_ok=True)
    tmp = CHECKPOINT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, CHECKPOINT_PATH)

    if state["generation"] % 100 == 0:
        snap = os.path.join(CKPT_DIR, f"checkpoint_gen{state['generation']:06d}.json")
        with open(snap, "w") as f:
            json.dump(state, f, indent=2)


def log_generation(row):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(row) + "\n")


def local_refine(candidate, rng, iterations=REFINE_ITERS, sigma=REFINE_SIGMA):
    """A freshly structurally-mutated candidate (one more stage, a new
    embedded pair, a just-switched family) starts untuned and would almost
    always lose a one-shot comparison against an already-refined smaller
    candidate -- not because the structure is worse, but because it hasn't
    had a chance yet. Give it a short coefficient-only hill-climb burst
    before it's judged, so structural moves get evaluated at their own
    best, not their birth state."""
    best = candidate
    best_metrics = evaluate.evaluate(best, dt=DT, T=T_HORIZON)
    for _ in range(iterations):
        trial = genome.apply_mutation(best, "perturb_coefficient", sigma, rng)
        if trial is None:
            continue
        m = evaluate.evaluate(trial, dt=DT, T=T_HORIZON)
        if m["fitness"] > best_metrics["fitness"]:
            best, best_metrics = trial, m
    return best, best_metrics


def stop_condition(state, max_generations):
    if state["best_ever"]["metrics"]["rms_dx"] < 1e-10:
        return True, "error below floating-point noise floor"
    if state["plateau_counters"]["global"] >= K_GLOBAL:
        return True, "global plateau reached"
    if state["generation"] >= max_generations:
        return True, "max generation cap reached"
    return False, None


def run(max_generations=MAX_GENERATIONS, resume=True, verbose_every=50):
    state = load_checkpoint() if resume else None
    if state is None:
        state = init_state()
        print("Starting fresh run from seed (1-stage plain tableau).")
    else:
        print(f"Resuming from checkpoint at generation {state['generation']}.")

    rng = random.Random()
    rng.setstate(pickle.loads(bytes.fromhex(state["rng_state"])))

    t_start = time.time()
    while True:
        done, reason = stop_condition(state, max_generations)
        if done:
            print(f"\nStopped at generation {state['generation']}: {reason}")
            break

        mutation_type = None
        candidate = None
        for _ in range(10):  # a few retries if a mutation is inapplicable at current bounds
            mt = policy_mod.propose_mutation_type(state["mutation_policy"], rng)
            cand = genome.apply_mutation(state["best"], mt, state["mutation_policy"]["sigma"], rng)
            if cand is not None:
                mutation_type, candidate = mt, cand
                break

        state["generation"] += 1

        if candidate is None:
            log_generation({"generation": state["generation"], "mutation_type": "none", "accepted": False})
            save_checkpoint(state)
            continue

        if mutation_type in NEEDS_REFINE:
            candidate, metrics = local_refine(candidate, rng)
        else:
            metrics = evaluate.evaluate(candidate, dt=DT, T=T_HORIZON)
        delta = metrics["fitness"] - state["best_fitness"]
        threshold = EPS_STRUCTURAL if mutation_type in STRUCTURAL_TYPES else EPS_COEF
        meaningful = delta > threshold

        if delta >= 0:
            accepted = True
        else:
            accept_prob = math.exp(delta / max(state["temperature"], 1e-9))
            accepted = rng.random() < accept_prob

        if accepted:
            state["best"] = candidate
            state["best_fitness"] = metrics["fitness"]
            state["best_metrics"] = metrics
            if metrics["fitness"] > state["best_ever"]["fitness"]:
                state["best_ever"] = {
                    "candidate": genome.clone(candidate),
                    "fitness": metrics["fitness"],
                    "metrics": metrics,
                    "generation_found": state["generation"],
                }

        state["temperature"] = max(state["temperature"] * COOL_RATE, TEMP_MIN)

        state["phase"] = "B" if (state["best"]["family"] == "plain" and state["best"]["b_star"] is not None) else "A"

        if meaningful:
            state["plateau_counters"]["local"] = 0
            state["plateau_counters"]["global"] = 0
        else:
            state["plateau_counters"]["local"] += 1
            state["plateau_counters"]["global"] += 1

        policy_mod.update_policy(state["mutation_policy"], mutation_type, accepted)
        state["rng_state"] = pickle.dumps(rng.getstate()).hex()

        log_generation({
            "generation": state["generation"],
            "fitness": metrics["fitness"],
            "rms_dx": metrics["rms_dx"],
            "rms_dE": metrics["rms_dE"],
            "num_f_evals": metrics["num_f_evals"],
            "stage_count": metrics["stage_count"],
            "family": candidate["family"],
            "mutation_type": mutation_type,
            "accepted": accepted,
            "sa_accepted_worse": accepted and delta < 0,
            "meaningful": meaningful,
            "phase": state["phase"],
            "temperature": state["temperature"],
            "best_ever_fitness": state["best_ever"]["fitness"],
        })
        save_checkpoint(state)

        if state["generation"] % verbose_every == 0:
            b = state["best"]
            be = state["best_ever"]
            print(f"gen {state['generation']:5d}  cur_fit={state['best_fitness']:7.3f}  "
                  f"best_ever={be['fitness']:7.3f} (gen {be['generation_found']:5d})  "
                  f"family={b['family']:11s} stages={evaluate._stage_count(b):2d}  "
                  f"rms_dx={state['best_metrics']['rms_dx']:.3e}  "
                  f"rms_dE={state['best_metrics']['rms_dE']:.3e}  "
                  f"T={state['temperature']:.4f} sigma={state['mutation_policy']['sigma']:.4f}")

    elapsed = time.time() - t_start
    print(f"Elapsed: {elapsed:.1f}s, {state['generation']} generations")
    print("Best-ever candidate (generation {}):".format(state["best_ever"]["generation_found"]))
    print(json.dumps(state["best_ever"]["candidate"], indent=2))
    print("metrics:", json.dumps(state["best_ever"]["metrics"], indent=2))
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=MAX_GENERATIONS)
    parser.add_argument("--fresh", action="store_true", help="ignore any existing checkpoint")
    args = parser.parse_args()
    run(max_generations=args.generations, resume=not args.fresh)
