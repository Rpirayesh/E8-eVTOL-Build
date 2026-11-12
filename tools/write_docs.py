"""Write README.md and the engineering documents from the result files.

    python tools/write_docs.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/Rpirayesh/E8-eVTOL-Build"
PAGES = "https://rpirayesh.github.io/E8-eVTOL-Build/"


def J(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else {}


SEL = J("design/selected_design.json")
CAD = J("cad/mass_properties.json")
PARTS = J("docs/data/parts.json").get("parts", [])
BOM = J("docs/data/bom.json")
AF = J("analysis/fea/airframe/results.json")
PF = J("analysis/fea/parts/summary.json")
VAL = J("analysis/fea/validation/validation.json")
CFD0012 = J("analysis/cfd/airfoil2d/naca0012_validation.json")
GRID = J("analysis/cfd/airfoil2d/naca0012_grid_study.json")
P4415 = J("analysis/cfd/airfoil2d/naca4415_polar.json")
C3D = J("analysis/cfd/cruise3d/results.json")
H3D = J("analysis/cfd/hover3d/results.json")
CFDCHK = J("analysis/sizing/cfd_check.json")
FINE = J("analysis/cfd/cruise3d/fine_mesh.json")
PROP = J("analysis/propeller/results.json")
FS = J("fullscale/results/results.json")
SPAR = J("analysis/fea/airframe/spar_sizing.json")


def f(x, n=1):
    return f"{x:.{n}f}"


def md_table(header, rows):
    out = "| " + " | ".join(header) + " |\n| " + " | ".join("---" for _ in header) + " |\n"
    for r in rows:
        out += "| " + " | ".join(str(c) for c in r) + " |\n"
    return out


def cfd_section():
    if not C3D:
        return "Pending."
    fz = CFDCHK.get("frozen_design_with_cfd_drag", {})
    reg = C3D["drag_area_by_region_m2"]
    bu = SEL["drag_buildup"]
    sens = H3D.get("hover_sensitivity", {})
    rows = [[k, f(reg[k], 4), f(v, 4)] for k, v in (("wing", bu["wing"]), ("fuselage", bu["fuselage"] + bu["pusher_hub"]),
            ("tail", bu["tail"]), ("booms", bu["booms"]), ("rotors", bu["stopped_rotors"]), ("gear", bu["landing_gear"]))]
    fine = ""
    if FINE:
        fine = (f"\nA finer mesh ({FINE['cells']:,} cells) gives CD = {f(FINE['a0']['CD'], 4)} at 0 deg "
                f"(coarse {f(FINE['coarse_a0']['CD'], 4)}) and CL = {f(FINE['a8']['CL'], 3)} at 8 deg (coarse {f(FINE['coarse_a8']['CL'], 3)}).\n")
    out = f"""Full-aircraft OpenFOAM (k-omega SST, {C3D['mesh_cells']:,}-cell half model, lift rotors stopped):
**CD0 = {f(C3D['cd0_full_aircraft'], 4)}**, Oswald e = {f(C3D['oswald_e'], 2)}, lift slope {f(C3D['cl_alpha_per_deg'], 3)} /deg,
neutral point {f(C3D['x_neutral_point_m'] * 1000, 0)} mm behind the leading edge -> **static margin {f(100 * C3D['static_margin'], 1)} % MAC**
at the design CG (stable; move the battery 15 mm forward for about 10 %).

{md_table(["Drag area D/q (m²)", "CFD", "Component build-up"], rows)}
The stopped lift rotors are the largest drag item in both methods and the two agree on them. The wing and landing gear
are higher in the CFD: the CFD is fully turbulent with wall functions (the 2-D transition runs show the laminar
bucket the printed wing can keep if its surface is smooth), and the bare legs and feet are bluff — faired legs are an
easy gain. Performance is therefore bracketed:

{md_table(["Drag model", "Cruise L/D", "Cruise power", "Range"], [
    ["Component build-up (design value)", f(SEL['mission']['cruise']['LD'], 1), f"{f(SEL['mission']['cruise']['p_elec_w'], 0)} W", f"{f(SEL['mission']['range_km'], 1)} km"],
    ["CFD, fully turbulent (conservative)", f(fz.get('LD', 0), 1), f"{f(fz.get('cruise_w', 0), 0)} W", f"{f(fz.get('range_km', 0), 1)} km"]])}
