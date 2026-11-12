"""2-D airfoil polars with OpenFOAM simpleFoam on a structured O-grid.

    python tools/cfd/airfoil2d.py validate            # NACA 0012, Re 6e6 vs NASA TMR / Ladson
    python tools/cfd/airfoil2d.py wing                # NACA 4415, Re ~5e5 (wing cruise) SST + transition
    python tools/cfd/airfoil2d.py mesh-study          # NACA 0012 grid convergence at alpha 10

Each angle of attack is an independent case; cases run concurrently.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfd.ogrid import build_ogrid_march, inverted_cells, resample_surface, write_polymesh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "cfd" / "airfoil2d"
RUNS = ROOT / ".cache" / "cfd2d"
FOAM_ENV = Path.home() / "tools" / "foamenv.sh"


def tmr_naca0012(n: int = 400) -> np.ndarray:
    """NASA TMR sharp-trailing-edge NACA 0012 (chord 1)."""
    b = np.linspace(0, np.pi, n)
    x = (1 - np.cos(b)) / 2
    y = 0.594689181 * (0.298222773 * np.sqrt(x) - 0.127125232 * x - 0.357907906 * x**2
                       + 0.291984971 * x**3 - 0.105174606 * x**4)
    up = np.column_stack([x[::-1], y[::-1]])
    lo = np.column_stack([x[1:-1], -y[1:-1]])
    return np.vstack([up, lo])


def naca4_closed(code: str, chord: float, n: int = 300) -> np.ndarray:
    """NACA 4-digit with the closed-TE thickness coefficient (-0.1036); the printed
    wing's 0.6 mm (0.2 % c) trailing-edge thickness is omitted for the 2-D CFD."""
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    x = (1 - np.cos(np.linspace(0, np.pi, n))) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    if m:
        yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2))
        dy = np.where(x < p, 2 * m / p**2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    else:
        yc = dy = np.zeros_like(x)
    th = np.arctan(dy)
    up = np.column_stack([x - yt * np.sin(th), yc + yt * np.cos(th)])[::-1]
    lo = np.column_stack([x + yt * np.sin(th), yc - yt * np.cos(th)])[1:-1]
    return np.vstack([up, lo]) * chord


HDR = "FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n\n"


def write_case(case: Path, U: float, alpha: float, nu: float, chord: float, dz: float,
               model: str, iters: int, tu: float = 0.0008, visc_ratio: float = 0.2):
    a = math.radians(alpha)
    Ux, Uy = U * math.cos(a), U * math.sin(a)
    k = 1.5 * (U * tu) ** 2
    om = k / (visc_ratio * nu)
    (case / "0").mkdir(parents=True, exist_ok=True)
    (case / "system").mkdir(exist_ok=True)
    (case / "constant").mkdir(exist_ok=True)
    w = lambda p, cls, obj, body: (case / p).write_text(HDR.format(cls=cls, obj=obj) + body)
    empty = "    \"(front|back)\" { type empty; }\n"
    w("0/U", "volVectorField", "U", f"dimensions [0 1 -1 0 0 0 0];\ninternalField uniform ({Ux} {Uy} 0);\nboundaryField\n{{\n"
      f"    farfield {{ type freestreamVelocity; freestreamValue uniform ({Ux} {Uy} 0); }}\n"
      f"    airfoil {{ type noSlip; }}\n{empty}}}\n")
    w("0/p", "volScalarField", "p", "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
      "    farfield { type freestreamPressure; freestreamValue uniform 0; }\n"
      f"    airfoil {{ type zeroGradient; }}\n{empty}}}\n")
    w("0/k", "volScalarField", "k", f"dimensions [0 2 -2 0 0 0 0];\ninternalField uniform {k};\nboundaryField\n{{\n"
      f"    farfield {{ type inletOutlet; inletValue uniform {k}; value uniform {k}; }}\n"
      f"    airfoil {{ type kLowReWallFunction; value uniform 1e-14; }}\n{empty}}}\n")
    w("0/omega", "volScalarField", "omega", f"dimensions [0 0 -1 0 0 0 0];\ninternalField uniform {om};\nboundaryField\n{{\n"
      f"    farfield {{ type inletOutlet; inletValue uniform {om}; value uniform {om}; }}\n"
      f"    airfoil {{ type omegaWallFunction; value uniform {om}; }}\n{empty}}}\n")
    w("0/nut", "volScalarField", "nut", "dimensions [0 2 -1 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
      "    farfield { type calculated; value uniform 0; }\n"
      f"    airfoil {{ type nutLowReWallFunction; value uniform 0; }}\n{empty}}}\n")
    if model == "kOmegaSSTLM":
        # Langtry-Menter correlations for the free-stream transition onset Reynolds number
        tu_pct = tu * 100
        re_theta = 1173.51 - 589.428 * tu_pct + 0.2196 / tu_pct**2 if tu_pct <= 1.3 else 331.5 * (tu_pct - 0.5658) ** -0.671
        w("0/ReThetat", "volScalarField", "ReThetat", f"dimensions [0 0 0 0 0 0 0];\ninternalField uniform {re_theta};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {re_theta}; value uniform {re_theta}; }}\n"
          f"    airfoil {{ type zeroGradient; }}\n{empty}}}\n")
        w("0/gammaInt", "volScalarField", "gammaInt", "dimensions [0 0 0 0 0 0 0];\ninternalField uniform 1;\nboundaryField\n{\n"
          "    farfield { type inletOutlet; inletValue uniform 1; value uniform 1; }\n"
          f"    airfoil {{ type zeroGradient; }}\n{empty}}}\n")
    w("constant/transportProperties", "dictionary", "transportProperties", f"transportModel Newtonian;\nnu {nu};\n")
    w("constant/turbulenceProperties", "dictionary", "turbulenceProperties",
      f"simulationType RAS;\nRAS\n{{\n    RASModel {model};\n    turbulence on;\n    printCoeffs off;\n}}\n")
    lift = (-math.sin(a), math.cos(a), 0)
    drag = (math.cos(a), math.sin(a), 0)
    w("system/controlDict", "dictionary", "controlDict", f"""application simpleFoam;
startFrom startTime; startTime 0; stopAt endTime; endTime {iters}; deltaT 1;
writeControl timeStep; writeInterval {iters}; purgeWrite 1; writeFormat binary; writePrecision 8; runTimeModifiable false;
functions
{{
    forceCoeffs
    {{
        type forceCoeffs; libs (forces); writeControl timeStep; writeInterval 1;
        patches (airfoil); rho rhoInf; rhoInf 1; CofR ({0.25 * chord} 0 0);
        liftDir ({lift[0]} {lift[1]} 0); dragDir ({drag[0]} {drag[1]} 0); pitchAxis (0 0 1);
        magUInf {U}; lRef {chord}; Aref {chord * dz};
    }}
    yPlus {{ type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }}
    wallShearStress {{ type wallShearStress; libs (fieldFunctionObjects); patches (airfoil); writeControl writeTime; }}
}}
""")
    w("system/fvSchemes", "dictionary", "fvSchemes", """ddtSchemes { default steadyState; }
gradSchemes { default cellLimited Gauss linear 1; grad(U) cellLimited Gauss linear 1; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) bounded Gauss limitedLinear 1;
    div(phi,omega) bounded Gauss limitedLinear 1;
    div(phi,ReThetat) bounded Gauss limitedLinear 1;
    div(phi,gammaInt) bounded Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
wallDist { method meshWave; }
""")
    w("system/fvSolution", "dictionary", "fvSolution", """solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-9; relTol 0.05; }
    "(U|k|omega|ReThetat|gammaInt)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0.1; }
}
SIMPLE { nNonOrthogonalCorrectors 0; consistent yes; residualControl { p 1e-7; U 1e-8; } }
relaxationFactors { equations { U 0.85; ".*" 0.6; } fields { p 1; } }
""")


def run(case: Path, log: str = "log.simpleFoam") -> None:
    cmd = f"source {FOAM_ENV} && cd {case} && checkMesh > log.checkMesh 2>&1; simpleFoam > {log} 2>&1"
    subprocess.run(["bash", "-c", cmd], check=False)


def coeffs(case: Path, avg: int = 400) -> dict:
    f = case / "postProcessing" / "forceCoeffs" / "0" / "coefficient.dat"
    rows = [l.split() for l in f.read_text().splitlines() if l and not l.startswith("#")]
    hdr = [l for l in f.read_text().splitlines() if l.startswith("#")][-1].lstrip("#").split()
    arr = np.array(rows, float)
    col = {h: i for i, h in enumerate(hdr)}
    tail = arr[-avg:]
    out = {k: float(tail[:, col[k]].mean()) for k in ("Cd", "Cl", "CmPitch")}
    out["Cl_std"] = float(tail[:, col["Cl"]].std())
    out["iterations"] = int(arr[-1, 0])
    return out


def polar(foil_pts: np.ndarray, chord: float, U: float, nu: float, alphas, model: str, tag: str,
          ni: int = 320, nj: int = 160, ds: float = None, iters: int = 6000, jobs: int = 10, R_far: float = 50,
          tu: float = 0.0008, visc_ratio: float = 0.2) -> list:
    re = U * chord / nu
    ds = ds or chord * 1.0 / (re * 0.035) * 0.8  # target y+ < 1
    surf = resample_surface(foil_pts, ni)
    X = build_ogrid_march(surf, nj, ds, R_far, chord)
    assert inverted_cells(X) == 0, f"{tag}: folded grid"
    base = RUNS / tag
    if base.exists():
        shutil.rmtree(base)
    cases = []
    for a in alphas:
        case = base / f"a{a:+05.1f}"
        info = write_polymesh(X, case, dz=0.01 * chord)
        write_case(case, U, a, nu, chord, 0.01 * chord, model, iters, tu, visc_ratio)
        cases.append((a, case))
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(lambda ac: run(ac[1]), cases))
    res = []
    for a, case in cases:
        try:
            c = coeffs(case)
        except Exception as e:  # noqa: BLE001
            c = {"error": str(e)}
        mesh_ok = "Mesh OK" in (case / "log.checkMesh").read_text()
        res.append(dict(alpha=a, model=model, Re=re, cells=info["cells"], mesh_ok=mesh_ok, **c))
        print(tag, res[-1])
    return res


