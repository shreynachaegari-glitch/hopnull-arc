"""
Null survival: how long a committed null keeps >= R dB of rejection when the stored
direction is NOT refreshed (FIISM reuse, blinking jammer, partial-band revisit).

  (A) body-frame hold  - what stored per-band weights (US 4,800,390 style) or airframe
                          direction tracking do: the null is fixed to the airframe.
  (B) earth-frame state - HOPNULL-ARC: direction stored in earth frame, re-rotated with
                          IMU attitude every hop; only true LOS motion degrades it.
"""
import numpy as np
from . import params as P
from .array import unit, steer, rot_z, rot_x
from .nuller import null_weights, rejection_db

F = P.LINK["f_hz"]


def scenario(jam_az, jam_range=5_000.0, gcs_az=0.0, gcs_range=P.DRDO["link_range_m"],
             alt=P.LINK["uav_alt_m"]):
    kD = unit(gcs_az, -np.degrees(np.arctan2(alt, gcs_range)))
    kJ = unit(jam_az, -np.degrees(np.arctan2(alt, jam_range)))
    return kD, kJ


def tolerance_deg(kD, kJ, target_db=30.0, f=F):
    """Smallest angular perturbation of the TRUE jammer direction (worst direction on a
    ring of 16) that drops rejection below target_db, for weights built on kJ."""
    w, _ = null_weights(steer(kD, f), steer(kJ, f))
    # orthonormal basis around kJ
    t1 = np.cross(kJ, [0, 0, 1.0]); t1 /= np.linalg.norm(t1)
    t2 = np.cross(kJ, t1)
    # first-crossing scan (the pattern is not monotonic: end-fire geometries have
    # double zeros, so a bisection can jump past the first crossing)
    grid = np.radians(np.arange(0.005, 20.0, 0.005))
    worst = np.inf
    for phi in np.linspace(0, 2 * np.pi, 16, endpoint=False):
        u = np.cos(phi) * t1 + np.sin(phi) * t2
        for g in grid:
            if g >= worst:
                break
            k = np.cos(g) * kJ + np.sin(g) * u
            if rejection_db(w, steer(k, f)) < target_db:
                worst = g
                break
    return np.degrees(worst)


def tolerance_sweep(target_db=30.0, jam_range=5_000.0):
    """Tolerance over the jammer azimuths (15 deg grid) that pass the mainlobe gate."""
    from .geometry import defended_pairs
    pairs = defended_pairs(step=15, jam_range=jam_range)
    az = np.array([a for a, _, _ in pairs])
    tol = np.array([tolerance_deg(kD, kJ, target_db) for _, kD, kJ in pairs])
    return az, tol


def body_hold_timeseries(t, rate_dps, jam_az=90.0, jam_range=5_000.0, axis="yaw"):
    kD, kJ = scenario(jam_az, jam_range)
    w, _ = null_weights(steer(kD, F), steer(kJ, F))
    out = []
    for ti in t:
        R = rot_z(rate_dps * ti) if axis == "yaw" else rot_x(rate_dps * ti)
        out.append(rejection_db(w, steer(R.T @ kJ, F)))
    return np.array(out)


def earth_state_timeseries(t, rate_dps, jam_az=90.0, jam_range=5_000.0,
                           v_rel=P.JAMMER["speed_mps"] + P.PLATFORM["speed_mps"],
                           gyro_bias_dph=P.IMU["gyro_bias_dph"]):
    """IMU re-rotation every hop; truth moves at worst-case tangential LOS rate v_rel/R;
    the predicted attitude carries gyro-bias drift."""
    kD_e, kJ_e = scenario(jam_az, jam_range)
    los_rate = np.degrees(v_rel / jam_range)
    out = []
    for ti in t:
        R_true = rot_z(rate_dps * ti)
        R_imu = rot_z(rate_dps * ti + gyro_bias_dph / 3600.0 * ti)
        kJ_true_e = rot_z(los_rate * ti) @ kJ_e
        w, _ = null_weights(steer(R_imu.T @ kD_e, F), steer(R_imu.T @ kJ_e, F))
        out.append(rejection_db(w, steer(R_true.T @ kJ_true_e, F)))
    return np.array(out)


def crossing_time(t, rej, target_db=30.0):
    idx = np.argmax(rej < target_db)
    return float(t[idx]) if rej[idx] < target_db else float("inf")


