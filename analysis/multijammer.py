"""
Tier-2 V2 path: two simultaneous jammers.

Two-rate split (only possible because FIISM stores DIRECTIONS, which age in 0.17-3 s):
  background (may span several hops):
      4x4 sample covariance at f(n) -> fixed-sweep Jacobi EVD (bounded, no convergence
      test) -> source count -> fixed 3-level grid MUSIC (bounded evaluations) ->
      earth-frame directions into FIISM
  per hop (critical path, inside T1):
      model covariance AT f(n+1): sum p_k a_k a_k^H + (1+dl) s^2 I -> 4x4 Cholesky ->
      forward/back substitution with a_D -> MVDR weights (no explicit inverse)

Also shows why the design stores directions rather than weights: a covariance/weight
learned at f(n) and applied at f(n+1) (per-band weight storage, US 4,800,390 style,
over a wide band) loses most of its depth.
"""
import numpy as np
from . import params as P
from .array import steer, unit
from .nuller import doa_phase_gradient, rejection_db, desired_gain_db
from .survival import scenario

RNG = np.random.default_rng(7)
AZ_STEP = 360 / 64
EL_GRID = np.array([-1.0, -3.0, -6.0, -10.0, -20.0, -35.0, -60.0, -85.0])
MUSIC_LEVELS = 3        # refinement levels, 5x5 local grid each, step halves
LOCAL = 5


def jacobi_eigh(A, sweeps=5):
    """Cyclic complex Jacobi with a FIXED number of sweeps (bounded WCET, no convergence test)."""
    A = A.astype(complex).copy()
    n = A.shape[0]
    V = np.eye(n, dtype=complex)
    for _ in range(sweeps):
        for p in range(n - 1):
            for q in range(p + 1, n):
                b = A[p, q]
                if abs(b) == 0:
                    continue
                al = np.angle(b)
                th = 0.5 * np.arctan2(2 * abs(b), (A[q, q] - A[p, p]).real)
                c, s = np.cos(th), np.sin(th)
                J = np.eye(n, dtype=complex)
                J[p, p] = c; J[q, q] = c
                J[p, q] = s * np.exp(1j * al); J[q, p] = -s * np.exp(-1j * al)
                A = J.conj().T @ A @ J
                V = V @ J
    return np.real(np.diag(A)), V, np.linalg.norm(A - np.diag(np.diag(A)))


def music_cost(En, f, az, el):
    a = steer(unit(az, el), f)
    return float(np.linalg.norm(En.conj().T @ a) ** 2)


def grid_music(En, f, n_src):
    """Fixed coarse grid + fixed local refinement: evaluation count is a constant."""
    evals = 0
    C = np.empty((64, len(EL_GRID)))
    for i in range(64):
        for j, e in enumerate(EL_GRID):
            C[i, j] = music_cost(En, f, i * AZ_STEP, e)
            evals += 1
    # pick n_src separated minima (non-maximum suppression on the wrapped az axis)
    picks = []
    order = np.dstack(np.unravel_index(np.argsort(C, axis=None), C.shape))[0]
    for i, j in order:
        if all(min(abs(i - pi), 64 - abs(i - pi)) > 2 for pi, _ in picks):
            picks.append((i, j))
        if len(picks) == n_src:
            break
    out = []
    for i, j in picks:
        az, el = i * AZ_STEP, EL_GRID[j]
        daz = AZ_STEP / 2
        del_ = max(2.0, (EL_GRID[min(j + 1, len(EL_GRID) - 1)] - EL_GRID[max(j - 1, 0)]) / 4)
        for _ in range(MUSIC_LEVELS):
            best = (np.inf, az, el)
            for u in np.linspace(-1, 1, LOCAL):
                for v in np.linspace(-1, 1, LOCAL):
                    ee = float(np.clip(el + v * del_, -89.9, -0.05))
                    c = music_cost(En, f, az + u * daz, ee)
                    evals += 1
                    if c < best[0]:
                        best = (c, az + u * daz, ee)
            _, az, el = best
            daz /= 2
            del_ /= 2
        out.append(unit(az, el))
    return out, evals


def cholesky_mvdr(R, aD):
    L = np.linalg.cholesky(R)
    y = np.linalg.solve(L, aD)                     # forward substitution in RTL
    return np.linalg.solve(L.conj().T, y)          # back substitution


