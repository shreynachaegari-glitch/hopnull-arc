"""
Cycle-level latency budget from explicit operation counts.

Resources assumed (V1): one pipelined CORDIC (16 iterations, latency 18, 1 result/cycle),
HW["mults"] shared real multipliers for B1-B3, a dedicated beamformer MAC array.
Cycles per stage = CORDIC fill (if used) + CORDIC issue slots + ceil(mults / M) + overhead.
The whole estimate is multiplied by HW["derate"] before any margin is claimed; the figure
is replaced by post-synthesis numbers at M9.
"""
import math
from . import params as P

HW = P.HW

# (stage, cordic_ops, real_mults, notes)
B1_OPS = [
    ("3 centre-arm correlators -> phase/magnitude (CORDIC vectoring)", 3, 0, "streamed during T_obs"),
    ("coherence gate |r_i0|^2 >= g^2 P_i P_0 (cross-multiplied)", 0, 9, "no division"),
    ("closure phase arg(r1 r2 r3) = 0 (plane-wave / multipath gate)", 1, 8, "arms sum to zero"),
    ("k_xy = LUT[1/f] * G(2x3) phi", 0, 8, "constant G, per-channel reciprocal LUT"),
    ("k_z = sqrt(1-kx^2-ky^2), ground-plane sign", 0, 2, "+ sqrt unit"),
    ("quaternion -> DCM, body -> earth (C_eb k)", 0, 21, "IMU attitude at t_obs"),
    ("presence gate + FIISM write-back", 0, 2, ""),
]
B2_OPS = [
    ("attitude prediction q(n+1) = q(n) x dq(w dT)", 0, 24, "first-order + renorm"),
    ("earth -> body for k_J and k_D (C_eb^T k)", 0, 30, "DCM + 2 rotations"),
    ("element phases 2pi f/c (p.k), 4 elem x 2 dirs", 0, 24, ""),
    ("steering vectors e^{j phi} (CORDIC rotation)", 8, 0, ""),
    ("self-check |a_m|^2 = 1", 0, 16, "independent of weight path"),
    ("rho = a_J^H a_D ; mainlobe gate |rho|^2 <= g M^2", 0, 18, ""),
    ("w = M a_D - rho a_J (M a_D is a shift)", 0, 16, ""),
    ("||w||^2, CLZ shift, 16-entry LUT refine", 0, 16, "no reciprocal"),
    ("null self-check |w^H a_J|^2 <= eps ||w||^2", 0, 18, "verifies the null exists"),
]
B3_OPS = [
    ("TRUST_CUT <- max(TRUST_CUT, now - MAX_AGE_eff)", 0, 0, "1 subtract + 1 max"),
    ("FIISM read + validity/tilt checks", 0, 2, "1 SRAM read"),
    ("arbitration FRESH > FIISM > BYPASS, freq-tag", 0, 0, ""),
    ("bundle CRC/parity + shadow-buffer write", 0, 0, "4 complex words"),
]
B3_FIXED_CYCLES = 16

# V2 dual-jammer path (Tier 2), split by rate.
# Per hop (critical path, inside T1):
V2_PERHOP = [
    ("steering for 2 stored jammers at f(n+1)", 6, 18, ""),
    ("model covariance at f(n+1): sum p_k a_k a_k^H + (1+dl) s^2 I", 0, 120, "10 unique entries x 2 sources"),
    ("4x4 Cholesky (rsqrt via CORDIC)", 4, 56, "no explicit inverse"),
    ("forward + back substitution with a_D (MVDR)", 0, 80, ""),
    ("null self-check on both jammers", 0, 36, ""),
]
# Background (direction state; may span hops because directions age in >= 0.17 s):
MUSIC_EVALS = 64 * 8 + 2 * 3 * 25
V2_BACKGROUND = [
    ("4x4 Hermitian EVD: cyclic Jacobi, 5 fixed sweeps x 6 rotations", 60, 30 * 96, "bounded: no convergence test"),
    ("source count (eigenvalue threshold, cross-multiplied)", 0, 8, ""),
    (f"grid MUSIC: {MUSIC_EVALS} fixed evaluations (coarse 64x8 + 3-level 5x5 refine)", 3 * MUSIC_EVALS, 45 * MUSIC_EVALS, "bounded"),
    ("body -> earth rotation + FIISM write", 0, 42, ""),
]
V2_COV_MULTS_PER_SAMPLE = 40   # 10 complex MACs / sample, streamed during T_obs


