"""Design optimisation of the subscale E8 lift+cruise demonstrator.

Searches wing span, chord and battery configuration; for each candidate the
cruise speed is chosen for maximum range.  Candidates must pass all constraints;
the feasible candidate with the longest range is selected.

    python tools/sizing.py            # uses the analytic drag build-up
    python tools/sizing.py --cfd      # uses CD0 calibrated from the OpenFOAM cruise case

Writes design/selected_design.json and analysis/sizing/*.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from e8lib import aircraft as ac  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "sizing"

CONSTRAINTS = {
    "stall_ms_max": 15.0,          # wing-borne transition must finish at a modest speed
    "tw_min": 2.0,                 # all-engine hover thrust / weight
    "rotor_out_frac_max": 0.75,    # most-loaded remaining rotor, one rotor failed
    "hover_c_rate_max": 0.5,       # fraction of rated continuous C
    "cruise_current_max_a": 40.0,  # AT4130 KV230: 60 A peak (180 s); keep cruise <= 2/3 of peak
    "span_max_m": 3.0,             # transport / workshop
    "aspect_ratio_min": 6.0,
}


def cfd_cd0() -> float | None:
    path = ROOT / "analysis" / "cfd" / "cruise3d" / "results.json"
    if path.exists():
        return json.loads(path.read_text())["cd0_full_aircraft"]
    return None


V_REQUIRED = 25.0  # design cruise speed (m/s): the pusher is there for speed


def evaluate(span, chord, battery, n_bat, cd0=None, v_req=V_REQUIRED) -> dict:
    d = ac.build(ac.Design(span_m=span, chord_m=chord, battery=battery, n_battery=n_bat, cd0_override=cd0))
    d.cruise_ms = max(ac.best_cruise_speed(d), v_req)
    m = ac.mission(d)
    ro = ac.rotor_out(d)
    bat = ac.COMPONENTS[battery]
    worst = max((r["max_thrust_frac"] for r in ro if r["feasible"]), default=9)
    checks = {
        "stall": ac.stall_speed(d) <= CONSTRAINTS["stall_ms_max"],
        "tw": m["hover"]["tw_ratio"] >= CONSTRAINTS["tw_min"],
        "rotor_out": all(r["feasible"] for r in ro) and worst <= CONSTRAINTS["rotor_out_frac_max"],
        "c_rate": m["c_rate_hover"] <= CONSTRAINTS["hover_c_rate_max"] * bat["c_cont"],
        "cruise_current": m["cruise"]["motor_current"] <= CONSTRAINTS["cruise_current_max_a"],
        "span": span <= CONSTRAINTS["span_max_m"] and span >= 2 * d.boom_y_m + 0.5,
        "AR": d.geom["AR"] >= CONSTRAINTS["aspect_ratio_min"],
    }
    return dict(design=d, mission=m, rotor_out=ro, worst_rotor_out=worst, checks=checks,
                feasible=all(checks.values()))


def max_speed(d) -> float:
    """Level speed limited by the pusher's 180 s peak current (60 A) or by the
    voltage available from a 12S pack under load (3.5 V/cell = 42 V)."""
    for V in np.arange(15, 45, 0.25):
        try:
            cr = ac.cruise(d, V)
        except ValueError:
            return float(V - 0.25)
        if cr["motor_current"] > 60 or cr["motor_voltage"] > 42.0:
            return float(V - 0.25)
    return 45.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfd", action="store_true", help="use CD0 from the CFD cruise case")
    args = ap.parse_args()
    cd0 = cfd_cd0() if args.cfd else None
    if args.cfd and cd0 is None:
        sys.exit("No CFD result yet: run the cruise3d case first")
    OUT.mkdir(parents=True, exist_ok=True)

    spans = np.round(np.arange(2.0, 3.01, 0.1), 2)
    chords = np.round(np.arange(0.20, 0.361, 0.02), 3)
    batteries = [("battery_16000", 2), ("battery_16000", 4), ("battery_22000", 2), ("battery_22000", 4)]
    rows, results = [], []
    for span, chord, (bat, n) in itertools.product(spans, chords, batteries):
        r = evaluate(float(span), float(chord), bat, n, cd0)
        d, m = r["design"], r["mission"]
        rows.append(dict(span_m=span, chord_m=chord, battery=bat, n_battery=n,
                         mass_kg=round(d.mass["total_kg"], 3), wing_area_m2=round(d.geom["S"], 3),
                         cruise_ms=d.cruise_ms, LD=round(m["cruise"]["LD"], 2),
                         cruise_w=round(m["cruise"]["p_elec_w"], 1), hover_w=round(m["hover"]["p_elec_w"], 1),
                         range_km=round(m["range_km"], 2), endurance_min=round(m["cruise_min"], 1),
                         stall_ms=round(ac.stall_speed(d), 2), tw=round(m["hover"]["tw_ratio"], 2),
                         rotor_out_frac=round(r["worst_rotor_out"], 3), feasible=r["feasible"],
                         failed=";".join(k for k, v in r["checks"].items() if not v)))
        results.append(r)
    with open(OUT / ("trade_study_cfd.csv" if args.cfd else "trade_study.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    feas = [r for r in results if r["feasible"]]
    best = max(feas, key=lambda r: r["mission"]["range_km"])
    d = best["design"]
    s = ac.summary(d)
    s["optimisation"] = dict(candidates=len(results), feasible=len(feas), constraints=CONSTRAINTS,
                             objective=f"maximum range at cruise speed >= {V_REQUIRED} m/s with 2 min hover, 8 Wh transition, 20 % reserve",
                             drag_model="CFD-calibrated CD0" if cd0 else "component build-up")
    s["max_level_speed_ms"] = max_speed(d)
    s["layout"] = ac.rotor_layout(d)
    (ROOT / "design").mkdir(exist_ok=True)
    if cd0 is None:
        out_json = ROOT / "design" / "selected_design.json"
    else:
        # CFD drag check: re-optimised point and the frozen design evaluated with the CFD CD0
        out_json = OUT / "cfd_check.json"
        frozen = json.loads((ROOT / "design" / "selected_design.json").read_text())["design"]
        fd = ac.build(ac.Design(**{k: v for k, v in frozen.items() if k != "cd0_override"}, cd0_override=cd0))
        fd.cruise_ms = frozen["cruise_ms"]
        fm = ac.mission(fd)
        s["frozen_design_with_cfd_drag"] = dict(cd0=cd0, range_km=fm["range_km"], cruise_min=fm["cruise_min"],
                                                cruise_w=fm["cruise"]["p_elec_w"], LD=fm["cruise"]["LD"],
                                                pusher_current_a=fm["cruise"]["motor_current"], max_speed_ms=max_speed(fd))
        print("frozen design with CFD drag:", s["frozen_design_with_cfd_drag"])
    out_json.write_text(json.dumps(s, indent=2, default=float))
    print(f"{len(results)} candidates, {len(feas)} feasible")
    print(f"selected: span {d.span_m} m, chord {d.chord_m} m, {d.n_battery}x {d.battery}, "
          f"mass {d.mass['total_kg']:.2f} kg, V {d.cruise_ms} m/s, range {best['mission']['range_km']:.1f} km, "
          f"endurance {best['mission']['cruise_min']:.1f} min, Vmax {s['max_level_speed_ms']:.1f} m/s")
    pareto = []
    for v_req in np.arange(16, 33.1, 1.0):
        best_v = None
        for span, chord, (bat, n) in itertools.product(spans[::2], chords[::2], batteries):
            r = evaluate(float(span), float(chord), bat, n, cd0, float(v_req))
            if r["feasible"] and (best_v is None or r["mission"]["range_km"] > best_v["mission"]["range_km"]):
                best_v = r
        if best_v:
            bd = best_v["design"]
            pareto.append(dict(v_req=float(v_req), range_km=best_v["mission"]["range_km"], span=bd.span_m,
                               chord=bd.chord_m, battery=f"{bd.n_battery}x {bd.battery}", mass=bd.mass["total_kg"]))
    (OUT / f"pareto{'_cfd' if args.cfd else ''}.json").write_text(json.dumps(pareto, indent=1, default=float))
    plots(rows, d, args.cfd, pareto)


def plots(rows, d, cfd, pareto):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tag = "_cfd" if cfd else ""
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=130)
    labels = {("battery_16000", 2): "12S 16 Ah (2 packs)", ("battery_16000", 4): "12S 32 Ah (4 packs)",
              ("battery_22000", 2): "12S 22 Ah (2 packs)", ("battery_22000", 4): "12S 44 Ah (4 packs)"}
    for key, lab in labels.items():
        sub = [r for r in rows if (r["battery"], r["n_battery"]) == key]
        f = [r for r in sub if r["feasible"]]
        nf = [r for r in sub if not r["feasible"]]
        p = ax.scatter([r["mass_kg"] for r in f], [r["range_km"] for r in f], s=10, label=lab)
        ax.scatter([r["mass_kg"] for r in nf], [r["range_km"] for r in nf], s=6, marker="x",
                   color=p.get_facecolor()[0], alpha=0.25)
    ax.scatter([d.mass["total_kg"]], [ac.mission(d)["range_km"]], s=120, facecolor="none", edgecolor="k", lw=1.5,
               label="selected")
    ax.set_xlabel("Take-off mass (kg)")
    ax.set_ylabel("Cruise range (km)")
    ax.set_title("Design space (dots feasible, crosses violate a constraint)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / f"design_space{tag}.png")

    fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=130)
    V = np.arange(14, 36, 0.5)
    cr = [ac.cruise(d, v) for v in V]
    ax[0].plot(V, [c["p_elec_w"] for c in cr], label="electrical power")
    ax[0].plot(V, [c["drag_n"] * c["V"] for c in cr], label="drag power (D·V)")
    ax[0].axvline(d.cruise_ms, color="k", ls="--", lw=0.8)
    ax[0].set_xlabel("Airspeed (m/s)")
    ax[0].set_ylabel("Power (W)")
    ax[0].legend(frameon=False)
    ax[0].grid(alpha=0.3)
    ax[1].plot(V, [c["LD"] for c in cr], label="L/D")
    ax[1].plot(V, [c["eta_prop"] * 10 for c in cr], label="prop efficiency ×10")
    ax[1].axvline(d.cruise_ms, color="k", ls="--", lw=0.8)
    ax[1].set_xlabel("Airspeed (m/s)")
    ax[1].legend(frameon=False)
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / f"cruise_polar{tag}.png")

    fig, ax = plt.subplots(figsize=(6.5, 4), dpi=130)
    ax.plot([p["v_req"] * 3.6 for p in pareto], [p["range_km"] for p in pareto], marker="o")
    ax.axvline(V_REQUIRED * 3.6, color="k", ls="--", lw=0.8)
    ax.set_xlabel("Required cruise speed (km/h)")
    ax.set_ylabel("Best feasible range (km)")
    ax.set_title("Speed vs range trade (each point re-optimised)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / f"pareto{tag}.png")


if __name__ == "__main__":
    main()
