"""
Array-geometry trade (why the design uses a planar Y, not a line or a square).

For each candidate 4-element geometry:
  * is the full 3-D direction observable?  (needed to store it in an earth frame)
  * what fraction of jammer azimuths passes the mainlobe gate (defended sector),
    worst case over GCS bearings, with GCS and jammer both near the horizon?
  * desired-signal gain kept after the null, and the 30 dB pointing tolerance.
"""
import numpy as np
from . import params as P
from .array import positions, positions_square, positions_ula, steer, unit
from .nuller import null_weights, mainlobe_gate, desired_gain_db

F = P.LINK["f_hz"]
LT = P.lam(P.ARRAY["f_design_hz"])


def el_for(range_m, alt=P.LINK["uav_alt_m"]):
    return -np.degrees(np.arctan2(alt, range_m))


def gated_deg(pos, gcs_az, jam_range=5_000.0, step=1.0):
    kD = unit(gcs_az, el_for(P.DRDO["link_range_m"]))
    aD = steer(kD, F, pos)
    n = 0
    for a in np.arange(0, 360, step):
        _, rho = null_weights(aD, steer(unit(a, el_for(jam_range)), F, pos))
        n += not mainlobe_gate(rho, 4)
    return n * step


def defended_pairs(pos=None, gcs_az=0.0, step=15, jam_range=5_000.0):
    """(kD, kJ) pairs on an azimuth grid that pass the mainlobe gate."""
    pos = positions() if pos is None else pos
    kD = unit(gcs_az, el_for(P.DRDO["link_range_m"]))
    out = []
    for a in np.arange(0, 360, step):
        kJ = unit(a, el_for(jam_range))
        _, rho = null_weights(steer(kD, F, pos), steer(kJ, F, pos))
        if mainlobe_gate(rho, 4):
            out.append((float(a), kD, kJ))
    return out


def compare():
    cands = [
        ("ULA, 4 x 0.5 lambda", positions_ula(0.5 * LT), False),
        ("Square 2x2, 0.5 lambda", positions_square(0.5 * LT), True),
        ("Square 2x2, 0.45 lambda", positions_square(0.45 * LT), True),
        ("Y (centre + 3), r = 0.45 lambda", positions(0.45 * LT), True),
    ]
    rows = []
    for name, pos, obs3d in cands:
        g = [gated_deg(pos, b) for b in range(0, 91, 15)]
        gains = [desired_gain_db(null_weights(steer(kD, F, pos), steer(kJ, F, pos))[0], steer(kD, F, pos))
                 for _, kD, kJ in defended_pairs(pos, step=5)]
        rows.append(dict(name=name, obs3d=obs3d, gated_min_deg=min(g), gated_max_deg=max(g),
                         defended_worst_pct=100 * (1 - max(g) / 360), defended_best_pct=100 * (1 - min(g) / 360),
                         gain_median_db=float(np.median(gains))))
    return rows


def random_defended(rng, pos=None):
    """Random (kD, kJ) with jammer range 1-20 km that passes the mainlobe gate."""
    pos = positions() if pos is None else pos
    kD = unit(0.0, el_for(P.DRDO["link_range_m"]))
    while True:
        kJ = unit(rng.uniform(0, 360), el_for(rng.uniform(1e3, 20e3)))
        if mainlobe_gate(null_weights(steer(kD, F, pos), steer(kJ, F, pos))[1], 4):
            return kD, kJ
