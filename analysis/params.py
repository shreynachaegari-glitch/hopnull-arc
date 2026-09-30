"""
Every assumption the analysis depends on, in one place.

Each value is either (a) a design decision of HOPNULL-ARC, (b) a stated
reference-scenario assumption, or (c) a published requirement.  Nothing in
the annexures should quote a number that does not trace back to this file or
to a computation on it (see run_all.py -> results.json).
"""
import math

C = 299_792_458.0  # m/s

# ---------------------------------------------------------------- array -----
# (a) Planar "Y" of lambda/4 monopole/blade elements on the belly ground plane:
#     centre reference element + 3 at 120 deg, radius r. A linear array only
#     observes a cone angle, which cannot be rotated into an earth frame; a planar
#     array observes both in-plane direction cosines and the ground plane resolves
#     the above/below mirror ambiguity. The Y beats a 2x2 square because a square
#     lattice aliases a near-horizon jammer behind the UAV onto a GCS ahead
#     (see geometry.py): Y gates 55/360 deg at every GCS bearing, square 67-120.
#     r = 0.45 lambda at the top of the band leaves an 18 deg no-wrap phase guard.
ARRAY = dict(
    M=4,
    f_design_hz=2.4835e9,
    r_frac=0.45,
    geometry="Y: centre + 3 at 120 deg, belly-mounted, x fwd / y right / z down (body FRD)",
)

# ---------------------------------------------------------- hop band -------
BAND_BENCH = dict(name="2.4 GHz ISM (bench, V1)", f_lo=2.400e9, f_hi=2.4835e9,
                  ch_bw_hz=1.0e6, n_channels=79)
BAND_TARGET = dict(name="S-band (DRDO TDF target)", f_lo=2.0e9, f_hi=4.0e9)

# ------------------------------------------------------- DRDO reference -----
# (c) DRDO TDF jam-proof swarm RFP (public reporting, 1 Aug 2026):
#     "five-kilometre jammer-proof communication link in the S-band, HF band or
#     C-band, equipped with ECCM features"; swarm position errors corrected
#     within ~500 ms.
DRDO = dict(link_range_m=5_000.0, position_correction_s=0.5)

# ---------------------------------------------------- reference link -------
# (b) Conservative C2 uplink budget at the bench frequency.
LINK = dict(
    f_hz=2.44e9,
    gcs_eirp_dbm=36.0,           # 1 W PA + 6 dBi GCS antenna
    uav_elem_gain_dbi=0.0,       # monopole/blade element toward the horizon
    noise_figure_db=4.0,
    fade_margin_db=10.0,         # airframe shadowing + multipath fade allowance
    sinr_req_db=10.0,            # coded GFSK/BPSK FH modem, per-hop
    uav_alt_m=500.0,
    jammer_mast_m=10.0,
)

# ---------------------------------------------------- platform / jammer ----
PLATFORM = dict(
    turn_rate_dps=20.0,          # coordinated turn used in the survival example
    max_body_rate_dps=60.0,      # small-UAV aggressive manoeuvre bound
    roll_rate_dps=45.0,          # bank-in / bank-out transient
    speed_mps=30.0,              # own-ship ground speed (parallax)
)
JAMMER = dict(speed_mps=30.0, ranges_m=[1_000, 2_000, 5_000, 10_000, 20_000])

# -------------------------------------------------------- IMU (MEMS) -------
IMU = dict(gyro_bias_dph=10.0,       # tactical/industrial MEMS bias instability
           timestamp_skew_s=100e-6,  # IMU <-> sample-index alignment
           attitude_err_deg=0.5)     # absolute AHRS attitude error

# ------------------------------------------------------- calibration -------
CAL = dict(
    phase_rms_deg_list=[0.25, 0.5, 1, 1.5, 2, 3, 4, 6],
    amp_rms_db_per_deg=0.05,     # amplitude error tied to phase error
    trials=4000,
)

# ------------------------------------------------------------ timing -------
# (b) Timing scenarios. G = modem retune guard; L_pre = strobe -> first new-hop
#     sample at the multipliers; L_total = RF-in -> RF-out latency.
FS_HZ = 10e6                     # complex baseband per channel after DDC
TIMING_SCENARIOS = [
    dict(name="Slow FH", hop_rate=200.0, G_s=50e-6),
    dict(name="Design point", hop_rate=1000.0, G_s=20e-6),
    dict(name="Fast FH", hop_rate=5000.0, G_s=10e-6),
]
PIPE = dict(
    L_pre_s=1.2e-6,              # ADC + DDC decimation group delay
    L_total_s=3.0e-6,            # ADC/DDC + beamformer + DUC/DAC
    T_flush_s=1.0e-6,            # mute = DDC/DUC FIR flush
    settle_nco_s=0.1e-6,         # fixed-LO wideband front end, digital NCO retune
    settle_pll_s=40e-6,          # analog LO relock (fast-lock class), if used
)
CLOCKS = dict(fpga_hz=100e6, asic_hz=50e6)   # Zynq-7000 fabric / SCL 180 nm
HW = dict(mults=4, cordic_iter=16, cordic_latency=18, sqrt_latency=18,
          overhead_per_stage=8, derate=2.0)   # derate: RTL-vs-estimate margin
OBS = dict(K=256)                 # snapshots per observation window

# --------------------------------------------------------- Case B ----------
CASEB = dict(
    clock_ppm_modem=20.0, clock_ppm_accel=20.0,
    transition_detect_s=1.0e-6,   # hop-edge timing resolution after averaging
    fft_n=64,                     # channelizer bins used to identify the hop
    fs_wide_hz=100e6,             # wideband capture for Case B (Tier-2 analysis)
    n_subbands=8,
)

# ------------------------------------------------------ fail-safe ----------
FAILSAFE = dict(
    watchdog_missed_hops=3,       # heartbeat = one per committed hop
    ss_switch_s=1e-6,             # solid-state SPDT, powered from board rail
    relay_switch_s=15e-3,         # fail-safe (normally-closed) coaxial relay
    autopilot_failsafe_s=1.5,     # typical short-failsafe timeout
    insertion_loss_db=0.6,        # relay + SPDT in the bypass path
)

# ------------------------------------------------------ security -----------
FIISM = dict(n_subbands=32, entries_per_subband=2, bits_per_entry=128)
ZEROIZE = dict(word_bits=128, extra_words=16, hold_up_uF=10.0, rail_v=3.3,
               core_power_w=0.1)


def lam(f_hz):
    return C / f_hz


def spacing_m():
    """Centre-to-outer radius r (the only baselines used for phase-gradient DoA)."""
    return ARRAY["r_frac"] * lam(ARRAY["f_design_hz"])


def db(x):
    return 10.0 * math.log10(x)
