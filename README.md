# HOPNULL-ARC

A hop-synchronous, direction-state anti-jam spatial-nulling accelerator for frequency-hopping UAV command-and-control (C2) links.

## What it is

Most anti-jam beamforming work is about the math (null-steering, MVDR/LCMV, CRPA). HOPNULL-ARC's
differentiator is a hop-synchronous, frequency-indexed, deadline-bound hardware transaction layer
around that math: the guarantee that the right spatial null, validated against the right
calibration/frequency/jammer state, gets committed before the right hop deadline, every time, with
a provable fallback when it can't.

Core idea: instead of storing per-band null weights (destroyed by the platform's own rotation in
tens of milliseconds), HOPNULL-ARC stores the jammer's **direction** in an earth frame, re-rotated
every hop from IMU attitude. Direction state survives turns, blinking jammers, and wide hop spans
in a way per-band weight storage cannot.

Architecture (frozen at the block level):

```
Block 1 (observe) -> Block 2 (candidate) -> Block 3 (commit) -> Block 4 (apply) -> unmodified FH modem
```

- **Block 1 — Spatial Observation**: calibrated IQ -> phase-gradient interferometry -> direction
  cosines + coherence-gated validity, deterministic bounded execution.
- **Block 2 — Candidate Generator**: DoA state -> closed-form minimum-norm weight vector,
  quantized, self-checked, published as an immutable candidate transaction.
- **Block 3 — Transaction Manager + FIISM**: arbitrates fresh candidate vs. frequency-indexed
  history vs. safe bypass; sole commit authority; owns fault lifecycle and calibration-domain
  consistency.
- **Block 4 — Beamformer**: mode-blind linear combiner, applies whatever was committed.
- **Pillar 5 — Ibex RISC-V core**: advisory-only config/control plane, no commit authority.

Target: SCL 180 nm via India's C2S MPW shuttle program, with an FPGA (Zynq-class) prototype
validated under conducted (never radiated) jamming first.

## Golden model

Every number this project quotes is **computed**, not typed. `analysis/` is a Python/NumPy golden
model that runs the actual math (array geometry trade, null survival, calibration limits, latency
budgets, multi-jammer path, survivability) and gates on 10 invariant self-checks — the same
properties the RTL will later be held to formally.

```
python3 -m pip install -r requirements.txt
python3 -m analysis.run_all       # runs every model + self-checks, writes results.json + RESULTS.md
python3 -m analysis.plots         # data figures (survival/calibration, survivability/latency)
python3 -m analysis.diagrams      # hand-laid architecture/timing/state-machine diagrams
python3 -m pytest analysis        # the same invariants as pytest cases
```

## Layout

- `analysis/` — the golden model and analysis suite
  - `params.py` — every assumption (design decisions, reference scenario, published requirements) in one place
  - `array.py`, `nuller.py` — Y-array steering, 2-D phase-gradient DoA, closed-form nuller, CLZ+LUT normalisation, self-checks
  - `geometry.py` — array-geometry trade (why a planar Y beats a line or a square)
  - `survival.py` — null survival under rotation (body-frame vs. earth-frame), FIISM hit rate, stale-weight loss across hop spans
  - `calibration.py` — calibration-limited vs. estimation-limited rejection depth
  - `latency.py` — cycle-level timing budget, max hop rate, Case-B (no-sideband) dwell-timer bound
  - `multijammer.py` — two-jammer path (fixed-sweep Jacobi EVD, grid MUSIC, 4x4 Cholesky)
  - `survivability.py` — link budget, denial range, fail-safe, zeroize, GNSS-denied operation
  - `checks.py` / `test_golden.py` — the invariant self-checks (future RTL formal properties)
  - `plots.py`, `diagrams.py` — vector SVG figures drawn from `results.json`
  - `RESULTS.md` — human-readable summary of the latest analysis run
- `assets/` — the vector figures produced by `plots.py`/`diagrams.py`
- `source/` — the original architecture reference document
- `requirements.txt` — `numpy`, `matplotlib`

## Status

Architecture is frozen at the block level (structure, gate ordering, formal invariants, fault
lifecycle). Fixed-point widths, the V2 dual-jammer path's real-world validation, and RTL
implementation are the open work — see `analysis/RESULTS.md` for exactly what the golden model has
and hasn't settled yet.