With the conservative drag the pusher draws {f(fz.get('pusher_current_a', 0), 0)} A at 25 m/s (60 A peak rating): cruise at
22-23 m/s if flight logs confirm the higher drag.
{fine}
**Hover download** (eight actuator disks): {f(H3D.get('download_n', 0), 0)} N = {f(100 * H3D.get('download_fraction_of_thrust', 0), 0)} % of thrust as an upper
bound (uniform disks load the hub; flight data of similar aircraft is typically 5-10 %). Even at the upper bound the
thrust-to-weight is {f(sens.get('CFD upper bound', {}).get('thrust_to_weight', 0), 2)} and the worst rotor-out case loads the remaining rotors to
{f(100 * sens.get('CFD upper bound', {}).get('worst_rotor_out_frac', 0), 0)} % of maximum.

![drag breakdown](docs/img/cfd3d_drag_breakdown.png)"""
    return out


def readme():
    m, d, g = SEL["mission"], SEL["design"], SEL["geometry"]
    cr, hv = m["cruise"], m["hover"]
    ms = AF["margins"]
    min_part = min(PF.items(), key=lambda kv: kv[1]["MS"])
    n_made = sum(p["qty"] for p in PARTS if p["process"] in ("FDM", "CNC"))
    n_all = sum(p["qty"] for p in PARTS)
    cd0 = C3D.get("cd0_full_aircraft")
    cfd_line = (f"CFD drag polar of the whole aircraft: CD0 = {f(cd0, 4)}, Oswald e = {f(C3D['oswald_e'], 2)}, "
                f"cruise L/D = {f(C3D['cruise_LD'], 1)}, static margin {f(100 * C3D['static_margin'], 0)} % MAC") if cd0 else ""
    txt = f"""# E8-S: lift + cruise eVTOL demonstrator

A buildable, analysed subscale demonstrator of the two-seat E8 eVTOL concept, redesigned as a **lift + cruise** aircraft
with eight fixed lift rotors and a **rear pusher propeller** for speed. Every part is designed to be made with a
**3-axis CNC and FDM 3-D printers** (no metal printing) or bought off the shelf, and the whole aircraft is checked with
open-source CFD (OpenFOAM) and FEA (CalculiX).

**[Open the 3-D build viewer]({PAGES})** — every component in 3-D, how it is made, its settings and download links ·
**[Analysis & validation]({PAGES}analysis.html)** · **[Bill of materials]({PAGES}bom.html)**

![Assembled aircraft](docs/img/render_iso.png)

## Design at a glance

{md_table(["Item", "Value"], [
    ["Configuration", "twin boom, high wing, H-tail; 8 fixed lift rotors (4 per boom), 1 rear pusher"],
    ["Span / chord / wing area", f"{d['span_m']} m / {d['chord_m']} m / {f(g['S'], 2)} m² (NACA 4415)"],
    ["Take-off mass (sized, incl. 10 % growth)", f"{f(SEL['mass']['total_kg'], 2)} kg (CAD-measured structure)"],
    ["Battery", f"2 x Tattu 22000 mAh 6S in series = 12S, {f(m['e_nom_wh'], 0)} Wh"],
    ["Lift system", "8 x T-Motor MN5008 KV170 + P18x6.1, FLAME 60A 12S ESCs"],
    ["Pusher", "T-Motor AT4130 KV230 + APC 17x10EP, FLAME 80A 12S"],
    ["Hover power / thrust-to-weight", f"{f(hv['p_elec_w'], 0)} W / {f(hv['tw_ratio'], 2)}"],
    ["Worst single-rotor-out", f"{f(100 * max(r['max_thrust_frac'] for r in SEL['rotor_out']), 0)} % of a rotor's maximum thrust on the most loaded motor"],
    ["Cruise", f"{f(cr['V'], 0)} m/s ({f(3.6 * cr['V'], 0)} km/h), {f(cr['p_elec_w'], 0)} W electrical"],
    ["Range / cruise endurance", f"{f(m['range_km'], 1)} km / {f(m['cruise_min'], 0)} min (2 min hover, 20 % reserve)"],
    ["Top speed (pack-voltage limited)", f"{f(SEL['max_level_speed_ms'], 1)} m/s ({f(3.6 * SEL['max_level_speed_ms'], 0)} km/h)"],
    ["Stall speed (CLmax 1.25)", f"{f(SEL['stall_ms'], 1)} m/s"],
    ["Components", f"{n_all} in the assembly; {n_made} made in-house ({sum(1 for p in PARTS if p['process'] == 'FDM')} printed and {sum(1 for p in PARTS if p['process'] == 'CNC')} machined part types)"],
    ["Estimated cost", f"${BOM['total_usd']:,.0f} including charger and transmitter"],
])}
{cfd_line}

