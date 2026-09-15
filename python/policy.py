"""The mutation policy: this is where the 'recursive' part of RSI lives.
select_best() alone would just be hill-climbing. This module tracks a
success rate per mutation type and biases future proposals toward
whatever has actually been paying off -- including switch_family, which
starts out with no reason to be favored and must earn its weight from
observed results, the same as everything else.
"""
import random

from genome import MUTATION_TYPES

EMA_ALPHA = 0.1
EXPLORATION_FLOOR = 0.05
SIGMA_MIN, SIGMA_MAX = 1e-4, 1.0


def init_policy():
    return {
        "success_rate": {m: 0.2 for m in MUTATION_TYPES},
        "sigma": 0.1,
    }


def propose_mutation_type(policy, rng):
    weights = [max(policy["success_rate"][m], EXPLORATION_FLOOR) for m in MUTATION_TYPES]
    return rng.choices(MUTATION_TYPES, weights=weights, k=1)[0]


def update_policy(policy, mutation_type, accepted, rng=None):
    old = policy["success_rate"][mutation_type]
    policy["success_rate"][mutation_type] = (1 - EMA_ALPHA) * old + EMA_ALPHA * (1.0 if accepted else 0.0)

    if mutation_type == "perturb_coefficient":
        rate = policy["success_rate"]["perturb_coefficient"]
        if rate > 0.25:
            policy["sigma"] = min(policy["sigma"] * 1.1, SIGMA_MAX)
        elif rate < 0.15:
            policy["sigma"] = max(policy["sigma"] * 0.9, SIGMA_MIN)