REF = OUT / "reference"  # NASA TMR files (mirror: https://tmbwg.github.io/turbmodels/naca0012_val.html)


def read_tecplot_zones(path: Path) -> dict:
    zones, cur = {}, None
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.lower().startswith("zone"):
            cur = line.split("=")[-1].strip().strip('"')
            zones[cur] = []
        elif line and line[0] in "-.0123456789":
            zones.setdefault(cur or "data", []).append([float(v) for v in line.split()])
    return {k: {"alpha": [r[0] for r in v], "Cl": [r[1] for r in v], "Cd": [r[2] for r in v]} for k, v in zones.items()}


def tmr_reference() -> dict:
    return {"source": "NASA Turbulence Modeling Resource 2DN00, https://turbmodels.larc.nasa.gov/naca0012_val.html",
            "CFL3D_SST_897x257": read_tecplot_zones(REF / "CLCD_CFL3D_SST.dat")["data"],
            "Ladson_1988_tripped": read_tecplot_zones(REF / "CLCD_Ladson_expdata.dat")}


def neuralfoil_polar(name_or_coords, alphas, re):
    import aerosandbox as asb
    import neuralfoil as nf
    af = asb.Airfoil(name_or_coords) if isinstance(name_or_coords, str) else asb.Airfoil(coordinates=name_or_coords)
    r = nf.get_aero_from_airfoil(af, alpha=np.array(alphas, float), Re=re, model_size="xlarge")
    return {"alpha": list(map(float, alphas)), "Cl": r["CL"].tolist(), "Cd": r["CD"].tolist(), "Cm": r["CM"].tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["validate", "wing", "mesh-study", "tail"])
    ap.add_argument("--jobs", type=int, default=10)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.what == "validate":
        alphas = [0, 4, 8, 10, 12, 15]
        res = polar(tmr_naca0012(), 1.0, 1.0, 1 / 6e6, alphas, "kOmegaSST", "naca0012_sst", jobs=args.jobs, iters=8000,
                    tu=0.00052, visc_ratio=0.009)
        nfp = neuralfoil_polar("naca0012", alphas, 6e6)
        (OUT / "naca0012_validation.json").write_text(json.dumps(dict(openfoam=res, tmr=tmr_reference(), neuralfoil=nfp), indent=1))
    elif args.what == "mesh-study":
        res = []
        for ni, nj, tag in ((160, 80, "coarse"), (240, 120, "medium"), (320, 160, "fine"), (480, 240, "extra-fine")):
            r = polar(tmr_naca0012(), 1.0, 1.0, 1 / 6e6, [10], "kOmegaSST", f"naca0012_grid_{tag}", ni=ni, nj=nj, jobs=1,
                      iters=10000, tu=0.00052, visc_ratio=0.009)
            res.append(dict(grid=tag, ni=ni, nj=nj, **r[0]))
        (OUT / "naca0012_grid_study.json").write_text(json.dumps(res, indent=1))
    elif args.what == "wing":
        chord, U, nu = 0.30, 25.0, 1.46e-5
        foil = naca4_closed("4415", chord)
        alphas = [-4, -2, 0, 2, 4, 6, 8, 10, 12, 14, 16]
        sst = polar(foil, chord, U, nu, alphas, "kOmegaSST", "naca4415_sst", jobs=args.jobs)
        lm = polar(foil, chord, U, nu, alphas, "kOmegaSSTLM", "naca4415_lm", jobs=args.jobs, iters=12000)
        nfp = neuralfoil_polar(foil / chord, alphas, U * chord / nu)
        (OUT / "naca4415_polar.json").write_text(json.dumps(dict(sst=sst, transition=lm, neuralfoil=nfp), indent=1))
    elif args.what == "tail":
        chord, U, nu = 0.11, 25.0, 1.46e-5
        foil = naca4_closed("0010", chord)
        alphas = [0, 4, 8, 12]
        sst = polar(foil, chord, U, nu, alphas, "kOmegaSST", "naca0010_sst", jobs=args.jobs)
        nfp = neuralfoil_polar(foil / chord, alphas, U * chord / nu)
        (OUT / "naca0010_polar.json").write_text(json.dumps(dict(sst=sst, neuralfoil=nfp), indent=1))


if __name__ == "__main__":
    main()
