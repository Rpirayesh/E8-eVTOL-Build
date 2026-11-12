"""Full-aircraft 3-D RANS (OpenFOAM simpleFoam, k-omega SST) on a snappyHexMesh half model.

    python tools/cfd/aircraft3d.py geometry          # export region STLs (m)
    python tools/cfd/aircraft3d.py mesh  [--level N] # blockMesh + snappyHexMesh (parallel)
    python tools/cfd/aircraft3d.py cruise            # angle-of-attack sweep, stopped lift rotors
    python tools/cfd/aircraft3d.py hover             # eight rotorDisk actuators at hover thrust
    python tools/cfd/aircraft3d.py post              # coefficients, plots, results.json

The symmetry plane is y = 0 (starboard half).  Rotor spin directions are mirrored
port/starboard, so the mean flow is symmetric.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".cache" / "cfd3d"
OUT = ROOT / "analysis" / "cfd" / "cruise3d"
OUT_H = ROOT / "analysis" / "cfd" / "hover3d"
FOAM_ENV = Path.home() / "tools" / "foamenv.sh"
SEL = json.loads((ROOT / "design" / "selected_design.json").read_text())

U_CRUISE = 25.0
NU = 1.46e-5
RHO = 1.225
REGIONS = ["fuselage", "wing", "tail", "booms", "rotors", "gear"]
LEVELS = {"fuselage": (4, 5), "wing": (5, 6), "tail": (5, 6), "booms": (4, 5), "rotors": (5, 6), "gear": (4, 5)}
HDR = "FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n\n"


def sh(cmd: str, cwd: Path, log: str) -> int:
    full = f"source {FOAM_ENV} && cd {cwd} && {cmd} > {log} 2>&1"
    return subprocess.run(["bash", "-c", full]).returncode


def wfile(case: Path, rel: str, cls: str, obj: str, body: str):
    p = case / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(HDR.format(cls=cls, obj=obj) + body)


# ----------------------------------------------------------------------------- geometry
def export_geometry():
    import trimesh
    from cad import oml
    tri = WORK / "geometry"
    tri.mkdir(parents=True, exist_ok=True)
    for name, fn in oml.REGIONS.items():
        solid = fn()
        verts, faces = solid.tessellate(0.2, 0.15)
        v = np.array([[p.X, p.Y, p.Z] for p in verts]) / 1000.0  # mm -> m
        m = trimesh.Trimesh(v, np.array(faces), process=True)
        if not m.is_watertight:
            m.merge_vertices(merge_tex=True, merge_norm=True)
            trimesh.repair.fill_holes(m)
            trimesh.repair.fix_normals(m)
        m.export(tri / f"{name}.stl")
        print(name, len(m.faces), "faces, watertight:", m.is_watertight)


# ----------------------------------------------------------------------------- mesh
def write_mesh_dicts(case: Path, base: float = 0.25, extra: int = 0):
    xmin, xmax, ymin, ymax, zmin, zmax = -4.0, 8.0, 0.0, 4.0, -4.0, 4.0
    nx, ny, nz = (round((xmax - xmin) / base), round((ymax - ymin) / base), round((zmax - zmin) / base))
    wfile(case, "system/blockMeshDict", "dictionary", "blockMeshDict", f"""convertToMeters 1;
vertices ( ({xmin} {ymin} {zmin}) ({xmax} {ymin} {zmin}) ({xmax} {ymax} {zmin}) ({xmin} {ymax} {zmin})
           ({xmin} {ymin} {zmax}) ({xmax} {ymin} {zmax}) ({xmax} {ymax} {zmax}) ({xmin} {ymax} {zmax}) );
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
boundary
(
    farfield {{ type patch; faces ( (0 4 7 3) (1 2 6 5) (3 7 6 2) (0 3 2 1) (4 5 6 7) ); }}
    symmetry {{ type symmetryPlane; faces ( (0 1 5 4) ); }}
);
""")
    lv = {r: (a + extra, b + extra) for r, (a, b) in LEVELS.items()}
    feats = "\n".join(f'        {{ file "{r}.eMesh"; level {lv[r][1]}; }}' for r in REGIONS)
    geo = "\n".join(f'    {r}.stl {{ type triSurfaceMesh; name {r}; }}' for r in REGIONS)
    ref = "\n".join(f"        {r} {{ level ({lv[r][0]} {lv[r][1]}); patchInfo {{ type wall; inGroups (aircraft); }} }}" for r in REGIONS)
    wfile(case, "system/snappyHexMeshDict", "dictionary", "snappyHexMeshDict", f"""castellatedMesh true; snap true; addLayers true;
