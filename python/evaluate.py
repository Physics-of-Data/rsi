"""Runs a candidate genome on the SHO problem and scores it. Mirrors the
Java baseline's own error-table methodology (rms/final position error,
energy error, function-evaluation count) so fitness numbers are directly
comparable to results/sho_solver_comparison.csv.
"""
import math

import sho

W_ENERGY = 1.0
LAMBDA_COST = 0.15
FLOOR = 1e-15
FITNESS_CAP = 10.0  # caps each error term's contribution once it reaches the
                     # ~1e-10 floating-point noise floor, so a term that's
                     # already effectively perfect can't keep dominating the
                     # objective while another term is still large.


def step_plain(cand, x, v, h):
    A, b, c = cand["A"], cand["b"], cand["c"]
    s = len(b)
    kx = [0.0] * s
    kv = [0.0] * s
    evals = 0
    for i in range(s):
        xi = x + h * sum(A[i][j] * kx[j] for j in range(i))
        vi = v + h * sum(A[i][j] * kv[j] for j in range(i))
        dx, dv = sho.rhs(xi, vi)
        kx[i], kv[i] = dx, dv
        evals += 1
    x_new = x + h * sum(b[i] * kx[i] for i in range(s))
    v_new = v + h * sum(b[i] * kv[i] for i in range(s))
    err_est = 0.0
    if cand["b_star"] is not None:
        bs = cand["b_star"]
        x_star = x + h * sum(bs[i] * kx[i] for i in range(s))
        v_star = v + h * sum(bs[i] * kv[i] for i in range(s))
        err_est = math.hypot(x_new - x_star, v_new - v_star)
    return x_new, v_new, evals, err_est


def step_partitioned(cand, x, v, h):
    evals = 0
    for st in cand["steps"]:
        if st["type"] == "kick":
            _, dv = sho.rhs(x, v)
            v = v + h * st["w"] * dv
        else:
            dx, _ = sho.rhs(x, v)
            x = x + h * st["w"] * dx
        evals += 1
    return x, v, evals, 0.0


def step(cand, x, v, h):
    if cand["family"] == "plain":
        return step_plain(cand, x, v, h)
    return step_partitioned(cand, x, v, h)


def evaluate(cand, dt=0.1, T=18.0):
    """Returns a dict of metrics, including 'fitness'. A candidate that
    diverges (NaN/overflow) gets the worst possible fitness rather than
    crashing the loop -- the search must survive its own bad proposals."""
    x, v, t = sho.X0, sho.V0, 0.0
    num_steps = round(T / dt)
    num_evals = 0
    sum_sq_dx = 0.0
    sum_sq_dE = 0.0
    sum_err_est = 0.0

    try:
        for _ in range(num_steps):
            x, v, evals, err_est = step(cand, x, v, dt)
            t += dt
            num_evals += evals
            sum_err_est += err_est
            if not (math.isfinite(x) and math.isfinite(v)):
                raise OverflowError
            dx = x - sho.analytic_x(t)
            dE = sho.energy(x, v) - sho.E_ANALYTIC
            sum_sq_dx += dx * dx
            sum_sq_dE += dE * dE
    except (OverflowError, ValueError):
        return {
            "fitness": -1e9,
            "rms_dx": float("inf"),
            "rms_dE": float("inf"),
            "num_f_evals": num_evals,
            "stage_count": _stage_count(cand),
            "diverged": True,
        }

    rms_dx = math.sqrt(sum_sq_dx / num_steps)
    rms_dE = math.sqrt(sum_sq_dE / num_steps)
    pos_term = min(-math.log10(rms_dx + FLOOR), FITNESS_CAP)
    energy_term = min(-math.log10(rms_dE + FLOOR), FITNESS_CAP)
    fitness = (
        pos_term
        + W_ENERGY * energy_term
        - LAMBDA_COST * math.log10(max(num_evals, 1))
    )
    return {
        "fitness": fitness,
        "rms_dx": rms_dx,
        "rms_dE": rms_dE,
        "num_f_evals": num_evals,
        "stage_count": _stage_count(cand),
        "diverged": False,
    }


def _stage_count(cand):
    if cand["family"] == "plain":
        return len(cand["b"])
    return len(cand["steps"])
