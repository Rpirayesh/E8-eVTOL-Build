"""Post-processing of the 3-D OpenFOAM cases -> analysis/cfd/cruise3d and hover3d."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from cfd.aircraft3d import OUT, OUT_H, REGIONS, RHO, SEL, U_CRUISE, WORK, read_coeffs, read_forces

G0 = 9.80665


def cruise_post():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in sorted(WORK.glob("cruise_a*")):
        a = float(case.name.split("_a")[1])
        c = read_coeffs(case)
        q = 0.5 * RHO * U_CRUISE**2
        ar = math.radians(a)
        drag_dir = np.array([math.cos(ar), 0, math.sin(ar)])
        reg = {r: float(2 * read_forces(case, r) @ drag_dir / q) for r in REGIONS}  # full aircraft drag area, m^2
        rows.append(dict(alpha=a, CL=c["Cl"], CD=c["Cd"], Cm=c["CmPitch"], CL_std=c["Cl_std"], iterations=c["iterations"],
                         drag_area_m2=reg))
    rows.sort(key=lambda r: r["alpha"])
    al = np.array([r["alpha"] for r in rows]); CL = np.array([r["CL"] for r in rows])
    CD = np.array([r["CD"] for r in rows]); Cm = np.array([r["Cm"] for r in rows])
    lin = np.abs(al) <= 4.5  # attached-flow points; 8 deg is unsteady on this mesh (reported separately)
    cla, cl0 = np.polyfit(al[lin], CL[lin], 1)
    k, cd0 = np.polyfit(CL[lin] ** 2, CD[lin], 1)
    cma, cm0 = np.polyfit(CL[lin], Cm[lin], 1)
    g = SEL["geometry"]
    c = SEL["design"]["chord_m"]
    AR = g["AR"]
    e = 1 / (math.pi * AR * k)
    x_np = g["x_cg_target"] - cma * c          # Cm about the CG: dCm/dCL = (x_cg - x_np)/c
    W = SEL["mass"]["total_kg"] * G0
    CL_cr = W / (0.5 * RHO * U_CRUISE**2 * g["S"])
    alpha_cr = (CL_cr - cl0) / cla
    i0 = int(np.argmin(np.abs(al - alpha_cr)))
    res = dict(polar=rows, cl_alpha_per_deg=cla, cl0=cl0, cd0_full_aircraft=cd0, k_induced=k, oswald_e=e,
               cm_cl=cma, cm0=cm0, x_neutral_point_m=x_np, x_cg_m=g["x_cg_target"],
               static_margin=(x_np - g["x_cg_target"]) / c, cruise_CL=CL_cr, cruise_alpha_deg=alpha_cr,
               cruise_LD=CL_cr / (cd0 + k * CL_cr**2),
               drag_area_by_region_m2=rows[i0]["drag_area_m2"], drag_area_alpha_deg=rows[i0]["alpha"],
               buildup_drag_area_m2=SEL["drag_buildup"], reference=dict(S=g["S"], c=c, V=U_CRUISE),
               mesh_cells=int((WORK / "mesh" / "log.checkMesh").read_text().split("cells:")[1].split()[0]))
    (OUT / "results.json").write_text(json.dumps(res, indent=1))
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.8), dpi=140)
    ax[0].plot(al, CL, "o-"); ax[0].set_xlabel("alpha (deg)"); ax[0].set_ylabel("CL")
    ax[1].plot(CD, CL, "o-"); ax[1].set_xlabel("CD"); ax[1].set_ylabel("CL")
    cl_f = np.linspace(CL.min(), CL.max(), 50); ax[1].plot(cd0 + k * cl_f**2, cl_f, "--", lw=0.8, label=f"fit CD0={cd0:.4f}, e={e:.2f}")
    ax[1].legend(frameon=False, fontsize=7)
    ax[2].plot(CL, Cm, "o-"); ax[2].set_xlabel("CL"); ax[2].set_ylabel("Cm about CG")
    for a_ in ax:
        a_.grid(alpha=.3)
    fig.suptitle(f"Full aircraft, OpenFOAM k-omega SST, 25 m/s, lift rotors stopped (static margin {res['static_margin'] * 100:.0f} % MAC)")
    fig.tight_layout(); fig.savefig(OUT / "polar.png"); plt.close(fig)
    reg = res["drag_area_by_region_m2"]
    bu = SEL["drag_buildup"]
    map_bu = {"wing": bu["wing"], "fuselage": bu["fuselage"] + bu["pusher_hub"], "tail": bu["tail"], "booms": bu["booms"],
              "rotors": bu["stopped_rotors"], "gear": bu["landing_gear"]}
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=140)
    xs = np.arange(len(REGIONS))
    ax.bar(xs - 0.2, [reg[r] for r in REGIONS], 0.4, label=f"CFD (alpha {res['drag_area_alpha_deg']:.0f} deg)")
    ax.bar(xs + 0.2, [map_bu[r] for r in REGIONS], 0.4, label="component build-up (sizing)")
    ax.set_xticks(xs, REGIONS); ax.set_ylabel("Drag area D/q (m^2)"); ax.grid(alpha=.3, axis="y"); ax.legend(frameon=False)
    ax.set_title("Drag breakdown by component")
    fig.tight_layout(); fig.savefig(OUT / "drag_breakdown.png"); plt.close(fig)
    print(json.dumps({k: v for k, v in res.items() if k not in ("polar", "buildup_drag_area_m2")}, indent=1))


def hover_post(from_iter: int = 500):
    """Hover download, averaged over the last iterations (steady RANS of a hover wake is not
    strictly steady; the band of the oscillation is reported)."""
    OUT_H.mkdir(parents=True, exist_ok=True)
    case = WORK / "hover"
    W = SEL["mass"]["total_kg"] * G0
    reg, band = {}, {}
    for r in REGIONS:
        f = sorted((case / "postProcessing" / f"forces_{r}").glob("*/force.dat"))[-1]
        arr = np.array([l.split() for l in f.read_text().splitlines() if l and not l.startswith("#")], float)
        arr = arr[arr[:, 0] >= from_iter, 3]
        reg[r] = float(2 * arr.mean())                  # full aircraft, vertical force (N), + up
        band[r] = [float(2 * arr.min()), float(2 * arr.max())]
    download = -sum(reg.values())
    T_total = 8 * SEL["mission"]["hover"]["thrust_per_rotor_n"]
    res = dict(vertical_force_by_region_n=reg, band_n=band, download_n=download,
               download_fraction_of_thrust=download / T_total, rotor_thrust_total_n=T_total, weight_n=W,
               model="uniform actuator disks (momentum sources, no swirl), steady k-omega SST, averaged over iterations 500-800",
               note="uniform disks load the hub region, so nacelle/motor download is an upper bound; real rotors unload the hub")
    # consequences for the hover performance at 10 % (typical measured) and at the CFD upper bound
    from e8lib.props import LiftRotor
    lift = LiftRotor.load()
    sens = {}
    for label, fr in (("no download", 0.0), ("10 % download", 0.10), ("CFD upper bound", download / T_total)):
        T = W * (1 + fr) / 8
        sens[label] = dict(thrust_per_rotor_n=T, hover_power_w=8 * lift.electrical_power_w(T) + 8.0,
                           thrust_to_weight=8 * lift.max_thrust_n / (W * (1 + fr)),
                           worst_rotor_out_frac=max(r["max_thrust_frac"] for r in SEL["rotor_out"]) * (1 + fr))
    res["hover_sensitivity"] = sens
    (OUT_H / "results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def post():
    cruise_post()
    if (WORK / "hover").exists():
        hover_post()