geometry
{{
{geo}
    nearBox {{ type box; min (-1.3 0 -0.6); max (2.2 1.8 0.5); }}
    wakeBox {{ type box; min (-0.2 0 -0.45); max (3.5 1.7 0.35); }}
    rotorBox {{ type box; min (-1.3 0.25 -0.05); max (1.45 0.95 0.2); }}
}}
castellatedMeshControls
{{
    maxLocalCells 4000000; maxGlobalCells 30000000; minRefinementCells 10; maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features
    (
{feats}
    );
    refinementSurfaces
    {{
{ref}
    }}
    resolveFeatureAngle 30;
    refinementRegions
    {{
        nearBox {{ mode inside; levels ((1E15 {2 + extra})); }}
        wakeBox {{ mode inside; levels ((1E15 {3 + extra})); }}
        rotorBox {{ mode inside; levels ((1E15 {3 + extra})); }}
    }}
    locationInMesh (-3.1 2.1 2.3);
    allowFreeStandingZoneFaces true;
}}
snapControls {{ nSmoothPatch 3; tolerance 2.0; nSolveIter 50; nRelaxIter 5; nFeatureSnapIter 10;
               implicitFeatureSnap false; explicitFeatureSnap true; multiRegionFeatureSnap true; }}
addLayersControls
{{
    relativeSizes true;
    layers {{ "(fuselage|wing|tail|booms)" {{ nSurfaceLayers 3; }} "(rotors|gear)" {{ nSurfaceLayers 2; }} }}
    expansionRatio 1.25; finalLayerThickness 0.4; minThickness 0.08; nGrow 0;
    featureAngle 130; slipFeatureAngle 30; nRelaxIter 3; nSmoothSurfaceNormals 1; nSmoothNormals 3;
    nSmoothThickness 10; maxFaceThicknessRatio 0.5; maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90;
    nBufferCellsNoExtrude 0; nLayerIter 50;
}}
meshQualityControls
{{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-13;
    minTetQuality 1e-15; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05;
    minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75;
    relaxed {{ maxNonOrtho 75; }}
}}
mergeTolerance 1e-6;
""")
    wfile(case, "system/surfaceFeatureExtractDict", "dictionary", "surfaceFeatureExtractDict",
          "\n".join(f"{r}.stl {{ extractionMethod extractFromSurface; extractFromSurfaceCoeffs {{ includedAngle 150; }} writeObj no; }}" for r in REGIONS) + "\n")


def write_decompose(case: Path, n: int):
    wfile(case, "system/decomposeParDict", "dictionary", "decomposeParDict", f"numberOfSubdomains {n};\nmethod scotch;\n")


def write_solver_files(case: Path, alpha_deg: float, iters: int, U: float = U_CRUISE, hover: bool = False):
    a = math.radians(alpha_deg)
    Ux, Uz = U * math.cos(a), U * math.sin(a)
    if hover:
        Ux, Uz = 0.0, 0.0
    Uref = max(U, 1.0)
    tu, vr = 0.003, 1.0
    k = 1.5 * (Uref * tu) ** 2
    om = k / (vr * NU)
    farU = (f"type freestreamVelocity; freestreamValue uniform ({Ux} 0 {Uz});" if not hover else
            "type pressureInletOutletVelocity; value uniform (0 0 0);")
    farP = ("type freestreamPressure; freestreamValue uniform 0;" if not hover else "type totalPressure; p0 uniform 0; value uniform 0;")
    sym = "    symmetry { type symmetryPlane; }\n"
    wfile(case, "0/U", "volVectorField", "U", f"dimensions [0 1 -1 0 0 0 0];\ninternalField uniform ({Ux} 0 {Uz});\nboundaryField\n{{\n"
          f"    farfield {{ {farU} }}\n    aircraft {{ type noSlip; }}\n{sym}}}\n")
    wfile(case, "0/p", "volScalarField", "p", f"dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{{\n"
          f"    farfield {{ {farP} }}\n    aircraft {{ type zeroGradient; }}\n{sym}}}\n")
    wfile(case, "0/k", "volScalarField", "k", f"dimensions [0 2 -2 0 0 0 0];\ninternalField uniform {k};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {k}; value uniform {k}; }}\n"
          f"    aircraft {{ type kqRWallFunction; value uniform {k}; }}\n{sym}}}\n")
    wfile(case, "0/omega", "volScalarField", "omega", f"dimensions [0 0 -1 0 0 0 0];\ninternalField uniform {om};\nboundaryField\n{{\n"
          f"    farfield {{ type inletOutlet; inletValue uniform {om}; value uniform {om}; }}\n"
          f"    aircraft {{ type omegaWallFunction; value uniform {om}; }}\n{sym}}}\n")
    wfile(case, "0/nut", "volScalarField", "nut", "dimensions [0 2 -1 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
          "    farfield { type calculated; value uniform 0; }\n    aircraft { type nutUSpaldingWallFunction; value uniform 0; }\n" + sym + "}\n")
    wfile(case, "constant/transportProperties", "dictionary", "transportProperties", f"transportModel Newtonian;\nnu {NU};\n")
    wfile(case, "constant/turbulenceProperties", "dictionary", "turbulenceProperties",
          "simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs off; }\n")
    g = SEL["geometry"]
    S_half = g["S"] / 2
    c = SEL["design"]["chord_m"]
    xcg = g["x_cg_target"]
    lift = (-math.sin(a), 0, math.cos(a))
    drag = (math.cos(a), 0, math.sin(a))
    if hover:
        lift, drag = (0, 0, 1), (1, 0, 0)
    per_region = "\n".join(f"""    forces_{r} {{ type forces; libs (forces); patches ({r}); rho rhoInf; rhoInf {RHO}; CofR ({xcg} 0 0); writeControl timeStep; writeInterval 10; }}"""
                           for r in REGIONS)
    wfile(case, "system/controlDict", "dictionary", "controlDict", f"""application simpleFoam;
