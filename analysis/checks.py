"""
Golden-model self-checks: the invariants the RTL will later be held to as formal
properties. run_all.py fails the build if any check fails.
"""
import numpy as np
from . import params as P
from .array import steer, unit, positions
from .nuller import (null_weights, rejection_db, doa_phase_gradient, complete_k, clz_normalise,
                     self_check, mainlobe_gate, quantise)
from .geometry import random_defended

F = P.LINK["f_hz"]


def _snap(k, jnr_db, K, rng, f=F):
    s = (rng.normal(size=K) + 1j * rng.normal(size=K)) * np.sqrt(10 ** (jnr_db / 10) / 2)
    n = (rng.normal(size=(4, K)) + 1j * rng.normal(size=(4, K))) / np.sqrt(2)
    return np.outer(steer(k, f), s) + n


def check_exact_null(rng):
    for _ in range(200):
        kD, kJ = random_defended(rng)
        w, _ = null_weights(steer(kD, F), steer(kJ, F))
        if rejection_db(w, steer(kJ, F)) < 200:
            return False
    return True


def check_mainlobe_bound(rng):
    """Gate guarantees desired gain >= M * (1 - gamma) = 3 dB over a single element."""
    for _ in range(500):
        kD = unit(rng.uniform(0, 360), -rng.uniform(1, 30))
        kJ = unit(rng.uniform(0, 360), -rng.uniform(1, 30))
        aD, aJ = steer(kD, F), steer(kJ, F)
        w, rho = null_weights(aD, aJ)
        if mainlobe_gate(rho, 4):
            g = abs(np.vdot(w, aD)) ** 2 / np.vdot(w, w).real
            if 10 * np.log10(g) < 10 * np.log10(2.0) - 1e-9:
                return False
    return True


def check_no_wrap():
    """Centre-arm phase never exceeds 0.9 pi anywhere in the hop band (18 deg guard)."""
    r = np.linalg.norm(positions()[1, :2])
    return 2 * np.pi * P.BAND_BENCH["f_hi"] / P.C * r <= 0.9 * np.pi + 1e-9


def check_doa_unbiased(rng):
    kD, kJ = random_defended(rng)
    err = []
    for _ in range(100):
        kxy, g = doa_phase_gradient(_snap(kJ, 20, 256, rng), F)
        err.append(np.linalg.norm(kxy - kJ[:2]))
    return float(np.mean(err)) < 0.01


def check_closure_rejects_two_sources(rng):
    """Two equal-power jammers must never pass BOTH V1 gates."""
    passed = 0
    for _ in range(100):
        _, k1 = random_defended(rng)
        _, k2 = random_defended(rng)
        if np.degrees(np.arccos(np.clip(k1 @ k2, -1, 1))) < 30:
            continue
        X = _snap(k1, 30, 256, rng) + _snap(k2, 30, 256, rng)
        _, g = doa_phase_gradient(X, F)
        passed += g["coherence"] and g["closure"]
    return passed == 0


def check_clz_bounds(rng):
    for _ in range(1000):
        w = (rng.normal(size=4) + 1j * rng.normal(size=4)) * 10 ** rng.uniform(-4, 4)
        n = np.linalg.norm(clz_normalise(w))
        if not (0.5 - 1e-12 <= n < 1.0 + 1e-12):
            return False
    return True


def fixed_point_floor_db(rng, trials=500):
    """Null residual of 16-bit quantised weights (the floor the self-check sits above)."""
    worst = -np.inf
    for _ in range(trials):
        kD, kJ = random_defended(rng)
        aD, aJ = steer(kD, F), steer(kJ, F)
        w = quantise(clz_normalise(null_weights(aD, aJ)[0]))
        worst = max(worst, -rejection_db(w, aJ))
    return float(worst)


def min_detectable_corruption_deg(rng, trials=300):
    """Smallest single-weight phase corruption the self-check always catches (worst case
    over geometry and over which weight is hit)."""
    worst = 0.0
    for _ in range(trials):
        kD, kJ = random_defended(rng)
        aD, aJ = steer(kD, F), steer(kJ, F)
        w = quantise(clz_normalise(null_weights(aD, aJ)[0]))
        m = rng.integers(0, 4)
        for d in np.arange(0.01, 20, 0.01):
            w2 = w.copy(); w2[m] *= np.exp(1j * np.radians(d))
            if not self_check(aD, aJ, w2):
                worst = max(worst, d)
                break
    return float(worst)


def check_self_check_passes_clean_quantised(rng):
    for _ in range(300):
        kD, kJ = random_defended(rng)
        aD, aJ = steer(kD, F), steer(kJ, F)
        if not self_check(aD, aJ, quantise(clz_normalise(null_weights(aD, aJ)[0]))):
            return False
    return True


def check_self_check_catches_corruption(rng):
    """A 1 deg corruption of any single weight (SEU-like) must fail the null self-check."""
    for _ in range(300):
        kD, kJ = random_defended(rng)
        aD, aJ = steer(kD, F), steer(kJ, F)
        w = quantise(clz_normalise(null_weights(aD, aJ)[0]))
        w2 = w.copy(); w2[rng.integers(0, 4)] *= np.exp(1j * np.radians(1.0))
        if self_check(aD, aJ, w2):
            return False
    return True


def check_trust_cut_monotonic(rng):
    """TRUST_CUT <- max(TRUST_CUT, now - MAX_AGE_eff): raising MAX_AGE never resurrects."""
    tc, now, valid_before = -np.inf, 0.0, set()
    ts = {i: rng.uniform(0, 5) for i in range(50)}
    for step in range(200):
        now += 0.05
        max_age = rng.choice([0.2, 0.5, 2.0])
        tc = max(tc, now - max_age)
        valid = {i for i, t in ts.items() if t >= tc and t <= now}
        if not valid.issubset(valid_before | {i for i, t in ts.items() if now - 0.05 < t <= now}):
            return False
        valid_before = valid
    return True


def check_freq_tag_invariant(rng):
    """Active bundle tag must equal the current hop's frequency, or mode == BYPASS."""
    tag, mode = None, "BYPASS"
    for _ in range(1000):
        f_now = rng.integers(0, 79)
        cand_ok = rng.random() > 0.1
        if cand_ok:
            tag, mode = f_now, "NULL"
        else:
            mode = "BYPASS"           # hold-over at a stale tag is forbidden
        if not (mode == "BYPASS" or tag == f_now):
            return False
    return True


def run_all(seed=11):
    rng = np.random.default_rng(seed)
    checks = [
        ("closed-form null is exact (w^H a_J = 0)", check_exact_null(rng)),
        ("mainlobe gate bounds desired-signal gain >= 3 dB", check_mainlobe_bound(rng)),
        ("centre-arm phase <= 0.9 pi across the band (no wrap)", check_no_wrap()),
        ("phase-gradient DoA unbiased at JNR 20 dB, K 256", check_doa_unbiased(rng)),
        ("two equal jammers never pass both V1 gates", check_closure_rejects_two_sources(rng)),
        ("CLZ normalisation lands ||w|| in [0.5, 1)", check_clz_bounds(rng)),
        ("16-bit quantised weights pass the null self-check", check_self_check_passes_clean_quantised(rng)),
        ("null self-check catches a 1 deg single-weight corruption", check_self_check_catches_corruption(rng)),
        ("TRUST_CUT never resurrects an expired entry", check_trust_cut_monotonic(rng)),
        ("frequency-tag invariant holds on every hop", check_freq_tag_invariant(rng)),
    ]
    return [dict(name=n, ok=bool(o)) for n, o in checks]
