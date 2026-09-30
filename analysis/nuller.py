"""
Block 1 / Block 2 golden model: 2-D phase-gradient DoA, gates, closed-form nuller,
CLZ normalisation.

Y array: element 0 is the centre, 1-3 are the arms. Only the three centre-to-arm
baselines (length r = 0.45 lambda_top) are used, so no pair phase can wrap
(max 0.9 pi). The arm-to-arm baselines (r*sqrt(3)) would wrap and are never used
for phase-gradient DoA.
"""
import numpy as np
from .params import C, spacing_m
from .array import positions

PAIRS = [(1, 0), (2, 0), (3, 0)]


# ------------------------------------------------------------------ B1 ------
def correlators(X):
    """X: (4, K) snapshots. Returns pair correlators r_i0 = sum x_i x_0^* and powers."""
    P = np.sum(np.abs(X) ** 2, axis=1).real
    r = {p: np.vdot(X[p[1]], X[p[0]]) for p in PAIRS}
    return r, P


def ls_matrix(r=None):
    """Constant 2x3 least-squares matrix: k_xy = LUT[1/f] * G @ phi.
    For a symmetric Y, B^T B = (3 r^2 / 2) I, so G = (2 / (3 r^2)) B^T -- precomputed."""
    B = (positions(r)[1:, :2])
    return np.linalg.solve(B.T @ B, B.T)


def doa_phase_gradient(X, f_hz, r=None, coh_min=0.9, closure_max_deg=10.0):
    """Returns (k_xy, gates). k_xy are the in-plane direction cosines.
    Division-free in hardware: 1/f comes from a per-channel LUT, G is a constant, the
    gates are cross-multiplied comparisons."""
    rr, P = correlators(X)
    phi = np.array([np.angle(rr[p]) for p in PAIRS])
    kxy = (C / (2 * np.pi * f_hz)) * (ls_matrix(r) @ phi)
    # coherence gate |r_i0|^2 >= coh^2 P_i P_0  (no division)
    coh_ok = all(abs(rr[p]) ** 2 >= coh_min ** 2 * P[p[0]] * P[p[1]] for p in PAIRS)
    # closure phase: the arms sum to zero, so a plane wave gives arg(r1 r2 r3) = 0
    clos = abs(np.degrees(np.angle(rr[PAIRS[0]] * rr[PAIRS[1]] * rr[PAIRS[2]])))
    in_disc = float(kxy @ kxy) <= 1.0
    gates = dict(coherence=coh_ok, closure=clos <= closure_max_deg, closure_deg=clos,
                 in_visible_space=in_disc, power=float(P[0] / X.shape[1]))
    return kxy, gates


def complete_k(kxy):
    """Third direction cosine from the ground-plane constraint (source below array: kz >= 0)."""
    s = float(kxy @ kxy)
    return np.array([kxy[0], kxy[1], np.sqrt(max(0.0, 1.0 - s))])


# ------------------------------------------------------------------ B2 ------
def null_weights(aD, aJ):
    """w = M a_D - rho a_J, rho = a_J^H a_D.  w^H a_J = 0 exactly; no inversion, no division."""
    M = len(aD)
    rho = np.vdot(aJ, aD)
    return M * aD - rho * aJ, rho


def mainlobe_gate(rho, M, gamma=0.5):
    """|rho|^2 <= gamma M^2  <=>  desired-signal loss (1 - |rho|^2/M^2) no worse than 1-gamma."""
    return abs(rho) ** 2 <= gamma * M * M


def rejection_db(w, a):
    """Jammer rejection relative to a single reference element (noise-normalised)."""
    return -10 * np.log10(max(abs(np.vdot(w, a)) ** 2 / np.vdot(w, w).real, 1e-30))


def desired_gain_db(w, a):
    return 10 * np.log10(abs(np.vdot(w, a)) ** 2 / np.vdot(w, w).real)


def clz_normalise(w, frac_bits=15, lut_bits=0):
    """Fixed-point-style normalisation: shift so ||w||^2 lands in [2^-2, 1), optionally
    refine with a (1 + lut_bits)-bit LUT on ||w||^2. Returns the scaled w."""
    n2 = np.vdot(w, w).real
    shift = np.floor(np.log2(n2) / 2.0) + 1          # CLZ(n2)/2 in hardware
    ws = w / (2.0 ** shift)
    if lut_bits:
        n2s = np.vdot(ws, ws).real                   # in [0.25, 1)
        octave = 0 if n2s < 0.5 else 1
        base = 0.25 * 2 ** octave
        m = np.floor((n2s / base - 1.0) * 2 ** lut_bits)
        centre = base * (1.0 + (m + 0.5) / 2 ** lut_bits)
        ws = ws / np.sqrt(centre)
    return ws


def quantise(w, bits=16):
    """Q1.(bits-1) per real/imag component, after CLZ normalisation (||w|| < 1)."""
    q = 2.0 ** (bits - 1)
    return (np.round(w.real * q) + 1j * np.round(w.imag * q)) / q


NULL_CHECK_DB = -50.0     # ~34 dB above the 16-bit floor (-84 dB), NOT at the operating depth


def self_check(aD, aJ, w, unit_tol=1e-3, null_db=NULL_CHECK_DB):
    """Independent checks: unit-modulus steering, and the null is actually present.
    The null threshold sits ~40 dB above the fixed-point floor so that a corrupted
    weight (SEU, bad write) is caught even when it would still give a 'good' null."""
    unit_ok = np.all(np.abs(np.abs(aD) - 1) < unit_tol) and np.all(np.abs(np.abs(aJ) - 1) < unit_tol)
    null_ok = abs(np.vdot(w, aJ)) ** 2 <= 10 ** (null_db / 10) * np.vdot(w, w).real
    return bool(unit_ok and null_ok)