startFrom latestTime; startTime 0; stopAt endTime; endTime {iters}; deltaT 1;
writeControl timeStep; writeInterval {iters}; purgeWrite 1; writeFormat binary; writePrecision 8; runTimeModifiable true;
functions
{{
    coeffs
    {{
        type forceCoeffs; libs (forces); writeControl timeStep; writeInterval 1;
        patches (aircraft); rho rhoInf; rhoInf {RHO}; CofR ({xcg} 0 0);
        liftDir ({lift[0]} {lift[1]} {lift[2]}); dragDir ({drag[0]} {drag[1]} {drag[2]}); pitchAxis (0 1 0);
        magUInf {Uref}; lRef {c}; Aref {S_half};
    }}
{per_region}
    yPlus {{ type yPlus; libs (fieldFunctionObjects); writeControl writeTime; }}
}}
""")
    wfile(case, "system/fvSchemes", "dictionary", "fvSchemes", """ddtSchemes { default steadyState; }
gradSchemes { default cellLimited Gauss linear 1; grad(U) cellLimited Gauss linear 1; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) bounded Gauss upwind;
    div(phi,omega) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited 0.5; }
wallDist { method meshWave; }
""")
    wfile(case, "system/fvSolution", "dictionary", "fvSolution", """solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; nCellsInCoarsestLevel 50; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }
}
SIMPLE { nNonOrthogonalCorrectors 1; consistent yes; }
relaxationFactors { equations { U 0.7; ".*" 0.5; } fields { p 0.7; } }
""")


def mesh(nproc: int = 20, name: str = "mesh", extra: int = 0):
    case = WORK / name
    if case.exists():
        shutil.rmtree(case)
    (case / "constant" / "triSurface").mkdir(parents=True)
    for r in REGIONS:
        shutil.copy(WORK / "geometry" / f"{r}.stl", case / "constant" / "triSurface" / f"{r}.stl")
    write_mesh_dicts(case, extra=extra)
    write_decompose(case, nproc)
    write_solver_files(case, 0.0, 1)
    assert sh("blockMesh", case, "log.blockMesh") == 0
    assert sh("surfaceFeatureExtract", case, "log.sfe") == 0
    assert sh("decomposePar -force", case, "log.decompose") == 0
    rc = sh(f"mpirun -np {nproc} snappyHexMesh -overwrite -parallel", case, "log.snappy")
    assert rc == 0, "snappyHexMesh failed (see log.snappy)"
    assert sh("reconstructParMesh -constant", case, "log.reconstruct") == 0
    sh("checkMesh -constant", case, "log.checkMesh")
    print((case / "log.checkMesh").read_text()[-1500:])


def run_case(name: str, alpha: float, iters: int, nproc: int, hover: bool = False, fvoptions: str | None = None,
             mesh_name: str = "mesh") -> Path:
    src = WORK / mesh_name
    case = WORK / name
    if case.exists():
        shutil.rmtree(case)
    (case / "constant").mkdir(parents=True)
    shutil.copytree(src / "constant" / "polyMesh", case / "constant" / "polyMesh")
    write_solver_files(case, alpha, iters, hover=hover)
    if fvoptions:
        wfile(case, "constant/fvOptions", "dictionary", "fvOptions", fvoptions)
    write_decompose(case, nproc)
    sh("decomposePar -force", case, "log.decompose")
    sh(f"mpirun -np {nproc} potentialFoam -parallel -writephi", case, "log.potential") if not hover else None
    sh(f"mpirun -np {nproc} simpleFoam -parallel", case, "log.simpleFoam")
    return case


def read_coeffs(case: Path, avg: int = 200) -> dict:
    f = sorted((case / "postProcessing" / "coeffs").glob("*/coefficient.dat"))[-1]
    lines = f.read_text().splitlines()
    hdr = [l for l in lines if l.startswith("#")][-1].lstrip("#").split()
    arr = np.array([l.split() for l in lines if l and not l.startswith("#")], float)
    col = {h: i for i, h in enumerate(hdr)}
    t = arr[-avg:]
    return {k: float(t[:, col[k]].mean()) for k in ("Cd", "Cl", "CmPitch")} | {
        "Cl_std": float(t[:, col["Cl"]].std()), "Cd_std": float(t[:, col["Cd"]].std()), "iterations": int(arr[-1, 0])}


def read_forces(case: Path, region: str, avg: int = 20) -> np.ndarray:
    f = sorted((case / "postProcessing" / f"forces_{region}").glob("*/force.dat"))[-1]
    arr = np.array([l.split() for l in f.read_text().splitlines() if l and not l.startswith("#")], float)
    return arr[-avg:, 1:4].mean(axis=0)  # total force (x, y, z), N, half model


def cruise(alphas, iters: int, nproc_each: int, jobs: int):
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(lambda a: run_case(f"cruise_a{a:+.0f}", a, iters, nproc_each), alphas))


def hover_fvoptions() -> str:
    """Starboard lift rotors as uniform actuator disks: a momentum sink of exactly the hover
    thrust per rotor (N / rho) distributed over each disk's cells.  Swirl is neglected."""
    thrust = SEL["mission"]["hover"]["thrust_per_rotor_n"]
    blocks = []
    for (x, y) in [((r["x"] + SEL["geometry"]["x_cg_target"]), r["y"]) for r in SEL["layout"]]:
        if y < 0:
            continue
        name = f"rotor_{x:+.3f}".replace(".", "p").replace("+", "P").replace("-", "M")
        blocks.append(f"""{name}
{{
    type vectorSemiImplicitSource; selectionMode cellZone; cellZone {name}; volumeMode absolute;
    sources {{ U {{ explicit (0 0 {-thrust / RHO:.6f}); implicit 0; }} }}
}}""")
    return "\n".join(blocks)