def run(jams=((70.0, 30.0), (140.0, 25.0)), f_n=2.405e9, f_n1=2.478e9, K=256, sweeps=5,
        diag_load=0.1, rng=RNG, jam_range=5_000.0):
    kD, _ = scenario(0.0)
    kJs = [scenario(az, jam_range)[1] for az, _ in jams]
    pw = [10 ** (j / 10) for _, j in jams]
    X = (rng.normal(size=(4, K)) + 1j * rng.normal(size=(4, K))) / np.sqrt(2)
    for k, p in zip(kJs, pw):
        s = (rng.normal(size=K) + 1j * rng.normal(size=K)) * np.sqrt(p / 2)
        X = X + np.outer(steer(k, f_n), s)
    R = X @ X.conj().T / K

    # V1 behaviour: the coherence/closure gates see two sources and refuse to commit
    _, gates = doa_phase_gradient(X, f_n)

    lam, V, off = jacobi_eigh(R, sweeps)
    order = np.argsort(lam)[::-1]
    lam, V = lam[order], V[:, order]
    sigma2 = lam[-1]
    n_src = int(np.sum(lam > 10 * sigma2))
    ks, evals = grid_music(V[:, n_src:], f_n, n_src)
    # in-plane error is what the null depends on (a planar array sees only kx, ky)
    doa_err = [min(np.degrees(np.arcsin(min(1.0, np.linalg.norm(kh[:2] - kt[:2])))) for kh in ks) for kt in kJs]

    aD1 = steer(kD, f_n1)
    Rm = sigma2 * (1 + diag_load) * np.eye(4, dtype=complex)
    for kh, p in zip(ks, sorted(lam[:n_src] - sigma2, reverse=True)):
        a = steer(kh, f_n1)
        Rm += p * np.outer(a, a.conj())
    w = cholesky_mvdr(Rm, aD1)
    rej = [rejection_db(w, steer(k, f_n1)) for k in kJs]

    # counter-example: sample-matrix weights learned at f(n), applied at f(n+1)
    w_stale = cholesky_mvdr(R + 0.1 * sigma2 * np.eye(4), steer(kD, f_n))
    rej_stale = [rejection_db(w_stale, steer(k, f_n1)) for k in kJs]
    rej_same = [rejection_db(w_stale, steer(k, f_n)) for k in kJs]

    return dict(jammers=[dict(az=a, jnr_db=j) for a, j in jams], f_n=f_n, f_n1=f_n1, K=K,
                v1_gates=dict(coherence=bool(gates["coherence"]), closure=bool(gates["closure"])),
                jacobi_sweeps=sweeps, jacobi_offdiag=float(off), n_src=n_src, music_evals=evals,
                doa_err_deg=[float(x) for x in doa_err],
                v2_rejection_db=[float(x) for x in rej], v2_desired_gain_db=float(desired_gain_db(w, aD1)),
                stale_weight_rejection_db=[float(x) for x in rej_stale],
                same_freq_smi_rejection_db=[float(x) for x in rej_same])


def monte_carlo(trials=150, rng=RNG):
    from .geometry import random_defended
    rows, errs, v1_refused, stale = [], [], 0, []
    for _ in range(trials):
        _, k1 = random_defended(rng)
        while True:
            _, k2 = random_defended(rng)
            if np.degrees(np.arccos(np.clip(k1 @ k2, -1, 1))) > 30:
                break
        az = [float(np.degrees(np.arctan2(k[1], k[0]))) for k in (k1, k2)]
        r = run(jams=((az[0], rng.uniform(20, 40)), (az[1], rng.uniform(20, 40))),
                f_n=rng.uniform(2.400e9, 2.4835e9), f_n1=rng.uniform(2.400e9, 2.4835e9), rng=rng)
        v1_refused += not (r["v1_gates"]["coherence"] and r["v1_gates"]["closure"])
        if r["n_src"] == 2:
            rows.append(min(r["v2_rejection_db"]))
            errs.append(max(r["doa_err_deg"]))
            stale.append(min(r["stale_weight_rejection_db"]))
    rows = np.array(rows)
    return dict(trials=trials, detected_2=len(rows), v1_refused=v1_refused,
                median_db=float(np.median(rows)), p10_db=float(np.percentile(rows, 10)),
                doa_err_median_deg=float(np.median(errs)), doa_err_p90_deg=float(np.percentile(errs, 90)),
                stale_median_db=float(np.median(stale)))


def summary():
    return dict(example=run(), mc=monte_carlo())