## Aerodynamics: what the CFD changed

{cfd_section()}

## What was done

1. **Started from the E8 Design Explorer concept** (two-seat, eight tilting rotors). With a pusher for cruise thrust,
   tilting rotors are unnecessary: fixed lift rotors remove eight tilt mechanisms and stop in cruise (lift + cruise).
2. **Scale decision.** A person-carrying aircraft cannot be built or validated with a 3-axis CNC and polymer printers,
   so the build package is a subscale flying demonstrator of the same layout; the two-seat aircraft is re-studied in
   [fullscale/](fullscale/FULLSCALE.md).
3. **Optimisation** ([tools/sizing.py](tools/sizing.py)): span, chord and battery are searched for maximum range at a
   required 25 m/s cruise, subject to thrust-to-weight >= 2, rotor-out allocation <= 75 % of maximum thrust, stall <= 15 m/s,
   battery C-rate and pusher current limits. Performance uses the **manufacturer bench data** of the motors and APC's
   propeller tables. The structure masses are **measured from the CAD** and fed back until mass and CG converge.
4. **CAD** ([tools/cad/parts.py](tools/cad/parts.py), build123d / OpenCascade): {len(PARTS)} unique parts, STEP + STL each.
5. **CFD** (OpenFOAM v2412): NACA 0012 validation against NASA TMR data and a grid study, wing/tail section polars
   with SST and transition models, full-aircraft cruise polar and hover download with rotor actuator disks.
6. **FEA** (CalculiX 2.23 + own frame solver, both verified): ten ultimate load cases on the whole airframe, spar sizing,
   modal analysis, and solid FEA of every load-bearing printed / machined part.
7. **Propellers:** BEMT checked against APC data; printed blades analysed with centrifugal stiffening.
   **Verdict: buy the propellers** — printed blades pass static strength but fail fatigue (details below).

## Structural results (ultimate = 1.5 x limit)

{md_table(["Member", "Max stress", "Allowable", "Margin", "Critical case"],
          [[k, f"{f(v.get('max_sigma_mpa', v.get('max_tau_mpa', 0)), 0)} MPa", f"{f(v['allowable_mpa'], 0)} MPa", f"{v['MS']:+.2f}", v["case"]] for k, v in ms.items()]
          + [[f"{v['part']} ({k})", f"{f(v['vm_p995_mpa'], 1)} MPa", f"{f(v['allowable_mpa'], 0)} MPa", f"{v['MS']:+.2f}", v["load_case"]] for k, v in PF.items()])}
The spar search raised the main spar from 20 x 18 to **30 x 27 mm** (same stock as the booms) and the rear spar to
12 x 10 mm; the booms were upsized to 30 x 27 mm for stiffness; the wing-carry bulkheads were widened after the first
FEA showed a negative margin. First free-free airframe mode: **{f(AF['modes']['modes'][0]['f_hz'], 1)} Hz** (boom/wing pitch) —
measure it with a tap test and set the PX4 gyro notch ([firmware/](firmware/README.md)).

## 3-D printed propellers?

{md_table(["Blade material", "Peak stress (7900 rpm static)", "Static margin", "Fatigue margin (cruise)"],
          [[k, f"{f(v['max_stress_mpa'], 1)} MPa", f"{v['MS_static']:+.2f}", f"{v['MS_fatigue_cruise']:+.2f}"] for k, v in PROP['printed_pusher']['materials'].items()])}
A printed PA6-CF copy of the 17x10 pusher will not break on spin-up, but its fatigue margin is negative for the cruise
duty; it is acceptable only for **ground and bench tests up to {f(PROP['printed_pusher']['pa6cf_max_rpm_static']['rpm'], 0)} rpm**
behind a guard. Printed lift rotors also fail the fatigue check. The printable blade CAD is in
[cad/parts/PROP-PRINT](cad/parts/PROP-PRINT) for testing only.

## Repository map