def rotor_topo(case: Path):
    R = 0.2286
    seat_z = 0.0365 + 0.036
    actions = []
    for (x, y) in [((r["x"] + SEL["geometry"]["x_cg_target"]), r["y"]) for r in SEL["layout"]]:
        if y < 0:
            continue
        name = f"rotor_{x:+.3f}".replace(".", "p").replace("+", "P").replace("-", "M")
        actions.append(f"""    {{ name {name}c; type cellSet; action new; source cylinderToCell; p1 ({x} {y} {seat_z - 0.012}); p2 ({x} {y} {seat_z + 0.012}); radius {R}; }}
    {{ name {name}; type cellZoneSet; action new; source setToCellZone; set {name}c; }}""")
    wfile(case, "system/topoSetDict", "dictionary", "topoSetDict", "actions\n(\n" + "\n".join(actions) + "\n);\n")
    sh("topoSet", case, "log.topoSet")


def hover(iters: int, nproc: int):
    src = WORK / "mesh"
    case = WORK / "hover"
    if case.exists():
        shutil.rmtree(case)
    (case / "constant").mkdir(parents=True)
    shutil.copytree(src / "constant" / "polyMesh", case / "constant" / "polyMesh")
    write_solver_files(case, 0.0, iters, hover=True)
    rotor_topo(case)
    wfile(case, "constant/fvOptions", "dictionary", "fvOptions", hover_fvoptions())
    write_decompose(case, nproc)
    sh("decomposePar -force", case, "log.decompose")
    sh(f"mpirun -np {nproc} simpleFoam -parallel", case, "log.simpleFoam")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["geometry", "mesh", "mesh-fine", "cruise", "cruise-fine", "hover", "post"])
    ap.add_argument("--iters", type=int, default=1500)
    args = ap.parse_args()
    if args.what == "geometry":
        export_geometry()
    elif args.what == "mesh":
        mesh()
    elif args.what == "mesh-fine":
        mesh(name="mesh_fine", extra=1)
    elif args.what == "cruise-fine":
        with ThreadPoolExecutor(2) as ex:
            list(ex.map(lambda a: run_case(f"fine_a{a:+.0f}", a, args.iters, 10, mesh_name="mesh_fine"), [0, 8]))
    elif args.what == "cruise":
        cruise([-4, 0, 4, 8], args.iters, 5, 4)
    elif args.what == "hover":
        hover(args.iters, 20)
    elif args.what == "post":
        from cfd.post3d import post
        post()


if __name__ == "__main__":
    main()
