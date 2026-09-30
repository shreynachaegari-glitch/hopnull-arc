"""
Data figures for the annexures, drawn from analysis/results.json.
Vector SVG with live text (svg.fonttype none, Liberation Sans = Arial metrics) so the
PDF stays small and sharp; build_all.sh rasterises a PNG fallback for older Word.
Palette: validated categorical slots (blue, orange, aqua, violet), text in ink tokens.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import survival

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
R = json.loads((ROOT / "analysis" / "results.json").read_text())

BLUE, ORANGE, AQUA, VIOLET = "#000000", "#000000", "#666666", "#666666"
INK, INK2, MUTED, GRID = "#1b1b1b", "#52514e", "#8a8984", "#e4e3df"
NEUTRAL = "#cccccc"

plt.rcParams.update({
    "svg.fonttype": "none", "font.family": "Liberation Sans", "font.size": 7.5,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "axes.linewidth": 0.6,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.minor.size": 1.5, "ytick.minor.size": 1.5,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "grid.linestyle": "-",
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "lines.linewidth": 1.4, "lines.solid_capstyle": "round", "axes.titlesize": 8,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def save(fig, name):
    fig.savefig(ASSETS / f"{name}.svg", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def fig_survival_calibration():
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.6, 2.45), gridspec_kw=dict(width_ratios=[1.35, 1]))
    t = np.logspace(-3, np.log10(8), 400)
    az = 60.0
    series = [
        ("Body-frame hold, 60°/s", survival.body_hold_timeseries(t, 60, jam_az=az), ORANGE, (0, (4, 2))),
        ("Body-frame hold, 20°/s", survival.body_hold_timeseries(t, 20, jam_az=az), ORANGE, "-"),
        ("Earth-frame, jammer 1 km", survival.earth_state_timeseries(t, 20, jam_az=az, jam_range=1_000), AQUA, (0, (1, 1))),
        ("Earth-frame, jammer 5 km", survival.earth_state_timeseries(t, 20, jam_az=az, jam_range=5_000), BLUE, "-"),
    ]
    for label, y, c, ls in series:
        tc = survival.crossing_time(t, y)
        keep = t <= 2.5 * tc          # past the crossing the turn has changed the geometry; not informative
        ax.plot(t[keep] * 1e3, np.clip(y[keep], 0, 80), color=c, ls=ls, label=label)
        if np.isfinite(tc):
            ax.plot([tc * 1e3], [30], "o", ms=4, color=c, mec="white", mew=1.2, zorder=5)
            ax.annotate(f"{tc*1e3:.0f} ms" if tc < 1 else f"{tc:.2f} s", (tc * 1e3, 30),
                        xytext=(0, -11), textcoords="offset points", ha="center", color=INK2, fontsize=6.8)
    ax.axhline(30, color=INK2, lw=0.7)
    ax.text(1.1, 25.0, "30 dB design\nrejection", color=INK2, fontsize=6.5, va="top")
    ax.set_xscale("log")
    ax.set_xlim(1, 5000); ax.set_ylim(0, 80)
    ax.set_xlabel("time since last observation (ms)")
    ax.set_ylabel("jammer rejection (dB)")
    ax.set_title("(a) Null survival under a turn, no refresh")
    ax.legend(loc="upper right", fontsize=6.5, handlelength=2.2)

    rows = R["calibration"]["cal"]
    x = [r["phase_rms_deg"] for r in rows]
    bx.plot(x, [r["median_db"] for r in rows], color=BLUE, marker="o", ms=3.5, mec="white", mew=0.8, label="median")
    bx.plot(x, [r["p10_db"] for r in rows], color=VIOLET, ls="--", marker="s", ms=3.5, mec="white", mew=0.8, label="worst 10%")
    bx.axhline(30, color=INK2, lw=0.7)
    spec = R["calibration"]["phase_budget_30db_p10_deg"]
    bx.axvline(spec, color=INK2, lw=0.7)
    bx.text(spec + 0.12, 44, f"spec ≤ {spec:g}° RMS\n(thermal/vibration\npass criterion)", color=INK2, fontsize=6.5, va="top")
    bx.set_xlabel("residual channel phase error (° RMS)")
    bx.set_ylabel("jammer rejection (dB)")
    bx.set_title("(b) Calibration-limited rejection")
    bx.set_ylim(10, 50); bx.set_xlim(0, 6.2)
    bx.legend(loc="upper right", fontsize=6.5)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig3_survival_calibration")


def fig_survivability_latency():
    sb = R["survivability"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.6, 2.75), gridspec_kw=dict(width_ratios=[1.15, 1]))
    rows = sb["burn_through"]
    eirp = np.linspace(30, 60, 61)
    from .survivability import denial_range_km
    g = sb["gain_after_null_db"]["median"]
    rej = sb["design_rejection_db"]
    hz = sb["horizon_km"]
    curves = [
        ("Spot / follower, unprotected", [min(denial_range_km(e), hz) for e in eirp], ORANGE, "-"),
        ("Barrage, unprotected (FHSS gain)", [min(denial_range_km(e, barrage=True), hz) for e in eirp], ORANGE, (0, (4, 2))),
        ("Spot / follower, HOPNULL-ARC", [denial_range_km(e, rej, g) for e in eirp], BLUE, "-"),
        ("Barrage, HOPNULL-ARC", [denial_range_km(e, rej, g, barrage=True) for e in eirp], BLUE, (0, (4, 2))),
    ]
    for label, y, c, ls in curves:
        ax.plot(eirp, y, color=c, ls=ls, label=label)
    ax.axhline(R["params"]["drdo"]["link_range_m"] / 1e3, color=INK2, lw=0.7)
    ax.text(30.5, 5.8, "DRDO 5 km link", color=INK2, fontsize=6.5)
    ax.text(59.5, hz * 1.25, f"radio horizon {hz:.0f} km", color=INK2, fontsize=6.5, ha="right")
    ten = [r for r in rows if r["w_eirp"] == 10][0]
    ax.plot([40, 40], [ten["spot_null_km"], ten["spot_no_null_km"]], color=INK2, lw=0.7)
    ax.plot([40], [ten["spot_null_km"]], "o", ms=3.5, color=BLUE, mec="white", mew=0.8, zorder=5)
    ax.plot([40], [ten["spot_no_null_km"]], "o", ms=3.5, color=ORANGE, mec="white", mew=0.8, zorder=5)
    ax.text(40.7, 0.55, f"10 W spot jammer:\n{ten['spot_no_null_km']:.0f} km → {ten['spot_null_km']:.1f} km", color=INK, fontsize=6.6, va="center")
    ax.set_yscale("log"); ax.set_ylim(0.03, 200); ax.set_xlim(30, 60)
    ax.set_xlabel("jammer EIRP (dBm)")
    ax.set_ylabel("denial range (km)")
    ax.set_title(f"(a) Jammer must close in {sb['range_divisor']:.0f}× nearer")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=6.2, handlelength=2.2,
              columnspacing=1.0)

    lat = R["latency"]["margins_asic"]
    names = [f"{m['hop_rate']:.0f} hop/s" for m in lat]
    segs = [("guard G", "G_us", "#e6e6e6"), ("observe T_obs", "T_obs_us", "#999999"), ("compute B1-B3 (×2 derated)", "T_B_us", "#000000")]
    y = np.arange(len(lat))[::-1]
    for i, m in enumerate(lat):
        left = 0.0
        tot = m["T_hop_us"]
        for label, key, c in segs:
            wdt = 100 * m[key] / tot
            bx.barh(y[i], wdt, left=left, height=0.46, color=c, edgecolor="white", linewidth=1.0,
                    label=label if i == 0 else None)
            left += wdt
        bx.text(left + 1.5, y[i], f"{100*m['T1_util']:.0f}% used", va="center", color=INK, fontsize=6.8)
    bx.set_yticks(y); bx.set_yticklabels(names)
    bx.set_xlim(0, 100); bx.set_xlabel("share of hop dwell (%)")
    bx.set_title("(b) TC1 budget, SCL 180 nm @ 50 MHz")
    bx.grid(axis="y", visible=False)
    bx.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=6.2, columnspacing=1.0)
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig4_survivability_latency")


def main():
    ASSETS.mkdir(exist_ok=True)
    fig_survival_calibration()
    fig_survivability_latency()
    print("plots written")


if __name__ == "__main__":
    main()