def stage_cycles(ops, parallel_cordic_fill=True):
    cordic = sum(o[1] for o in ops)
    mults = sum(o[2] for o in ops)
    fill = HW["cordic_latency"] if cordic else 0
    return fill + cordic + math.ceil(mults / HW["mults"]) + HW["overhead_per_stage"] * len(ops)


def budget(clock_hz, v2=False):
    b1 = stage_cycles(B1_OPS) + HW["sqrt_latency"]
    b2 = stage_cycles(B2_OPS)
    b3 = B3_FIXED_CYCLES + stage_cycles(B3_OPS)
    v2c = stage_cycles(V2_PERHOP) if v2 else 0
    raw = b1 + b2 + b3 + v2c
    der = raw * HW["derate"]
    return dict(B1=b1, B2=b2, B3=b3, V2=v2c, raw_cycles=raw, derated_cycles=der,
                T_B_us=der / clock_hz * 1e6)


def margins(sc, clock_hz, v2=False, settle="nco"):
    """Timing constraints (named TC1-TC3 in the annexures; T1-T4 there mean delivery tiers):
       TC1: G + T_obs + T_B <= T_hop + L_pre (candidate ready by the swap sample)
       TC2: L_total + T_flush <= G           (mute hidden in the modem's own guard)
       TC3: NEXT_FREQ lead >= T_B2 + T_B3    (sideband delivers f(n+1) >= 1 hop ahead)
       S : front-end settle fits inside G   (NCO retune vs analog PLL relock)"""
    T_hop = 1.0 / sc["hop_rate"]
    G = sc["G_s"]
    T_obs = P.OBS["K"] / P.FS_HZ
    bud = budget(clock_hz, v2)
    T_B = bud["T_B_us"] * 1e-6
    t1 = (T_hop + P.PIPE["L_pre_s"]) - (G + T_obs + T_B)
    t2 = G - (P.PIPE["L_total_s"] + P.PIPE["T_flush_s"])
    t3 = T_hop - (bud["B2"] + bud["B3"]) * HW["derate"] / clock_hz
    settle_s = P.PIPE["settle_nco_s"] if settle == "nco" else P.PIPE["settle_pll_s"]
    ts = G - settle_s
    return dict(name=sc["name"], hop_rate=sc["hop_rate"], T_hop_us=T_hop * 1e6, G_us=G * 1e6,
                T_obs_us=T_obs * 1e6, T_B_us=T_B * 1e6,
                T1_slack_us=t1 * 1e6, T1_util=(G + T_obs + T_B) / (T_hop + P.PIPE["L_pre_s"]),
                T2_slack_us=t2 * 1e6, T3_slack_us=t3 * 1e6, settle_slack_us=ts * 1e6,
                ok=all(x >= 0 for x in (t1, t2, t3, ts)))


def v2_background(clock_hz):
    cyc = stage_cycles(V2_BACKGROUND) * HW["derate"]
    t = cyc / clock_hz
    rows = []
    for sc in P.TIMING_SCENARIOS:
        T_hop = 1.0 / sc["hop_rate"]
        busy = budget(clock_hz, v2=True)["T_B_us"] * 1e-6
        rows.append(dict(name=sc["name"], hop_rate=sc["hop_rate"],
                         hops=math.ceil(t / (T_hop - busy))))
    return dict(cycles=cyc, time_us=t * 1e6, music_evals=MUSIC_EVALS,
                cov_mults_per_s=V2_COV_MULTS_PER_SAMPLE * P.FS_HZ,
                cov_multipliers_needed=math.ceil(V2_COV_MULTS_PER_SAMPLE * P.FS_HZ / clock_hz),
                per_scenario=rows)


def max_hop_rate(clock_hz, G_s=10e-6, v2=False):
    T_B = budget(clock_hz, v2)["T_B_us"] * 1e-6
    T_obs = P.OBS["K"] / P.FS_HZ
    return 1.0 / (G_s + T_obs + T_B - P.PIPE["L_pre_s"])


