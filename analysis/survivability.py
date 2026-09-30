"""
Link survivability on the DRDO reference scenario (5 km C2 link), plus fault, capture
and GNSS-denial survivability.

Burn-through (denial) range: the jammer standoff inside which the link falls below the
modem's required SINR. HOPNULL-ARC divides it by 10^((R + G_D)/20), where R is the
effective rejection and G_D the array gain kept toward the GCS.
"""
import math
import numpy as np
from . import params as P
from .array import steer, unit
from .nuller import null_weights, desired_gain_db
from .survival import scenario

L = P.LINK


def fspl_db(d_m, f_hz=L["f_hz"]):
    return 20 * math.log10(4 * math.pi * d_m * f_hz / P.C)


def range_for_fspl(fspl, f_hz=L["f_hz"]):
    return 10 ** (fspl / 20) * P.C / (4 * math.pi * f_hz)


def link_budget():
    s = L["gcs_eirp_dbm"] - fspl_db(P.DRDO["link_range_m"]) + L["uav_elem_gain_dbi"] - L["fade_margin_db"]
    n = -174 + 10 * math.log10(P.BAND_BENCH["ch_bw_hz"]) + L["noise_figure_db"]
    return dict(fspl_db=fspl_db(P.DRDO["link_range_m"]), S_dbm=s, N_dbm=n, SNR_db=s - n,
                margin_db=s - n - L["sinr_req_db"])


def array_gain_after_null():
    """Median desired-signal gain kept toward the GCS over mainlobe-gated geometries."""
    from .geometry import defended_pairs
    g = []
    for _, kD, kJ in defended_pairs(step=5):
        w, _ = null_weights(steer(kD, L["f_hz"]), steer(kJ, L["f_hz"]))
        g.append(desired_gain_db(w, steer(kD, L["f_hz"])))
    return float(np.median(g)), float(min(g))


def horizon_km():
    return 4.12 * (math.sqrt(L["uav_alt_m"]) + math.sqrt(L["jammer_mast_m"]))


def denial_range_km(jam_eirp_dbm, rejection_db=0.0, gain_db=0.0, barrage=False):
    lb = link_budget()
    s = lb["S_dbm"] + gain_db
    j_max_mw = 10 ** ((s - L["sinr_req_db"]) / 10) - 10 ** (lb["N_dbm"] / 10)
    if j_max_mw <= 0:
        return float("inf")
    j_max = 10 * math.log10(j_max_mw) + rejection_db
    eirp = jam_eirp_dbm - (10 * math.log10(P.BAND_BENCH["n_channels"]) if barrage else 0.0)
    return range_for_fspl(eirp - j_max) / 1e3


def burn_through_table(rejection_db, gain_db):
    rows = []
    for eirp in (30, 40, 50, 60):
        r0 = denial_range_km(eirp)
        r1 = denial_range_km(eirp, rejection_db, gain_db)
        rows.append(dict(jam_eirp_dbm=eirp, w_eirp=10 ** ((eirp - 30) / 10),
                         spot_no_null_km=r0, spot_null_km=r1,
                         barrage_no_null_km=denial_range_km(eirp, barrage=True),
                         barrage_null_km=denial_range_km(eirp, rejection_db, gain_db, barrage=True)))
    return rows


def max_jnr_db(rejection_db, gain_db):
    """Largest jammer-to-noise ratio (per element, in-channel) the link survives."""
    lb = link_budget()
    snr = 10 ** ((lb["SNR_db"] + gain_db) / 10)
    x = snr / 10 ** (L["sinr_req_db"] / 10) - 1
    return 10 * math.log10(x) + rejection_db, 10 * math.log10(10 ** (lb["SNR_db"] / 10) / 10 ** (L["sinr_req_db"] / 10) - 1)


def follower(t_proc_s=20e-6, excess_path_m=2_000.0, hop_rate=1000.0, cover_needed=0.25):
    """Follower/repeater: reacts t_proc after the hop lands, plus excess path delay.
    Covered fraction of the dwell, and the hop rate that FHSS alone would need."""
    delay = t_proc_s + excess_path_m / P.C
    T_hop = 1 / hop_rate
    covered = max(0.0, 1 - delay / T_hop)
    need = (1 - cover_needed) / delay
    return dict(delay_us=delay * 1e6, covered_frac=covered, fhss_only_hop_rate_needed=need)


def gnss_denied_desired_loss(err_list=(2, 5, 10, 20)):
    """Desired-gain loss when the GCS direction is wrong by e deg (INS drift, no GNSS).
    Jammer tracking needs attitude only (AHRS), so it is unaffected."""
    out = []
    kD, kJ = scenario(90.0)
    f = L["f_hz"]
    for e in err_list:
        kD_wrong = unit(e, -np.degrees(np.arcsin(kD[2])))
        w, _ = null_weights(steer(kD_wrong, f), steer(kJ, f))
        out.append(dict(err_deg=e, loss_db=float(desired_gain_db(null_weights(steer(kD, f), steer(kJ, f))[0], steer(kD, f))
                                                 - desired_gain_db(w, steer(kD, f)))))
    return out


def failsafe(hop_rate=1000.0):
    fs = P.FAILSAFE
    T_hop = 1 / hop_rate
    logic = fs["watchdog_missed_hops"] * T_hop + fs["ss_switch_s"]
    power = fs["relay_switch_s"]
    worst = max(logic, power)
    return dict(hop_rate=hop_rate, logic_fault_ms=logic * 1e3, power_loss_ms=power * 1e3,
                hops_lost_logic=math.ceil(logic / T_hop), hops_lost_power=math.ceil(power / T_hop),
                worst_ms=worst * 1e3, drdo_budget_ms=P.DRDO["position_correction_s"] * 1e3,
                margin_vs_drdo=P.DRDO["position_correction_s"] / worst,
                margin_vs_autopilot=fs["autopilot_failsafe_s"] / worst,
                insertion_loss_db=fs["insertion_loss_db"],
                range_cost_pct=100 * (1 - 10 ** (-fs["insertion_loss_db"] / 20)))


def zeroize():
    z, f = P.ZEROIZE, P.FIISM
    words = f["n_subbands"] * f["entries_per_subband"] * f["bits_per_entry"] // z["word_bits"] + z["extra_words"]
    t = words / P.CLOCKS["asic_hz"]
    e_need = z["core_power_w"] * t
    e_cap = 0.5 * z["hold_up_uF"] * 1e-6 * (z["rail_v"] ** 2 - 2.5 ** 2)
    return dict(words=words, fiism_kbit=f["n_subbands"] * f["entries_per_subband"] * f["bits_per_entry"] / 1024,
                time_us=t * 1e6, energy_uJ=e_need * 1e6, holdup_uJ=e_cap * 1e6, margin=e_cap / e_need)


def summary(rejection_db=30.0):
    g_med, g_min = array_gain_after_null()
    lb = link_budget()
    jnr_with, jnr_without = max_jnr_db(rejection_db, g_med)
    return dict(link=lb, gain_after_null_db=dict(median=g_med, min=g_min), horizon_km=horizon_km(),
                design_rejection_db=rejection_db,
                range_divisor=10 ** ((rejection_db + g_med) / 20),
                power_multiplier_db=rejection_db + g_med,
                burn_through=burn_through_table(rejection_db, g_med),
                max_jnr_db=dict(with_hopnull=jnr_with, without=jnr_without),
                follower=follower(), follower_5k=follower(hop_rate=5000.0),
                gnss_denied=gnss_denied_desired_loss(),
                failsafe=failsafe(), failsafe_5k=failsafe(5000.0), zeroize=zeroize())
