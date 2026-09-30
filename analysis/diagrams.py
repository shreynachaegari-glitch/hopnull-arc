"""
Hand-laid vector diagrams (SVG, live text) for the annexures:
  fig1_architecture.svg   upgraded system architecture, tier-tagged (landscape)
  fig2_timing.svg         hop timing with the computed budget numbers
  fig5_states.svg         safety / security state machine with transition times
  fig0_gantt.svg          18-month plan with Tier-2 milestones (Annexure-1)
Numbers are read from analysis/results.json so the drawings never drift from the analysis.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
R = json.loads((ROOT / "analysis" / "results.json").read_text())
FONT = "Liberation Sans, Arial, Helvetica, sans-serif"

NAVY, INK, INK2, MUTED = "#000000", "#000000", "#333333", "#666666"
STYLE = {
    #          stroke     fill       chip-fill  chip-text  dash
    "core":  ("#000000", "#FFFFFF", "#000000", "#FFFFFF", None),
    "input": ("#000000", "#FFFFFF", "#000000", "#FFFFFF", None),
    "t1":    ("#000000", "#FFFFFF", "#000000", "#FFFFFF", None),
    "t2":    ("#000000", "#FFFFFF", "#000000", "#FFFFFF", "4 3"),
    "t3":    ("#000000", "#FFFFFF", "#000000", "#FFFFFF", "5 4"),
    "t4":    ("#000000", "#FFFFFF", "#000000", "#FFFFFF", "2 3"),
    "board": ("#000000", "#FFFFFF", "#000000", "#FFFFFF", "8 5"),
}
SAFETY = "#000000"


class SVG:
    def __init__(self, w, h):
        self.w, self.h, self.els = w, h, []
        self.defs = []
        for name, col in (("nav", NAVY), ("teal", "#000000"), ("amb", "#000000"), ("red", SAFETY), ("grey", MUTED)):
            self.defs.append(
                f'<marker id="a-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')

    def rect(self, x, y, w, h, stroke, fill, sw=1.6, rx=8, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.els.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=13.5, weight="normal", fill=INK, anchor="start", italic=False, spacing=None):
        st = ' font-style="italic"' if italic else ""
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        body = escape(s)
        if "^{" in s:                       # ^{H} -> raised small text (dy is widely supported)
            parts, out = s.split("^{"), [escape(s.split("^{")[0])]
            dy = round(size * 0.38, 1)
            for p in parts[1:]:
                sup, rest = p.split("}", 1)
                out.append(f'<tspan dy="-{dy}" font-size="{round(size * 0.72, 1)}">{escape(sup)}</tspan>'
                           f'<tspan dy="{dy}">{escape(rest)}</tspan>')
            body = "".join(out)
        self.els.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
                        f'fill="{fill}" text-anchor="{anchor}"{st}{ls}>{body}</text>')

    def line(self, pts, col=NAVY, sw=2.0, dash=None, head="nav", tail=None):
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        me = f' marker-end="url(#a-{head})"' if head else ""
        ms = f' marker-start="url(#a-{tail})"' if tail else ""
        self.els.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{sw}"{da}{me}{ms} stroke-linejoin="round"/>')

    def circle(self, x, y, r, fill, stroke="none", sw=0):
        self.els.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def raw(self, s):
        self.els.append(s)

    def write(self, name):
        body = "\n".join(self.els)
        s = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
             f'viewBox="0 0 {self.w} {self.h}"><defs>{"".join(self.defs)}</defs>'
             f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#FFFFFF"/>\n{body}\n</svg>\n')
        (ASSETS / f"{name}.svg").write_text(s)


def chip(g, x, y, label, style, size=11):
    stroke, _, cf, ct, _ = STYLE[style]
    w = 9 + 7.2 * len(label) * size / 11
    g.rect(x, y - size - 1, w, size + 6, cf, cf, sw=0, rx=4)
    g.text(x + w / 2, y + 0.5, label, size=size, weight="bold", fill=ct, anchor="middle")
    return w


def box(g, x, y, w, h, title, kicker=None, lines=(), style="core", tsize=17, lsize=13.2, step=17.5, tag=None):
    stroke, fill, _, _, dash = STYLE[style]
    g.rect(x, y, w, h, stroke, fill, sw=1.8 if style in ("core", "board") else 1.5, dash=dash)
    tx = x + 12
    if tag:
        tx += chip(g, x + 11, y + 25, tag, style) + 6
    g.text(tx, y + 25, title, size=tsize, weight="bold", fill=NAVY if style in ("core", "input", "board") else STYLE[style][0])
    yy = y + 25
    if kicker:
        g.text(x + 12, y + 43, kicker, size=11.2, fill=MUTED, spacing="0.4")
        yy = y + 43
    yy += step + 2
    for ln in lines:
        g.text(x + 12, yy, ln, size=lsize, fill=INK)
        yy += step
    return yy


def subbox(g, x, y, w, rows, style, lsize=12.2, step=15.5):
    """Tier-tagged sub-panel at the bottom of a block: rows = [(tag, text), ...] or text lines."""
    stroke, fill, _, _, dash = STYLE[style]
    h = 10 + step * len(rows)
    g.rect(x, y, w, h, stroke, fill, sw=1.1, rx=5, dash=dash)
    yy = y + step
    for r in rows:
        if isinstance(r, tuple):
            cw = chip(g, x + 7, yy, r[0], r[0].lower() if r[0] in ("T1", "T2", "T3") else style, size=10)
            g.text(x + 12 + cw, yy, r[1], size=lsize, fill=INK)
        else:
            g.text(x + 12, yy, r, size=lsize, fill=INK)
        yy += step
    return y + h


# ======================================================================= FIG 1
def fig_architecture():
    lat, sb, sv = R["latency"], R["survivability"], R["survival"]
    fs = sb["failsafe"]
    g = SVG(1400, 900)
    g.text(24, 38, "HOPNULL-ARC  |  System Architecture — upgraded baseline", size=25, weight="bold", fill=NAVY)
    g.text(24, 60, "Direction-state nulling on a Y array · single hardware commit authority · two-tier board fail-safe · "
                   "security & tamper domain · every tag says when it ships", size=13, fill=MUTED)
    # tier legend
    lx = 915
    for lab, st, txt in (("V1", "core", "core"), ("T1", "t1", "hardening, in baseline"),
                         ("T2", "t2", "in-project milestone"), ("T3", "t3", "future work")):
        pass
    items = [("V1", "core", "core"), ("T1", "t1", "hardening (in V1)"), ("T2", "t2", "in-project"), ("T3", "t3", "future")]
    lx = 868
    for lab, st, txt in items:
        cw = chip(g, lx, 44, lab, st, size=11)
        g.text(lx + cw + 5, 44, txt, size=12, fill=INK2)
        lx += cw + 12 + 6.6 * len(txt)

    # ---- digital-core boundary
    g.rect(236, 176, 928, 530, NAVY, "none", sw=1.2, rx=10, dash="3 4")
    g.text(252, 688, "HOPNULL-ARC digital core — FPGA prototype → SCL 180 nm (C2S)", size=12.5, weight="bold", fill=NAVY)

    # ---- top row: antenna, IMU, navigation, Case B, modem
    # Y-array icon
    g.rect(20, 86, 200, 76, NAVY, "#F2F2F2", sw=1.5)
    cx, cy, rr = 62, 124, 22
    import math
    for a in (0, 120, 240):
        ex, ey = cx + rr * math.cos(math.radians(a - 90)), cy + rr * math.sin(math.radians(a - 90))
        g.line([(cx, cy), (ex, ey)], col=MUTED, sw=1.2, head=None)
        g.circle(ex, ey, 5.5, NAVY)
    g.circle(cx, cy, 5.5, "#000000")
    g.text(96, 110, "Y array (belly)", size=13.5, weight="bold", fill=NAVY)
    g.text(96, 128, "centre + 3 @ 120°", size=12, fill=INK)
    g.text(96, 144, f"r = 0.45λ = {R['params']['r_mm']:.0f} mm", size=12, fill=INK)
    g.text(96, 157, "centre = bypass ref.", size=11, fill=MUTED)

    box(g, 250, 86, 200, 76, "IMU / AHRS", "ATTITUDE q · RATE ω",
        ["GNSS-free · skew ≤ 100 µs"], style="input", tsize=15.5, lsize=12.2)
    gd = [x for x in sb["gnss_denied"] if x["err_deg"] == 20][0]["loss_db"]
    box(g, 470, 86, 215, 76, "Navigation", "GCS DIRECTION a_D",
        [f"20° error → {gd:.1f} dB loss"], style="input", tsize=15.5, lsize=12.2)
    cb = [c for c in lat["case_b"] if c["hop_rate"] == 1000][0]
    box(g, 725, 86, 240, 76, "Case B: no sideband", None,
        [f"channelizer + dwell timer", f"coast {cb['n_coast_hops']} hops · {100*cb['unprotected_frac']:.1f}% dwell exposed"],
        style="t2", tsize=15.5, lsize=12.2, step=16, tag="T2")
    box(g, 1130, 86, 250, 76, "FH modem sideband (Case A)", None,
        ["HOP_STROBE · NEXT_FREQ ≥ 1 hop", "TX_ACTIVE (blank on transmit)"], style="input", tsize=15, lsize=12.2, step=15.5)

    # ---- main pipeline row
    Y0, H = 192, 282
    # RF front end (board)
    box(g, 20, Y0, 200, H, "RF front end", "PROTECT · CONDITION",
        ["4 coherent RX, one LO", "+ one sample clock", "fixed LO, wideband ADC,", "per-hop digital NCO", "(PLL relock > guard G)",
         "common AGC", "per-channel clip counters"], style="board", lsize=12.6, step=17)
    subbox(g, 28, Y0 + H - 42, 184, [("T2", "adaptive AGC loop")], "t2")

    b1 = box(g, 250, Y0, 210, H, "B1 Observation", "OBSERVE",
             [f"late window K={R['params']['K']} ({R['calibration']['T_obs_us']:.1f} µs)", "3 centre-arm correlators",
              "2-D phase-gradient DoA", "gates: coherence, closure,", "presence, mainlobe (≤3 dB)",
              "body → earth frame (IMU)", "FIISM ← dir + σ + tilt"], lsize=12.6, step=17)
    box(g, 485, Y0, 235, H, "B2 Candidate", "SYNTHESIZE",
        ["earth → body, predicted q(n+1)", "CORDIC steering at f(n+1)", "w = M·a_D − ρ·a_J (closed form)",
         f"CLZ + 16-LUT (≤{lat['gain_step_db']['lut3']:.1f} dB step)", "self-check: |a| = 1,",
         f"null ≤ {R['fixed_point']['threshold_db']:.0f} dB → transaction"], lsize=12.6, step=17)
    subbox(g, 493, Y0 + H - 74, 219, [("T2", "V2: 2 jammers, 4×4 Cholesky"),
                                      "model R at f(n+1), per hop;", "EVD + grid MUSIC in background"], "t2", step=15)
    box(g, 745, Y0, 225, H, "B3 Transaction mgr", "FIISM · COMMIT · RETAIN",
        ["FRESH → FIISM → BYPASS", "freq-tag invariant", "TRUST_CUT watermark", "TILT_MAX re-observe rule",
         "sample-index commit,", "mute inside guard G"], lsize=12.6, step=17)
    subbox(g, 753, Y0 + H - 74, 209, [("T1", "FIISM ECC + zeroize"), ("T2", "Case-B dwell arbitration"),
                                      ("T3", "lockstep commit logic")], "t1", step=15)
    # re-colour the T2/T3 rows' chips are drawn in their own style by chip(); fine
    box(g, 995, Y0, 160, H, "B4 Beamformer", "APPLY",
        ["y = w^{H}x, 4 cMACs", "mode-blind", "double-buffered", "CRC check at swap", "saturation", "telemetry", "→ DUC / DAC"],
        lsize=12.6, step=17)
    box(g, 1180, Y0, 200, H, "Board fail-safe", "INDEPENDENT SAFETY PATH",
        ["watchdog: 3 missed", f"heartbeats → SPDT 1 µs", "NC coax relay:", f"power loss → ≤{fs['power_loss_ms']:.0f} ms",
         "centre element", "→ modem direct"], style="board", lsize=12.6, step=17)
    subbox(g, 1188, Y0 + H - 42, 184, [("T1", "TAMPER_N forces bypass")], "t1")

    # ---- signal arrows
    ym = Y0 + 118
    for x1, x2 in ((220, 250), (460, 485), (720, 745), (970, 995), (1155, 1180)):
        g.line([(x1, ym), (x2 - 2, ym)], sw=2.4)
    g.line([(120, 162), (120, Y0 - 2)], sw=2.2)                               # antenna -> RF
    g.line([(350, 162), (350, Y0 - 2)], sw=2.0)                               # IMU -> B1
    g.line([(430, 162), (430, 172), (540, 172), (540, Y0 - 2)], sw=2.0)       # IMU -> B2
    g.line([(600, 162), (600, Y0 - 2)], sw=2.0)                               # nav -> B2
    g.line([(845, 162), (845, Y0 - 2)], col="#000000", sw=1.8, dash="6 4", head="amb")   # case B -> B3
    g.line([(1130, 112), (982, 112), (982, 212), (972, 212)], col=NAVY, sw=1.8, dash="6 4")  # sideband -> B3
    g.line([(1280, Y0), (1280, 164)], sw=2.2, tail=None)                      # fail-safe -> modem RF
    g.text(1288, 180, "RF out", size=11, fill=MUTED)
    g.text(990, 106, "sideband", size=11, fill=MUTED)
    # AGC feedback (T2)
    g.line([(250, Y0 + H - 25), (222, Y0 + H - 25)], col="#000000", sw=1.8, dash="5 3", head="amb")

    # ---- row 3
    Y3 = 500
    box(g, 250, Y3, 290, 150, "Control plane — Ibex RV32", "ADVISORY ONLY · NO COMMIT AUTHORITY",
        ["kinematic classifier → MAX_AGE_eff", "configuration + telemetry (AXI-Lite)", "write-once safety locks",
         "debug module off in mission mode"], style="input", tsize=15.5, lsize=12.6, step=17)
    box(g, 560, Y3, 225, 150, "Safety bounds", "HARDWIRED / OTP",
        ["MAX_AGE_MIN / MAX", "TILT_MAX · HOP_MIN / MAX", "gate thresholds", f"NULL_CHECK {R['fixed_point']['threshold_db']:.0f} dB"],
        style="input", tsize=15.5, lsize=12.6, step=17)
    z = sb["zeroize"]
    box(g, 805, Y3, 350, 190, "Security & tamper domain", None,
        ["TAP / JTAG, boundary scan, Ibex debug:", "  gated by OTP mission lock", "scan / test-mode entry ⇒ zeroize first",
         "secure boot: authenticated bitstream + FW", "tamper: lid switches + light sensor + potting", f"  → TAMPER_N → zeroize ({z['time_us']:.1f} µs) + bypass",
         "SEU: parity/ECC, config scrub, bundle CRC"], style="t1", tsize=15.5, lsize=12.4, step=16.5, tag="T1")
    box(g, 20, Y3, 200, 190, "Environment", "SCREENING TEST PLAN", ["JSS 55555 / MIL-STD-810H", "thermal · vibration · shock",
        f"pass: cal drift ≤ {R['calibration']['phase_budget_30db_p10_deg']:g}° RMS", "(= 30 dB on 90% of", "geometries), array + RF"],
        style="t1", tsize=15.5, lsize=12.4, step=16.5, tag="T1")
    g.line([(120, Y3), (120, Y0 + H + 2)], col="#000000", sw=1.6, dash="2 3", head="teal")
    # control-plane arrows
    g.line([(470, Y3), (470, Y0 + H + 2)], col=NAVY, sw=1.8, dash="6 4")      # Ibex -> B1/B2 (advisory)
    g.text(478, Y3 - 10, "advisory", size=11, fill=MUTED)
    g.line([(672, Y3), (672, 486), (800, 486), (800, Y0 + H + 2)], col=NAVY, sw=2.0)  # OTP -> B3 hard limits
    g.text(664, 496, "hard limits", size=11, fill=MUTED, anchor="end")
    # safety / tamper paths
    g.line([(930, Y3), (930, Y0 + H + 2)], col=SAFETY, sw=1.8, dash="2 3", head="red")        # zeroize B3
    g.text(922, Y3 - 10, "zeroize", size=11, fill=SAFETY, anchor="end")
    g.line([(1155, 600), (1300, 600), (1300, Y0 + H + 2)], col=SAFETY, sw=1.8, dash="2 3", head="red")  # tamper -> board
    g.text(1163, 592, "force bypass", size=11, fill=SAFETY)
    g.line([(955, Y0 + H), (955, 488), (1240, 488), (1240, Y0 + H + 2)], col=SAFETY, sw=1.6, head="red")  # heartbeat
    g.text(1010, 482, "heartbeat, one per commit", size=11, fill=SAFETY)

    # ---- bottom strips: T3 future, T4 non-goals
    Y4 = 716
    g.rect(20, Y4, 765, 104, STYLE["t3"][0], STYLE["t3"][1], sw=1.4, dash="5 4")
    cw = chip(g, 32, Y4 + 26, "T3", "t3")
    g.text(38 + cw, Y4 + 26, "Future work — named, not built in this proposal", size=15, weight="bold", fill=STYLE["t3"][0])
    for i, s in enumerate(["• dual-redundant / lockstep B3 commit logic", "• direction-dependent calibration table (F11)",
                           "• more than 2 simultaneous jammers", "• RF-over-fibre ground-station mast (separate variant)",
                           "• active tamper-detect mesh (production)", "• 3-D (non-coplanar) element placement"]):
        g.text(34 + (i % 2) * 380, Y4 + 50 + (i // 2) * 18, s, size=12.6, fill=INK)
    g.rect(805, Y4, 575, 104, STYLE["t4"][0], "#FFFFFF", sw=1.4, dash="2 3")
    cw = chip(g, 817, Y4 + 26, "T4", "t4")
    g.text(823 + cw, Y4 + 26, "Stated non-goals — deliberate, with rationale", size=15, weight="bold", fill=STYLE["t4"][0])
    for i, s in enumerate(["• N-modular redundancy", "• EMP / HEMP and total-dose hardening",
                           "• power / EM side-channel resistance", "• kinetic / ballistic hardening"]):
        g.text(819 + (i % 2) * 270, Y4 + 50 + (i // 2) * 18, s, size=12.6, fill=INK)
    g.text(819, Y4 + 92, "Cost unjustified at TRL 2→5, or outside the threat model (see §5).", size=11.5, fill=MUTED, italic=True)

    # ---- line legend
    Y5 = 862
    x = 24
    for col, dash, head, lab in ((NAVY, None, "nav", "sample / signal path"), (NAVY, "6 4", "nav", "control / transaction"),
                                 (SAFETY, "2 3", "red", "safety / tamper action"), ("#000000", "5 3", "amb", "Tier-2 addition")):
        g.line([(x, Y5), (x + 44, Y5)], col=col, sw=2.0, dash=dash, head=head)
        g.text(x + 52, Y5 + 4, lab, size=12, fill=INK2)
        x += 70 + 7.0 * len(lab)
    g.rect(x + 6, Y5 - 9, 22, 18, NAVY, "#F2F2F2", sw=1.4, rx=4, dash="8 5")
    g.text(x + 36, Y5 + 4, "board-level (outside the chip's failure domain)", size=12, fill=INK2)
    g.write("fig1_architecture")


# ======================================================================= FIG 2
# Portrait figures are drawn on a 960-unit canvas and placed 6.55 in wide, so 14 units
# print at ~6.9 pt and 15 units at ~7.4 pt.
def fig_timing():
    m = [x for x in R["latency"]["margins_asic"] if x["hop_rate"] == 1000][0]
    p = R["params"]["pipe"]
    bg = R["latency"]["v2_background_asic"]
    v2 = [x for x in R["latency"]["margins_asic_v2"] if x["hop_rate"] == 1000][0]
    g = SVG(960, 486)
    lanes = ["Modem", "Front end", "Observe", "Compute", "V2 (T2)", "Weights", "Output", "Heartbeat"]
    x0, x1 = 150, 950
    bn, bn1, Gw = 175, 735, 26
    ys = [34 + 52 * i for i in range(len(lanes))]
    FS, FA = 15, 14
    for y, lab in zip(ys, lanes):
        g.text(8, y + 27, lab, size=FS, weight="bold", fill=NAVY)
        g.line([(x0, y + 46), (x1, y + 46)], col="#ECEBE7", sw=1, head=None)
    for bx, lab in ((bn, "B(n)"), (bn1, "B(n+1)")):
        g.line([(bx, 22), (bx, 452)], col=MUTED, sw=1.2, dash="4 4", head=None)
        g.text(bx, 17, lab, size=FA, fill=INK2, anchor="middle")
    H = 32
    def bar(xa, xb, y, stroke=NAVY, fill="#FFFFFF", dash=None, sw=1.2):
        g.rect(xa, y + 8, xb - xa, H, stroke, fill, sw=sw, rx=2, dash=dash)
    # modem
    y = ys[0]
    for bx in (bn, bn1):
        bar(bx, bx + Gw, y, MUTED, "#E3E2DE", sw=1)
        g.text(bx + Gw / 2, y + 29, "G", size=FS, weight="bold", fill=INK, anchor="middle")
    bar(bn + Gw, bn1, y)
    g.text((bn + bn1) / 2, y + 29, f"hop n at f(n): T_hop {m['T_hop_us']:.0f} µs, guard G {m['G_us']:.0f} µs", size=FA, fill=INK, anchor="middle")
    bar(bn1 + Gw, x1, y)
    g.text(bn1 + Gw + 8, y + 29, "hop n+1 at f(n+1)", size=FA, fill=INK)
    # front end
    y = ys[1]
    for bx in (bn, bn1):
        bar(bx, bx + 7, y, "#000000", "#F2F2F2", sw=1)
    g.text(bn + 16, y + 29, f"digital NCO retune {p['settle_nco_s']*1e6:.1f} µs (an analog PLL, {p['settle_pll_s']*1e6:.0f} µs, would overrun G)", size=FA, fill=INK2)
    # observe (late window)
    y = ys[2]
    comp_end = bn1 - 14
    comp_start = comp_end - 118
    obs_end, obs_start = comp_start - 5, comp_start - 5 - 150
    bar(obs_start, obs_end, y, NAVY, "#F2F2F2")
    g.text((obs_start + obs_end) / 2, y + 29, f"K={R['params']['K']}, {m['T_obs_us']:.1f} µs", size=FA, fill=INK, anchor="middle")
    g.text(obs_start - 8, y + 29, "late window: catches followers", size=FA, fill=INK2, anchor="end")
    # compute
    y = ys[3]
    xx = comp_start
    for lab, fr in zip(("B1", "B2", "B3"), (0.36, 0.44, 0.20)):
        bar(xx, xx + 118 * fr, y)
        g.text(xx + 59 * fr, y + 29, lab, size=FA, weight="bold", fill=NAVY, anchor="middle")
        xx += 118 * fr
    g.text(comp_start - 8, y + 29, f"{m['T_B_us']:.1f} µs worst case (×2 derated, 50 MHz)", size=FA, fill=INK2, anchor="end")
    bar(comp_end, bn1 + 8, y, MUTED, "#F4F4F2", dash="3 3", sw=1)
    g.text(bn1 + 14, y + 29, f"TC1 slack {m['T1_slack_us']:.0f} µs ({100*m['T1_util']:.0f}% used)", size=FA, fill=INK2)
    # V2
    y = ys[4]
    bar(comp_end - 30, comp_end, y, "#000000", "#F2F2F2")
    g.text(comp_end - 38, y + 29, f"per hop: Cholesky +{v2['T_B_us'] - m['T_B_us']:.1f} µs", size=FA, fill="#000000", anchor="end")
    bar(bn + 14, bn + 300, y, "#000000", "#F2F2F2", dash="4 3", sw=1)
    g.text(bn + 24, y + 29, f"background EVD + MUSIC {bg['time_us']:.0f} µs", size=FA, fill="#000000")
    # weights
    y = ys[5]
    swap = bn1 + 10
    bar(bn + 6, swap, y)
    g.text((bn + swap) / 2, y + 29, "hop n weights (buffer A)", size=FA, fill=INK, anchor="middle")
    bar(swap, x1, y)
    g.text(swap + 8, y + 29, "buffer B, swap at +" + f"{p['L_pre_s']*1e6:.1f} µs", size=FA, fill=INK)
    g.line([(swap, ys[3] + 44), (swap, y + 44)], col=NAVY, sw=2.4, head=None)
    # output
    y = ys[6]
    mute_x = bn1 + 14
    bar(bn + 10, mute_x, y)
    g.text(bn + 20, y + 29, "hop n signal", size=FA, fill=INK)
    g.rect(mute_x, y + 8, 12, H, SAFETY, "#D9D9D9", sw=1, rx=1)
    bar(mute_x + 12, x1, y)
    g.text(mute_x + 20, y + 29, "hop n+1 signal", size=FA, fill=INK)
    g.text(mute_x - 8, y + 29, f"mute {p['L_total_s']*1e6:.0f}+{p['T_flush_s']*1e6:.0f} µs inside G (TC2 slack {m['T2_slack_us']:.0f} µs) →", size=FA, fill=SAFETY, anchor="end")
    # heartbeat
    y = ys[7]
    for bx in (bn + 8, bn1 + 10):
        g.line([(bx, y + 40), (bx, y + 12)], col=SAFETY, sw=2.0, head="red")
    g.text(bn + 22, y + 32, f"one per commit; {R['params']['failsafe']['watchdog_missed_hops']} missed → board bypass "
                            f"({R['survivability']['failsafe']['logic_fault_ms']:.1f} ms at 1 kHz)", size=FA, fill=SAFETY)
    g.text(x1, 478, "not to scale · 1,000 hop/s design point · SCL 180 nm @ 50 MHz", size=13, fill=MUTED, anchor="end", italic=True)
    g.write("fig2_timing")


# ======================================================================= FIG 5
def fig_states():
    sb = R["survivability"]
    fs, z = sb["failsafe"], sb["zeroize"]
    g = SVG(960, 452)
    TS, SS = 16, 14

    def state(x, y, w, h, title, sub, style, tcol=NAVY):
        stroke, fill, _, _, dash = STYLE[style]
        g.rect(x, y, w, h, stroke, fill, sw=2.0, rx=12, dash=dash)
        g.text(x + w / 2, y + 27, title, size=TS, weight="bold", fill=tcol, anchor="middle")
        for i, s_ in enumerate(sub):
            g.text(x + w / 2, y + 49 + 17 * i, s_, size=SS, fill=INK2, anchor="middle")

    Y, Hs, Ws = 14, 92, 190
    xs = [10, 262, 514, 760]
    state(xs[0], Y, Ws, Hs, "NULL · FRESH", ["hop-n candidate passed", "gates + self-checks"], "core")
    state(xs[1], Y, Ws, Hs, "NULL · FIISM", ["earth-frame entry", "valid: age, tilt, tag"], "core")
    state(xs[2], Y, Ws, Hs, "BYPASS · CHIP", ["reference-element", "weights; logic alive"], "input")
    state(xs[3], Y, Ws, Hs, "BYPASS · BOARD", ["SPDT / NC relay:", "centre elem. → modem"], "board")
    g.line([(200, 44), (260, 44)], sw=2.0)
    g.text(230, 36, "fails", size=SS - 1, fill=INK2, anchor="middle")
    g.line([(262, 78), (202, 78)], sw=2.0)
    g.text(232, 96, "passes", size=SS - 1, fill=INK2, anchor="middle")
    g.line([(452, 60), (512, 60)], sw=2.0)
    g.text(482, 44, "no valid", size=SS - 1, fill=INK2, anchor="middle")
    g.text(482, 80, "entry", size=SS - 1, fill=INK2, anchor="middle")
    # fresh -> chip on hard refusals; chip -> fresh when valid again
    g.line([(105, Y + Hs), (105, 158), (640, 158), (640, Y + Hs + 2)], sw=1.8, dash="6 4")
    g.text(372, 176, "multi-source (V1) · mainlobe gate · tag mismatch · CRC fail", size=SS - 0.5, fill=INK2, anchor="middle")
    g.line([(580, Y + Hs), (580, 132), (150, 132), (150, Y + Hs + 2)], sw=1.4, dash="3 3", col=MUTED, head="grey")
    g.text(372, 126, "valid candidate on a later hop", size=SS - 1, fill=MUTED, anchor="middle")
    # any -> board
    g.line([(855, 250), (855, Y + Hs + 2)], col=SAFETY, sw=2.2, head="red")
    g.text(845, 196, "from ANY state:", size=SS, weight="bold", fill=SAFETY, anchor="end")
    g.text(845, 214, f"heartbeat lost → {fs['logic_fault_ms']:.0f} ms", size=SS, fill=SAFETY, anchor="end")
    g.text(845, 232, f"board power lost → ≤ {fs['power_loss_ms']:.0f} ms", size=SS, fill=SAFETY, anchor="end")
    # zeroize
    g.rect(10, 262, 440, 112, SAFETY, "#FFFFFF", sw=1.4, rx=10, dash="2 3")
    g.text(24, 286, "Zeroize triggers — from ANY state:", size=SS + 0.5, weight="bold", fill=SAFETY)
    for i, s_ in enumerate(["TAMPER_N (lid switch, light sensor, potting)", "scan or test-mode entry",
                            "TAP / debug unlock attempt in mission mode", "secure-boot or configuration CRC failure"]):
        g.text(24, 306 + 17 * i, "• " + s_, size=SS, fill=INK)
    g.line([(450, 318), (512, 318)], col=SAFETY, sw=2.2, dash="2 3", head="red")
    state(514, 262, 436, 112, "ZEROIZE → BYPASS · BOARD (latched)",
          [f"FIISM, weight buffers, CSRs cleared in {z['time_us']:.1f} µs;", f"hold-up energy margin {z['margin']:.0f}×;",
           "re-arm only by authenticated boot"], "t1", tcol=STYLE["t1"][0])
    g.line([(855, 262), (855, 250)], col=SAFETY, sw=2.2, head=None)
    g.text(10, 404, f"Worst outage {fs['worst_ms']:.0f} ms = {fs['margin_vs_drdo']:.0f}× inside DRDO's 500 ms window; "
                    f"bypass = the unmodified radio − {fs['insertion_loss_db']:.1f} dB.", size=15, fill=NAVY, weight="bold")
    g.text(10, 430, "Invariant, asserted every hop: active bundle tag = current hop frequency, or mode = BYPASS.", size=14.5, fill=INK2, italic=True)
    g.write("fig5_states")


# ======================================================================= GANTT
def fig_gantt():
    g = SVG(960, 392)
    x0, x1 = 262, 890
    mw = (x1 - x0) / 18
    g.text(8, 22, "Phase / work package", size=14, weight="bold", fill=INK2)
    for m in range(18):
        g.text(x0 + mw * (m + 0.5), 22, f"{m+1}", size=13.5, fill=INK2, anchor="middle")
        g.line([(x0 + mw * m, 30), (x0 + mw * m, 384)], col="#EFEEEA", sw=1, head=None)
    g.line([(x1, 30), (x1, 384)], col="#EFEEEA", sw=1, head=None)
    rows = [
        ("1  Golden model + analysis", 1, 4, "core", "D1"),
        ("2  RTL V1 + formal TC1–TC3", 5, 9, "core", "D2"),
        ("    TAP/scan lock, zeroize, boot", 6, 9, "t1", ""),
        ("3  FPGA + RF + board fail-safe", 10, 12, "core", "D3"),
        ("    Tamper switches + potting", 10, 12, "t1", ""),
        ("    Adaptive AGC loop", 10, 12, "t2", ""),
        ("    Environmental screening", 12, 13, "t1", "D4"),
        ("4  Conducted-jamming campaign", 13, 15, "core", "D5"),
        ("    V2 Cholesky + verification", 11, 15, "t2", "D6"),
        ("    Case-B dwell-timer bound", 13, 14, "t2", "D7"),
        ("5  SCL 180 nm + C2S package", 16, 18, "core", "D8"),
    ]
    for i, (lab, a, b, st, ms) in enumerate(rows):
        y = 34 + 32 * i
        stroke, fill, _, _, dash = STYLE[st]
        sub = lab[0] == " "
        g.text(26 if sub else 8, y + 19, lab.strip(), size=14, weight="normal" if sub else "bold", fill=INK)
        g.rect(x0 + mw * (a - 1) + 2, y + 5, mw * (b - a + 1) - 4, 20, stroke, fill if st != "core" else "#E0E0E0",
               sw=1.3, rx=5, dash=dash)
        if st in ("t1", "t2"):
            chip(g, x0 + mw * (a - 1) + 7, y + 20, st.upper(), st, size=11)
        if ms:
            xm = x0 + mw * b - 2
            g.raw(f'<path d="M{xm},{y+5} l9,10 l-9,10 l-9,-10 z" fill="{NAVY}"/>')
            g.text(xm + 13, y + 20, ms, size=14, weight="bold", fill=NAVY)
    g.write("fig0_gantt")


def main():
    ASSETS.mkdir(exist_ok=True)
    fig_architecture()
    fig_timing()
    fig_states()
    fig_gantt()
    print("diagrams written")


if __name__ == "__main__":
    main()
