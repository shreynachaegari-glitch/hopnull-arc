"""
What limits the null in practice, and what that means for the test plan.

1. Calibration-limited depth: per-channel phase/amplitude error left after calibration
   (and any drift from temperature or vibration) bounds rejection regardless of how good
   the direction estimate is.  -> sets the thermal/vibration pass criterion (Tier 1).
2. Estimation-limited depth: a phase-gradient estimate from K snapshots at a given JNR.
   Residual jammer-to-noise after nulling ~ const/K, independent of JNR, until the
   calibration floor takes over.  -> sizes the observation window T_obs = K / fs.
"""
import numpy as np
from . import params as P
from .array import steer
from .nuller import null_weights, rejection_db, doa_phase_gradient, complete_k
from .survival import scenario
from .geometry import random_defended

F = P.LINK["f_hz"]
RNG = np.random.default_rng(20260929)


def cal_limited(phase_rms_deg, trials=P.CAL["trials"], rng=RNG):
    """Rejection when the nuller uses nominal steering but the channels carry
    residual complex gain errors. Returns (median, 10th percentile) in dB."""
    amp_rms_db = P.CAL["amp_rms_db_per_deg"] * phase_rms_deg
    rej = np.empty(trials)
    for i in range(trials):
        kD, kJ = random_defended(rng)
        e = (10 ** (rng.normal(0, amp_rms_db, 4) / 20)) * np.exp(1j * np.radians(rng.normal(0, phase_rms_deg, 4)))
        e /= e[0]                                        # errors relative to the reference element
        w, _ = null_weights(steer(kD, F), steer(kJ, F))
        rej[i] = rejection_db(w, steer(kJ, F) * e)
    return float(np.median(rej)), float(np.percentile(rej, 10))


def cal_sweep():
    rows = []
    for s in P.CAL["phase_rms_deg_list"]:
        med, p10 = cal_limited(s)
        rows.append(dict(phase_rms_deg=s, median_db=med, p10_db=p10))
    return rows


def phase_budget_for(target_db, rows):
    """Largest RMS phase error whose 10th-percentile rejection still meets target."""
    ok = [r["phase_rms_deg"] for r in rows if r["p10_db"] >= target_db]
    return max(ok) if ok else None


def estimation_limited(K, jnr_db, trials=300, jam_az=60.0, rng=RNG):
    """End-to-end: jammer + noise snapshots -> phase-gradient DoA -> weights -> rejection.
    Returns median rejection (dB), residual J/N after nulling (dB), in-plane DoA sigma."""
    kD, kJ = scenario(jam_az)
    aD, aJ = steer(kD, F), steer(kJ, F)
    jnr = 10 ** (jnr_db / 10)
    rej, err = [], []
    for _ in range(trials):
        s = (rng.normal(size=K) + 1j * rng.normal(size=K)) * np.sqrt(jnr / 2)
        n = (rng.normal(size=(4, K)) + 1j * rng.normal(size=(4, K))) / np.sqrt(2)
        X = np.outer(aJ, s) + n
        kxy, _ = doa_phase_gradient(X, F)
        kJ_hat = complete_k(kxy)
        w, _ = null_weights(aD, steer(kJ_hat, F))
        rej.append(rejection_db(w, aJ))
        err.append(np.linalg.norm(kxy - kJ[:2]))
    med = float(np.median(rej))
    return med, jnr_db - med, float(np.sqrt(np.mean(np.square(err)) / 2))


def estimation_sweep():
    rows = []
    for K in (32, 64, 128, 256, 512):
        for jnr in (10, 20, 30, 40):
            rej, resid, sig = estimation_limited(K, jnr)
            rows.append(dict(K=K, jnr_db=jnr, rejection_db=rej, residual_jn_db=resid, sigma_kxy=sig))
    return rows


def combined_rejection_db(est_db, cal_db):
    """Independent residuals add in power."""
    return -10 * np.log10(10 ** (-est_db / 10) + 10 ** (-cal_db / 10))


def summary():
    rows = cal_sweep()
    est = estimation_sweep()
    budget30 = phase_budget_for(30.0, rows)
    budget25 = phase_budget_for(25.0, rows)
    K = P.OBS["K"]
    k_rows = [r for r in est if r["K"] == K]
    return dict(cal=rows, phase_budget_30db_p10_deg=budget30, phase_budget_25db_p10_deg=budget25,
                est=est, K=K, T_obs_us=K / P.FS_HZ * 1e6,
                sigma_kxy_at_K_20db=next(r["sigma_kxy"] for r in k_rows if r["jnr_db"] == 20),
                residual_jn_at_K=[dict(jnr_db=r["jnr_db"], residual_jn_db=r["residual_jn_db"]) for r in k_rows])