def fiism_hit_probability(max_age_s, hop_rate, n_subbands):
    """P(a sub-band is revisited within max_age) for uniform pseudo-random hopping."""
    n = np.floor(max_age_s * hop_rate)
    return 1.0 - (1.0 - 1.0 / n_subbands) ** n


def tilt_observability(sigma_kxy=0.005, jam_el_deg=-5.7, target_err_deg=None):
    """A planar array measures (kx,ky) well; kz = sqrt(1-kx^2-ky^2) is ill-conditioned
    near the horizon. After the array plane tilts by dT (roll/pitch), the kz error leaks
    into the in-plane components. Returns the elevation error and the tilt at which the
    in-plane error reaches target_err_deg (the TILT_MAX bound). Pure yaw leaks nothing."""
    kz = np.sin(np.radians(-jam_el_deg))
    kxy = np.sqrt(1 - kz * kz)
    dkz = kxy * sigma_kxy / kz                     # first-order propagation
    el_err = np.degrees(dkz / np.cos(np.radians(jam_el_deg)))
    if target_err_deg is None:
        return el_err, None
    tilt = np.degrees(np.arcsin(min(1.0, np.radians(target_err_deg) / dkz)))
    return el_err, tilt


def summary():
    res = {}
    az, tol = tolerance_sweep()
    res["tol30_deg"] = dict(az=az.tolist(), tol=tol.round(3).tolist(),
                            min=float(tol.min()), median=float(np.median(tol)))
    th = float(tol.min())            # safety bounds are set from the WORST geometry
    th_med = float(np.median(tol))
    turn = P.PLATFORM["turn_rate_dps"]
    vrel = P.JAMMER["speed_mps"] + P.PLATFORM["speed_mps"]
    rows = []
    for R in P.JAMMER["ranges_m"]:
        w_los = np.degrees(vrel / R)
        w_jam = np.degrees(P.JAMMER["speed_mps"] / R)
        rows.append(dict(range_km=R / 1e3, los_rate_dps=w_los,
                         t_earth_s=th / w_los, t_earth_med_s=th_med / w_los,
                         t_jammer_only_s=th / w_jam, ratio_vs_turn=turn / w_los))
    res["survival_table"] = rows
    res["t_body_turn_ms"] = th / turn * 1e3
    res["t_body_turn_med_ms"] = th_med / turn * 1e3
    res["t_body_maxrate_ms"] = th / P.PLATFORM["max_body_rate_dps"] * 1e3
    # the original claim: jammer at 30 m/s, 10 km, own-ship parallax excluded
    res["rate_ratio_10km_jammer_only"] = turn / np.degrees(P.JAMMER["speed_mps"] / 10e3)
    # IMU error budget over a 1 s reuse at max body rate
    res["imu"] = dict(
        gyro_drift_deg_per_s_age=P.IMU["gyro_bias_dph"] / 3600.0,
        skew_err_deg=P.PLATFORM["max_body_rate_dps"] * P.IMU["timestamp_skew_s"],
        abs_attitude_err_cancels=True)
    # FIISM hit-rate with the aging window each approach can afford
    hr, S = 1000.0, P.CASEB["n_subbands"]
    age_body = res["t_body_maxrate_ms"] / 1e3
    age_earth = rows[1]["t_earth_s"]            # 2 km worst-case standoff
    res["fiism_hit"] = dict(hop_rate=hr, n_subbands=S,
                            age_body_s=age_body, p_body=float(fiism_hit_probability(age_body, hr, S)),
                            age_earth_s=age_earth, p_earth=float(fiism_hit_probability(age_earth, hr, S)))
    el_err, tilt = tilt_observability(target_err_deg=th / 2)
    res["tilt"] = dict(sigma_kxy=0.005, el_err_deg=float(el_err), tilt_max_deg=float(tilt))
    return res


def stale_weight_vs_span(spans=(0.01, 0.034, 0.10, 0.20, 0.40), trials=300, seed=3):
    """Weights built at f0 reused at f0(1+x) (what per-band weight storage does across a
    wide hop span). Direction state + late frequency binding has no such loss."""
    from .geometry import random_defended
    rng = np.random.default_rng(seed)
    rows = []
    for x in spans:
        r = []
        for _ in range(trials):
            kD, kJ = random_defended(rng)
            f0 = 2.4e9
            w, _ = null_weights(steer(kD, f0), steer(kJ, f0))
            r.append(rejection_db(w, steer(kJ, f0 * (1 + x))))
        rows.append(dict(span_pct=100 * x, median_db=float(np.median(r)), p10_db=float(np.percentile(r, 10))))
    return rows
