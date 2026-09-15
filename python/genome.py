"""The genome: candidate solver representations and the primitives that
mutate them. Nothing in this file ever names a known integrator -- the
mutation operators only add/remove/perturb generic structure. Any
resemblance to Euler, RK4, Verlet, etc. in the discovered output is a
result of the search, not something encoded here.
"""
import copy
import random

MIN_PLAIN_STAGES = 1
MAX_PLAIN_STAGES = 8
MIN_PARTITIONED_STEPS = 2
MAX_PARTITIONED_STEPS = 8


def seed_plain():
    """The minimal member of the plain-RK grammar: 1 stage, weight 1.
    This happens to be forward Euler, but it is reached as 'the simplest
    thing expressible', never handed in as a named method."""
    return {
        "family": "plain",
        "A": [[0.0]],
        "b": [1.0],
        "b_star": None,
        "c": [0.0],
    }


def seed_partitioned():
    """The minimal member of the kick/drift grammar: one kick, one drift.
    This happens to be Euler-Cromer, reached the same way seed_plain()
    happens to be Euler -- smallest expressible structure, not a hint."""
    return {
        "family": "partitioned",
        "steps": [
            {"type": "kick", "w": 1.0},
            {"type": "drift", "w": 1.0},
        ],
    }


def clone(candidate):
    return copy.deepcopy(candidate)


# ---------------------------------------------------------------- plain RK

def _add_stage_plain(cand, rng):
    s = len(cand["b"])
    if s >= MAX_PLAIN_STAGES:
        return False
    for row in cand["A"]:
        row.append(0.0)
    new_row = [rng.gauss(0, 0.3) for _ in range(s)] + [0.0]
    cand["A"].append(new_row)
    cand["b"].append(rng.gauss(0, 0.3))
    cand["c"].append(rng.uniform(0, 1))
    if cand["b_star"] is not None:
        cand["b_star"].append(rng.gauss(0, 0.3))
    return True


def _remove_stage_plain(cand, rng):
    s = len(cand["b"])
    if s <= MIN_PLAIN_STAGES:
        return False
    i = rng.randrange(s)
    del cand["b"][i]
    del cand["c"][i]
    del cand["A"][i]
    for row in cand["A"]:
        if i < len(row):
            del row[i]
    if cand["b_star"] is not None:
        del cand["b_star"][i]
    return True


def _perturb_plain(cand, sigma, rng):
    s = len(cand["b"])
    pool = [("b", i) for i in range(s)] + [("c", i) for i in range(s)]
    for i in range(s):
        for j in range(i):
            pool.append(("A", i, j))
    if cand["b_star"] is not None:
        pool += [("b_star", i) for i in range(s)]
    if not pool:
        return False
    choice = rng.choice(pool)
    if choice[0] == "A":
        _, i, j = choice
        cand["A"][i][j] += rng.gauss(0, sigma)
    else:
        name, i = choice
        cand[name][i] += rng.gauss(0, sigma)
    return True


def _enable_dual_output(cand, rng):
    if cand["family"] != "plain" or cand["b_star"] is not None:
        return False
    s = len(cand["b"])
    cand["b_star"] = [b + rng.gauss(0, 0.3) for b in cand["b"]]
    return True


# ---------------------------------------------------------- partitioned

def _add_stage_partitioned(cand, rng):
    steps = cand["steps"]
    if len(steps) >= MAX_PARTITIONED_STEPS:
        return False
    kind = rng.choice(["kick", "drift"])
    pos = rng.randrange(len(steps) + 1)
    # Range includes negative weights on purpose: any time-symmetric
    # composition method beyond 2nd order provably needs at least one
    # negative sub-step coefficient (Suzuki/Sanz-Serna). Seeding only
    # positive weights would structurally block the search from ever
    # reaching that region.
    steps.insert(pos, {"type": kind, "w": rng.uniform(-0.5, 0.5)})
    return True


def _remove_stage_partitioned(cand, rng):
    steps = cand["steps"]
    if len(steps) <= MIN_PARTITIONED_STEPS:
        return False
    n_kicks = sum(1 for st in steps if st["type"] == "kick")
    n_drifts = len(steps) - n_kicks
    candidates = [i for i, st in enumerate(steps)
                  if not (st["type"] == "kick" and n_kicks <= 1)
                  and not (st["type"] == "drift" and n_drifts <= 1)]
    if not candidates:
        return False
    i = rng.choice(candidates)
    del steps[i]
    return True


def _perturb_partitioned(cand, sigma, rng):
    steps = cand["steps"]
    if not steps:
        return False
    i = rng.randrange(len(steps))
    steps[i]["w"] += rng.gauss(0, sigma)
    return True


def _switch_family(cand, rng):
    if cand["family"] == "plain":
        return seed_partitioned()
    return seed_plain()


# --------------------------------------------------------------- dispatch

MUTATION_TYPES = [
    "perturb_coefficient",
    "add_stage",
    "remove_stage",
    "enable_dual_output",
    "switch_family",
]


def apply_mutation(candidate, mutation_type, sigma, rng):
    """Returns a new candidate (or the same one mutated in place, cloned
    by the caller beforehand) after applying one mutation primitive.
    Returns None if the mutation was not applicable (e.g. already at
    stage-count bounds) so the caller can retry another type."""
    cand = clone(candidate)

    if mutation_type == "switch_family":
        return _switch_family(cand, rng)

    if cand["family"] == "plain":
        ok = {
            "perturb_coefficient": lambda: _perturb_plain(cand, sigma, rng),
            "add_stage": lambda: _add_stage_plain(cand, rng),
            "remove_stage": lambda: _remove_stage_plain(cand, rng),
            "enable_dual_output": lambda: _enable_dual_output(cand, rng),
        }.get(mutation_type, lambda: False)()
    else:
        ok = {
            "perturb_coefficient": lambda: _perturb_partitioned(cand, sigma, rng),
            "add_stage": lambda: _add_stage_partitioned(cand, rng),
            "remove_stage": lambda: _remove_stage_partitioned(cand, rng),
            "enable_dual_output": lambda: False,  # not meaningful for this family
        }.get(mutation_type, lambda: False)()

    if not ok:
        return None
    normalize_consistency(cand)
    return cand


def normalize_consistency(cand):
    """Hard rule, not a scored choice: project so the method is at least
    consistent (converges to the right answer as h->0) before it is ever
    evaluated. Without this, Sum(b)=1 could drift away from 1 under
    perturb_coefficient and the candidate would be void, not just bad."""
    if cand["family"] == "plain":
        s = sum(cand["b"])
        if abs(s) < 1e-8:
            n = len(cand["b"])
            cand["b"] = [1.0 / n] * n
        else:
            cand["b"] = [b / s for b in cand["b"]]
        if cand["b_star"] is not None:
            s2 = sum(cand["b_star"])
            if abs(s2) < 1e-8:
                n = len(cand["b_star"])
                cand["b_star"] = [1.0 / n] * n
            else:
                cand["b_star"] = [b / s2 for b in cand["b_star"]]
    else:
        kicks = [st for st in cand["steps"] if st["type"] == "kick"]
        drifts = [st for st in cand["steps"] if st["type"] == "drift"]
        for group in (kicks, drifts):
            s = sum(st["w"] for st in group)
            if abs(s) < 1e-8:
                for st in group:
                    st["w"] = 1.0 / len(group)
            else:
                for st in group:
                    st["w"] /= s
