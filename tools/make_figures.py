"""Figures for the documentation, generated from the analysis result files.

    python tools/make_figures.py      -> docs/img/*.png
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
C = {"of": "#1f6feb", "ref": "#222222", "exp": "#c2410c", "nf": "#2f9e44", "lm": "#8250df"}
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False})


def load(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def fig_naca0012():
    d = load("analysis/cfd/airfoil2d/naca0012_validation.json")
    if not d:
        return
    of = [r for r in d["openfoam"] if "Cl" in r]
    lad = d["tmr"]["Ladson_1988_tripped"]
    cfl = d["tmr"]["CFL3D_SST_897x257"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=140)
    for z, v in lad.items():
        ax[0].scatter(v["alpha"], v["Cl"], s=10, color=C["exp"], alpha=0.6, label=f"Ladson 1988 ({z})" if z == "80 grit" else None)
        ax[1].scatter(v["Cl"], v["Cd"], s=10, color=C["exp"], alpha=0.6)
    ax[0].plot(cfl["alpha"], cfl["Cl"], "s", color=C["ref"], label="CFL3D SST, 897x257 (NASA TMR)")
    ax[1].plot(cfl["Cl"], cfl["Cd"], "s", color=C["ref"])
    ax[0].plot([r["alpha"] for r in of], [r["Cl"] for r in of], "o-", color=C["of"], label="OpenFOAM SST, this work")
    ax[1].plot([r["Cl"] for r in of], [r["Cd"] for r in of], "o-", color=C["of"])
    nf = d["neuralfoil"]
    ax[0].plot(nf["alpha"], nf["Cl"], "--", color=C["nf"], label="NeuralFoil (free transition)")
    ax[0].set_xlabel("alpha (deg)"); ax[0].set_ylabel("CL"); ax[0].set_xlim(-1, 18); ax[0].set_ylim(-0.1, 1.8)
    ax[1].set_xlabel("CL"); ax[1].set_ylabel("CD"); ax[1].set_xlim(-0.1, 1.7); ax[1].set_ylim(0, 0.03)
    ax[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Validation: NACA 0012, Re = 6 million, fully turbulent")
    fig.tight_layout(); fig.savefig(IMG / "cfd_naca0012_validation.png"); plt.close(fig)


def fig_grid():
    d = load("analysis/cfd/airfoil2d/naca0012_grid_study.json")
    if not d:
        return
    N = np.array([r["cells"] for r in d], float)
    h = 1 / np.sqrt(N)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6), dpi=140)
    ax[0].plot(h, [r["Cl"] for r in d], "o-", color=C["of"]); ax[0].axhline(1.0778, color=C["ref"], ls="--", label="CFL3D 897x257")
    ax[1].plot(h, [r["Cd"] for r in d], "o-", color=C["of"]); ax[1].axhline(0.012362, color=C["ref"], ls="--")
    for a, lab in zip(ax, ("CL", "CD")):
        a.set_xlabel("1 / sqrt(cells)"); a.set_ylabel(lab); a.set_xlim(left=0)
    ax[0].legend(frameon=False)
    fig.suptitle("Grid convergence: NACA 0012, alpha = 10 deg")
    fig.tight_layout(); fig.savefig(IMG / "cfd_grid_study.png"); plt.close(fig)


def fig_4415():
    d = load("analysis/cfd/airfoil2d/naca4415_polar.json")
    if not d:
        return
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.8), dpi=140)
    for key, col, lab in (("sst", C["of"], "OpenFOAM SST (fully turbulent)"), ("transition", C["lm"], "OpenFOAM SST-LM (transition)")):
        rr = [r for r in d.get(key, []) if "Cl" in r]
        if not rr:
            continue
        a = [r["alpha"] for r in rr]
        ax[0].plot(a, [r["Cl"] for r in rr], "o-", color=col, label=lab)
        ax[1].plot([r["Cl"] for r in rr], [r["Cd"] for r in rr], "o-", color=col)
        ax[2].plot(a, [r["Cl"] / r["Cd"] for r in rr], "o-", color=col)
    nf = d["neuralfoil"]
    ax[0].plot(nf["alpha"], nf["Cl"], "--", color=C["nf"], label="NeuralFoil (XFOIL-trained)")
    ax[1].plot(nf["Cl"], nf["Cd"], "--", color=C["nf"])
    ax[2].plot(nf["alpha"], np.array(nf["Cl"]) / np.array(nf["Cd"]), "--", color=C["nf"])
    ax[0].set_xlabel("alpha (deg)"); ax[0].set_ylabel("CL"); ax[1].set_xlabel("CL"); ax[1].set_ylabel("CD")
    ax[2].set_xlabel("alpha (deg)"); ax[2].set_ylabel("L/D"); ax[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Wing section NACA 4415 at the cruise Reynolds number (25 m/s, c = 0.32 m)")
    fig.tight_layout(); fig.savefig(IMG / "cfd_naca4415_polar.png"); plt.close(fig)


def fig_fea():
    r = load("analysis/fea/airframe/results.json")
    p = load("analysis/fea/parts/summary.json")
    if r:
        ms = r["margins"]
        names = list(ms) + (list(p) if p else [])
        vals = [ms[k]["MS"] for k in ms] + ([p[k]["MS"] for k in p] if p else [])
        fig, ax = plt.subplots(figsize=(8, 4.2), dpi=140)
        cols = ["#2f9e44" if v >= 0.25 else ("#f59f00" if v >= 0 else "#e03131") for v in vals]
        y = np.arange(len(names))
        ax.barh(y, np.clip(vals, -1, 5), color=cols)
        ax.set_yticks(y, names); ax.invert_yaxis()
        ax.axvline(0, color="k", lw=0.8); ax.axvline(0.25, color="k", lw=0.6, ls="--")
        for yi, v in zip(y, vals):
            ax.text(min(v, 5) + 0.05, yi, f"{v:+.2f}", va="center", fontsize=7)
        ax.set_xlabel("Margin of safety at ultimate load (clipped at 5)")
        ax.set_title("Structural margins: global airframe model (top) and CalculiX part models")
        fig.tight_layout(); fig.savefig(IMG / "fea_margins.png"); plt.close(fig)
        modes = r["modes"]["modes"][:24]
        fig, ax = plt.subplots(figsize=(8, 3.8), dpi=140)
        rpm = np.linspace(0, 6500, 50)
        ax.plot(rpm, rpm / 60, color="#e03131", label="1P (rotor speed)")
        ax.plot(rpm, 2 * rpm / 60, color="#e03131", ls="--", label="2P (blade passage)")
        for m_ in modes:
            dom = max(m_["energy"], key=m_["energy"].get)
            ax.axhline(m_["f_hz"], color={"booms": "#1f6feb", "wing": "#2f9e44", "fuselage": "#8250df", "tail": "#f59f00"}.get(dom, "#999"),
                       lw=0.8, alpha=0.8)
        hv = r["modes"]["rotor_1P_hover_hz"] * 60
        ax.axvline(hv, color="k", lw=0.8, ls=":")
        ax.text(hv + 50, 5, "hover rpm", fontsize=7)
        ax.set_xlabel("Lift rotor speed (rpm)"); ax.set_ylabel("Frequency (Hz)"); ax.set_ylim(0, 220)
        ax.set_title("Campbell diagram: free-free airframe modes (blue boom, green wing, purple fuselage, orange tail)")
        ax.legend(frameon=False, fontsize=7, loc="upper left")
        fig.tight_layout(); fig.savefig(IMG / "fea_campbell.png"); plt.close(fig)
    if p:
        for k in p:
            src = ROOT / "analysis" / "fea" / "parts" / f"{k}.png"
            if src.exists():
                shutil.copy(src, IMG / f"fea_{k}.png")


def fig_copy():
    for rel, name in (("analysis/sizing/design_space.png", "sizing_design_space.png"),
                      ("analysis/sizing/cruise_polar.png", "sizing_cruise_polar.png"),
                      ("analysis/sizing/pareto.png", "sizing_pareto.png"),
                      ("analysis/sizing/design_space_cfd.png", "sizing_design_space_cfd.png"),
                      ("analysis/sizing/cruise_polar_cfd.png", "sizing_cruise_polar_cfd.png"),
                      ("analysis/sizing/pareto_cfd.png", "sizing_pareto_cfd.png"),
                      ("analysis/propeller/bemt_vs_apc.png", "prop_bemt_vs_apc.png"),
                      ("analysis/propeller/printed_blade_stress.png", "prop_printed_blade_stress.png"),
                      ("fullscale/results/range_vs_speed.png", "fullscale_range_vs_speed.png")):
        src = ROOT / rel
        if src.exists():
            shutil.copy(src, IMG / name)
    for f in (ROOT / "analysis" / "cfd" / "cruise3d").glob("*.png"):
        shutil.copy(f, IMG / f"cfd3d_{f.name}")
    for f in (ROOT / "analysis" / "cfd" / "hover3d").glob("*.png"):
        shutil.copy(f, IMG / f"hover_{f.name}")


RESULTS = {"design/selected_design.json": "selected_design.json", "analysis/cfd/airfoil2d/naca0012_validation.json": "naca0012_validation.json",
           "analysis/cfd/cruise3d/results.json": "cruise3d.json", "analysis/cfd/cruise3d/fine_mesh.json": "cruise3d_fine_mesh.json", "analysis/cfd/hover3d/results.json": "hover3d.json",
           "analysis/fea/airframe/results.json": "airframe.json", "analysis/fea/parts/summary.json": "parts_fea.json",
           "analysis/fea/validation/validation.json": "validation.json", "analysis/propeller/results.json": "propeller.json",
           "fullscale/results/results.json": "fullscale.json"}


def copy_results():
    """Result files for the analysis web page (served next to it, works offline)."""
    dst = ROOT / "docs" / "data" / "results"
    dst.mkdir(parents=True, exist_ok=True)
    for src, name in RESULTS.items():
        if (ROOT / src).exists():
            shutil.copy(ROOT / src, dst / name)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    copy_results()
    fig_naca0012()
    fig_grid()
    fig_4415()
    fig_fea()
    fig_copy()
    print(sorted(p.name for p in IMG.glob("*.png")))


if __name__ == "__main__":
    main()