| Folder | Contents |
| --- | --- |
| [docs/](docs/) | Browser viewer (GitHub Pages), analysis and BOM pages, figures, GLB models |
| [cad/parts/](cad/parts/) | STEP + STL of every manufactured part (mm) |
| [cad/assembly/](cad/assembly/) | Full assembly STEP |
| [bom/](bom/) | `BOM.csv` with prices and sources, `cut_list.csv` for carbon tubes |
| [MANUFACTURING.md](MANUFACTURING.md) | Print / CNC settings for every part |
| [ASSEMBLY.md](ASSEMBLY.md) | Build sequence, wiring, CG check, first-flight test plan |
| [VALIDATION.md](VALIDATION.md) | CFD and FEA verification and validation evidence |
| [firmware/](firmware/README.md) | PX4 control-allocation parameters |
| [fullscale/](fullscale/FULLSCALE.md) | Two-seat aircraft study with pusher |
| [analysis/](analysis/) | Raw results (JSON) of sizing, CFD, FEA and propeller studies |
| [tools/](tools/) | Everything that produced the above |

## Reproduce

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt              # build123d, numpy, scipy, trimesh, neuralfoil, matplotlib
# OpenFOAM v2412, CalculiX and gmsh (e.g. conda-forge: openfoam=2412 calculix gmsh)
python tools/sizing.py                       # optimisation
python tools/build_cad.py                    # CAD, STEP/STL/GLB, mass properties
python tools/fea/validation.py               # solver verification
python tools/fea/airframe.py                 # global structure, modes
python tools/fea/parts_fea.py                # CalculiX part models
python tools/cfd/airfoil2d.py validate       # NACA 0012 vs NASA TMR
python tools/cfd/airfoil2d.py wing           # wing section polars
python tools/cfd/aircraft3d.py geometry && python tools/cfd/aircraft3d.py mesh
python tools/cfd/aircraft3d.py cruise && python tools/cfd/aircraft3d.py hover && python tools/cfd/aircraft3d.py post
python tools/sizing.py --cfd                 # re-evaluate with the CFD drag
python tools/propeller/prop_study.py
python tools/build_bom.py && python tools/make_figures.py && python tools/write_docs.py
```

## Safety and limits

This is an engineering design for an unmanned demonstrator of about {f(SEL['mass']['total_kg'], 0)} kg. Fly it only where
permitted (e.g. FAA Part 107 in the USA: under 25 kg, registered, within line of sight), with a failsafe, away from people.
Analyses are only as good as their inputs: printed-material allowables include knock-downs but printed parts vary
with printer, filament and moisture — **proof-load the boom/wing joint, spin-test the props, measure the CG and the first
structural mode, and tether the first hovers** (see [ASSEMBLY.md](ASSEMBLY.md)).
"""
    (ROOT / "README.md").write_text(txt)


def manufacturing():
    groups = {}
    for p in PARTS:
        groups.setdefault(p["group"], []).append(p)
    out = ["# Manufacturing guide\n",
           "Every in-house part, how to make it and with which settings. Files: `cad/parts/<ID>/<ID>.stl` (printing) and "
           "`<ID>.step` (CAM). Units are mm. Quantities are per aircraft.\n",
           "## Equipment and materials\n",
           "- **FDM printer** with at least 256 x 256 x 256 mm build volume, hardened 0.4 mm nozzle and an enclosure for PA6-CF "
           "(e.g. Bambu X1C/P1S, Prusa Core One). Dry PA6-CF at 80 °C for 8 h before printing.\n"
           "- **LW-PLA** (foaming PLA) for skins: calibrate flow for ~50 % expansion at about 230-245 °C; one perimeter gives the "
           "modelled 0.6 mm skin. Print segments standing on their root rib; no supports.\n"
           "- **3-axis CNC**: router for birch plywood; aluminium parts need a spindle and machine able to cut 6061 "
           "(light DOC, mist or air blast). If your CNC cannot cut aluminium, use a local job shop for the four aluminium parts — "
           "they are simple 2- and 2.5-D parts.\n"
           "- Carbon tubes are cut with a fine abrasive disc; wear a respirator and cut wet.\n"]
    for g, ps in groups.items():
        made = [p for p in ps if p["process"] in ("FDM", "CNC", "COTS-cut")]
        if not made:
            continue
        out.append(f"\n## {g}\n")
        for p in made:
            s = p["settings"]
            out.append(f"\n### {p['id']} — {p['name']}\n")
            out.append(f"- **Process:** {p['process']} · **Material:** {p['material']} · **Qty:** {p['qty']} · "
                       f"**Mass each:** {p['mass_g_each']} g · **Envelope:** {' x '.join(str(x) for x in p['size_mm'])} mm\n")
            for k, v in s.items():
                out.append(f"- {k.replace('_', ' ').capitalize()}: {v}\n")
            if p["notes"]:
                out.append(f"- Note: {p['notes']}\n")
            if p["files"]:
                out.append(f"- Files: [{p['files']['stl']}]({p['files']['stl']}), [{p['files']['step']}]({p['files']['step']})\n")
    (ROOT / "MANUFACTURING.md").write_text("".join(out))


def validation():
    v1 = VAL["V1"]["mesh_study"]
    of = [r for r in CFD0012["openfoam"] if "Cl" in r]
    cfl = CFD0012["tmr"]["CFL3D_SST_897x257"]
    rows_cfd = []
    for r in of:
        ref = next((cl for a, cl in zip(cfl["alpha"], cfl["Cl"]) if abs(a - r["alpha"]) < 0.1), None)
        refd = next((cd for a, cd in zip(cfl["alpha"], cfl["Cd"]) if abs(a - r["alpha"]) < 0.1), None)
        rows_cfd.append([r["alpha"], f(r["Cl"], 4), f(ref, 4) if ref is not None else "—", f(r["Cd"], 5), f(refd, 5) if refd is not None else "—"])
    txt = f"""# Verification and validation

## CFD

### NACA 0012, Re = 6 million (NASA Turbulence Modeling Resource case 2DN00)

OpenFOAM `simpleFoam`, k-omega SST, structured O-grid ({of[0]['cells']} cells, y+ < 1, far field 50 chords),
free-stream turbulence as specified by TMR (Tu 0.052 %, nu_t/nu 0.009). References: CFL3D SST on the 897 x 257 grid and
Ladson (1988) tripped experiments, both downloaded from the TMR site (`analysis/cfd/airfoil2d/reference/`).

{md_table(["alpha (deg)", "CL OpenFOAM", "CL CFL3D", "CD OpenFOAM", "CD CFL3D"], rows_cfd)}
Lift is 2-5 % high, the expected effect of a 50-chord far field without the point-vortex correction used by TMR (500 chords).

![NACA 0012](docs/img/cfd_naca0012_validation.png)

### Grid convergence (alpha 10 deg)

{md_table(["Grid", "Cells", "CL", "CD"], [[r["grid"], r["cells"], f(r["Cl"], 4), f(r["Cd"], 5)] for r in GRID])}
![grid](docs/img/cfd_grid_study.png)

### Wing section NACA 4415 at the cruise Reynolds number

Fully turbulent SST, Langtry-Menter transition (`kOmegaSSTLM`) and NeuralFoil (an XFOIL-trained model) are compared;
the transition model and NeuralFoil agree on the low drag bucket, the fully turbulent model is the conservative bound.

![4415](docs/img/cfd_naca4415_polar.png)

### Full aircraft

{"Cruise polar from the 3-D half-model (see analysis/cfd/cruise3d/results.json); mesh " + str(C3D.get('mesh_cells')) + " cells. CD0 = " + f(C3D['cd0_full_aircraft'], 4) + ", lift slope " + f(C3D['cl_alpha_per_deg'], 4) + " /deg, neutral point at x = " + f(C3D['x_neutral_point_m'] * 1000, 0) + " mm (CG " + f(C3D['x_cg_m'] * 1000, 0) + " mm), static margin " + f(100 * C3D['static_margin'], 0) + " % MAC." if C3D else "Pending."}

![polar](docs/img/cfd3d_polar.png)
![drag](docs/img/cfd3d_drag_breakdown.png)

## FEA

### V1: CalculiX C3D10 cantilever vs Timoshenko beam (mesh convergence)

{md_table(["h max (mm)", "Elements", "Tip (mm)", "Error tip", "Mid-span stress (MPa)", "Error stress"],
          [[r["hmax_mm"], r["elems"], f(r["tip_mm"], 4), f"{r['err_tip_pct']:+.2f} %", f(r["sigma_mid_mpa"], 2), f"{r['err_sigma_pct']:+.2f} %"] for r in v1])}
Exact solution: tip {f(VAL['V1']['tip_timoshenko_mm'], 4)} mm (Timoshenko), mid-span stress {f(VAL['V1']['sigma_mid_mpa'], 2)} MPa.
Reaction force equals the applied 100 N to machine precision in every run.

### V2: frame solver vs closed form

Tip deflection {f(VAL['V2']['tip_mm'], 3)} mm (exact {f(VAL['V2']['tip_analytic_mm'], 3)}), root stress {f(VAL['V2']['sigma_mpa'], 2)} MPa
(exact {f(VAL['V2']['sigma_analytic_mpa'], 2)}), first frequency with tip mass {f(VAL['V2']['f1_hz'], 3)} Hz (exact {f(VAL['V2']['f1_analytic_hz'], 3)} Hz).

### V3: CalculiX solid vs frame solver on the same tube

Tip deflection {f(VAL['V3']['tip_ccx_mm'], 4)} mm vs {f(VAL['V3']['tip_frame_mm'], 4)} mm ({VAL['V3']['diff_pct']:+.1f} %, shear flexibility of the solid).

### Load cases, margins and modes

![margins](docs/img/fea_margins.png)
![campbell](docs/img/fea_campbell.png)

Allowables (ultimate): carbon tube 250 MPa; 6061-T6 240 MPa; printed PA6-CF 25 MPa; PETG 14 MPa; birch plywood 25 MPa;
LW-PLA skin shear 3 MPa. Printed-part allowables include knock-downs for layer adhesion, moisture, creep and fatigue.

## Propeller method check

![bemt](docs/img/prop_bemt_vs_apc.png)
"""
    (ROOT / "VALIDATION.md").write_text(txt)


def fullscale():
    s, o = FS["selected"], FS["original"]
    txt = f"""# Full-scale two-seat E8 with a rear pusher (engineering study)

Not a build package: a person-carrying aircraft needs certified structures, systems and testing far beyond this
repository. This study answers *what the pusher changes* for the two-seat aircraft, using the assumptions of the
original E8 concept study.

Changes from the original: lift rotors fixed (eight tilt mechanisms, 32 kg, removed); a pusher (motor sized to 1.25 x
cruise power at {5.0:.0f} kW/kg, 1.8 m propeller) provides cruise thrust; the stopped lift rotors' drag is scaled from the
subscale CFD ({f(FS['stopped_rotor_drag_area_m2'], 3)} m², {FS['drag_source']}).

{md_table(["", "Original (tilt rotor)", "Lift + cruise with pusher"], [
    ["Cruise speed", f"{o['cruise_kph']} km/h", f"{s['V_kph']} km/h"],
    ["Mass", f"{o['mass_kg']} kg", f"{f(s['mass_kg'], 0)} kg"],
    ["Wing area / span", f"{o['wing_m2']} m² / {o['span_m']} m", f"{s['S']} m² / {s['b']} m"],
    ["Hover / cruise electrical", f"{o['hover_kw']} / {o['cruise_kw']} kW", f"{f(s['hover_kw'], 0)} / {f(s['cruise_kw'], 0)} kW"],
    ["Battery", f"{o['battery_kwh']} kWh", f"{f(s['battery_kwh'], 1)} kWh"],
    ["Range (20 % reserve)", f"{o['range_km']} km", f"{f(s['range_km'], 1)} km"],
])}
![range vs speed](../docs/img/fullscale_range_vs_speed.png)

Range against required cruise speed (each point re-optimised):

{md_table(["km/h", "range km", "S m²", "b m", "mass kg", "cruise kW", "L/D"], [[p["V_kph"], f(p["range_km"], 1), p["S"], p["b"], f(p["mass_kg"], 0), f(p["cruise_kw"], 0), f(p["LD"], 1)] for p in FS["pareto"]])}
**Findings.** At the original 140 km/h the pusher configuration flies about 25 % farther; at 180 km/h it matches the
original range while flying 29 % faster. The binding limit is the lift system: hover needs about
{f(s['per_motor_kw'], 1)} kW per motor (30 kW continuous rating) and the worst single-rotor-out case needs about
{f(max(r['shaft_kw'] for r in FS['rotor_out']), 0)} kW shaft on the most loaded motor — larger lift motors (or more rotors) are
the first change the full-scale aircraft needs, before any further aerodynamic refinement.
"""
    (ROOT / "fullscale" / "FULLSCALE.md").write_text(txt)


def main():
    readme()
    manufacturing()
    validation()
    fullscale()
    print("docs written")


if __name__ == "__main__":
    main()