def case_b(hop_rate=1000.0, G_s=20e-6):
    """Modem exposes no hop sideband.
    Timing: a local dwell timer is locked to observed hop edges. Between re-locks it
    coasts, drifting by (ppm_m + ppm_a) * T_hop per hop. The swap must stay inside G/2
    of the true boundary:   eps0 + N * d_ppm * T_hop <= G/2  ->  N_coast.
    Frequency: unknown until the hop lands -> channelizer identifies the sub-band after
    fft_n/fs_wide, then a PRE-COMPUTED per-sub-band weight (direction state is
    frequency-free) is selected. Unprotected time per hop = alignment + detect + select."""
    cb = P.CASEB
    T_hop = 1.0 / hop_rate
    d = (cb["clock_ppm_modem"] + cb["clock_ppm_accel"]) * 1e-6
    n_coast = math.floor((G_s / 2 - cb["transition_detect_s"]) / (d * T_hop))
    t_detect = cb["fft_n"] / cb["fs_wide_hz"]
    t_select = 8 / P.CLOCKS["asic_hz"]
    unprot = G_s / 2 + t_detect + t_select
    # sub-band-centre weight error: worst phase error across the aperture
    band = P.BAND_BENCH
    sub_bw = (band["f_hi"] - band["f_lo"]) / cb["n_subbands"]
    return dict(hop_rate=hop_rate, G_us=G_s * 1e6, drift_ns_per_hop=d * T_hop * 1e9,
                n_coast_hops=n_coast, coast_ms=n_coast * T_hop * 1e3,
                t_detect_us=t_detect * 1e6, unprotected_us=unprot * 1e6,
                unprotected_frac=unprot / T_hop, subband_bw_mhz=sub_bw / 1e6)


def subband_table_rejection(n_subbands=P.CASEB["n_subbands"]):
    """Rejection when weights built at the sub-band centre are applied at the band edge."""
    import numpy as np
    from .array import steer
    from .nuller import null_weights, rejection_db
    from .geometry import defended_pairs
    band = P.BAND_BENCH
    sub = (band["f_hi"] - band["f_lo"]) / n_subbands
    worst = []
    for _, kD, kJ in defended_pairs(step=15):
        fc = band["f_lo"] + sub / 2
        w, _ = null_weights(steer(kD, fc), steer(kJ, fc))
        worst.append(rejection_db(w, steer(kJ, fc + sub / 2)))
    return float(min(worst)), float(np.median(worst))


def gain_step_db():
    """Output-gain step between hops caused by CLZ normalisation, with/without LUT."""
    import numpy as np
    from .nuller import clz_normalise
    rng = np.random.default_rng(1)
    out = {}
    for bits in (0, 3):
        g = []
        for _ in range(4000):
            w = (rng.normal(size=4) + 1j * rng.normal(size=4)) * 10 ** rng.uniform(-3, 3)
            ws = clz_normalise(w, lut_bits=bits)
            g.append(20 * np.log10(np.linalg.norm(ws)))
        out[f"lut{bits}"] = float(max(g) - min(g))
    return out


def summary():
    res = dict(ops=dict(B1=B1_OPS, B2=B2_OPS, B3=B3_OPS, V2_PERHOP=V2_PERHOP, V2_BACKGROUND=V2_BACKGROUND))
    for tag, clk in (("fpga", P.CLOCKS["fpga_hz"]), ("asic", P.CLOCKS["asic_hz"])):
        res[f"budget_{tag}"] = budget(clk)
        res[f"budget_{tag}_v2"] = budget(clk, v2=True)
        res[f"margins_{tag}"] = [margins(sc, clk) for sc in P.TIMING_SCENARIOS]
        res[f"margins_{tag}_v2"] = [margins(sc, clk, v2=True) for sc in P.TIMING_SCENARIOS]
        res[f"max_hop_{tag}"] = max_hop_rate(clk)
        res[f"max_hop_{tag}_v2"] = max_hop_rate(clk, v2=True)
        res[f"v2_background_{tag}"] = v2_background(clk)
    res["pll_settle_check"] = [margins(sc, P.CLOCKS["asic_hz"], settle="pll") for sc in P.TIMING_SCENARIOS]
    res["case_b"] = [case_b(sc["hop_rate"], sc["G_s"]) for sc in P.TIMING_SCENARIOS]
    res["subband_rejection_db"] = subband_table_rejection()
    res["gain_step_db"] = gain_step_db()
    return res
