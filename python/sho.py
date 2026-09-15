"""Simple harmonic oscillator: the fixed physics harness.

This is the only thing a candidate solver is allowed to know about the
problem: rhs() as a black-box derivative oracle. Nothing here is searched.
"""
import math

K = 1.0
X0 = 1.0
V0 = 0.0
OMEGA = math.sqrt(K)
A = math.sqrt(X0 * X0 + (V0 / OMEGA) ** 2)
PHI = math.atan2(-V0 / OMEGA, X0)
E_ANALYTIC = 0.5 * V0 * V0 + 0.5 * K * X0 * X0


def rhs(x, v):
    """f_x(v) = v, f_v(x) = -k x -- exposed separably so a partitioned
    (Verlet/Euler-Cromer-shaped) genome can call each half independently."""
    return v, -K * x


def analytic_x(t):
    return A * math.cos(OMEGA * t + PHI)


def analytic_v(t):
    return -A * OMEGA * math.sin(OMEGA * t + PHI)


def energy(x, v):
    return 0.5 * v * v + 0.5 * K * x * x
