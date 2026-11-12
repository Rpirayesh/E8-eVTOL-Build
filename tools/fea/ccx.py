"""CalculiX solid FEA of individual parts (gmsh C3D10 mesh -> ccx -> von Mises).

Loads are applied as consistent nodal forces of uniform tractions on selected
boundary faces; supports fix all translations of selected boundary nodes.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from build123d import export_step

FOAM_ENV = Path.home() / "tools" / "foamenv.sh"   # same conda env holds ccx and gmsh
TET_FACES = ((0, 1, 2, 4, 5, 6), (0, 1, 3, 4, 8, 7), (1, 2, 3, 5, 9, 8), (0, 2, 3, 6, 9, 7))  # corner, corner, corner, mid, mid, mid


@dataclass
class Material:
    name: str
    E: float        # MPa
    nu: float
    rho: float      # t/mm^3
    allow: float    # MPa, ultimate design allowable (von Mises)
    note: str = ""


MATERIALS = {
    "6061-T6": Material("6061-T6", 68900, 0.33, 2.70e-9, 240.0, "yield 276 MPa; allowable = 0.87 x yield"),
    "PA6-CF": Material("PA6-CF (printed)", 3500, 0.35, 1.15e-9, 25.0, "dry XY ~70 MPa; allowable includes layer-adhesion, moisture, creep and fatigue knock-downs"),
    "PETG": Material("PETG (printed)", 2000, 0.38, 1.27e-9, 14.0, "XY ~45 MPa; knock-downs as above"),
    "Birch ply": Material("Birch plywood", 9000, 0.30, 0.68e-9, 25.0, "aircraft birch, bending ~60 MPa"),
    "TPU": Material("TPU 95A", 26, 0.45, 1.21e-9, 8.0, ""),
}


@dataclass
class Mesh:
    nodes: np.ndarray       # (n, 3)
    ids: np.ndarray         # node ids
    elems: np.ndarray       # (m, 10) node ids
    work: Path

    def idx(self):
        return {int(i): k for k, i in enumerate(self.ids)}


def mesh_solid(solid, work: Path, hmax: float, hmin: float, name="part") -> Mesh:
    work.mkdir(parents=True, exist_ok=True)
    export_step(solid, str(work / f"{name}.step"))
    (work / "mesh.geo").write_text(f"""SetFactory("OpenCASCADE");
Merge "{name}.step";
Mesh.CharacteristicLengthMax = {hmax};
Mesh.CharacteristicLengthMin = {hmin};
Mesh.CharacteristicLengthFromCurvature = 1;
Mesh.MinimumElementsPerTwoPi = 16;
Mesh.ElementOrder = 2;
Mesh.HighOrderOptimize = 1;
Mesh.Optimize = 1;
Physical Volume("PART") = Volume{{:}};
Mesh 3;
Save "mesh.inp";
""")
    subprocess.run(["bash", "-c", f"source {FOAM_ENV} && cd {work} && gmsh mesh.geo -nt 8 -v 1 -0 > log.gmsh 2>&1"], check=True)
    txt = (work / "mesh.inp").read_text()
    nblock = re.search(r"\*NODE\s*\n(.*?)\n\*", txt, re.S).group(1)
    nd = np.array([[float(v) for v in l.split(",")] for l in nblock.strip().splitlines()])
    eblocks = re.findall(r"\*ELEMENT, type=C3D10[^\n]*\n(.*?)(?=\n\*)", txt, re.S)
    el = []
    for b in eblocks:
        el += [[int(v) for v in l.split(",")[1:]] for l in b.strip().splitlines()]
    return Mesh(nd[:, 1:], nd[:, 0].astype(int), np.array(el), work)


def boundary_faces(m: Mesh):
    """Boundary T6 faces as arrays of node ids (corner x3, mid x3): faces used by one element only."""
    allf = np.concatenate([m.elems[:, list(f)] for f in TET_FACES])
    key = np.sort(allf[:, :3], axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    return allf[cnt[inv.ravel()] == 1]


def face_props(m: Mesh, faces):
    ix = m.idx()
    P = m.nodes
    c = np.array([[P[ix[n]] for n in f[:3]] for f in faces])
    nrm = np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    cent = c.mean(axis=1)
    return cent, nrm / (2 * area[:, None] + 1e-30), area


def traction_loads(m: Mesh, faces, total_force: np.ndarray | None = None, per_face_fn=None) -> dict:
    """Consistent nodal loads (T6: mid-side nodes 1/3 each) for tractions on faces.

    Either a uniform traction totalling `total_force`, or per_face_fn(centroid, normal)
    returning a traction vector (N/mm^2)."""
    cent, nrm, area = face_props(m, faces)
    loads = {}
    if total_force is not None:
        t = np.asarray(total_force) / area.sum()
        trac = np.tile(t, (len(faces), 1))
    else:
        trac = np.array([per_face_fn(c, n) for c, n in zip(cent, nrm)])
    for f, a, tr in zip(faces, area, trac):
        for n in f[3:]:
            loads[int(n)] = loads.get(int(n), 0) + tr * a / 3
    return loads


def solve(m: Mesh, mat: Material, fixed_nodes, loads: dict, name="case") -> dict:
    w = m.work
    with open(w / f"{name}.inp", "w") as fh:
        fh.write("*NODE, NSET=NALL\n")
        for i, p in zip(m.ids, m.nodes):
            fh.write(f"{i},{p[0]:.6f},{p[1]:.6f},{p[2]:.6f}\n")
        fh.write("*ELEMENT, TYPE=C3D10, ELSET=EALL\n")
        for k, e in enumerate(m.elems, 1):
            fh.write(f"{k}," + ",".join(map(str, e)) + "\n")
        fh.write("*NSET, NSET=FIX\n")
        for i, n in enumerate(sorted(set(int(x) for x in fixed_nodes))):
            fh.write(f"{n},\n")
        fh.write(f"*MATERIAL, NAME=M\n*ELASTIC\n{mat.E},{mat.nu}\n*DENSITY\n{mat.rho}\n*SOLID SECTION, ELSET=EALL, MATERIAL=M\n")
        fh.write("*STEP\n*STATIC\n*BOUNDARY\nFIX,1,3\n*CLOAD\n")
        for n, f in loads.items():
            for k in range(3):
                if abs(f[k]) > 0:
                    fh.write(f"{n},{k + 1},{f[k]:.6e}\n")
        fh.write("*NODE FILE\nU\n*EL FILE\nS\n*NODE PRINT, NSET=FIX, TOTALS=ONLY\nRF\n*END STEP\n")
    subprocess.run(["bash", "-c", f"source {FOAM_ENV} && cd {w} && OMP_NUM_THREADS=8 ccx -i {name} > log.{name} 2>&1"], check=True)
    return read_frd(w / f"{name}.frd", m) | {"reaction": read_reaction(w / f"{name}.dat")}


def read_reaction(path: Path):
    txt = path.read_text()
    m = re.search(r"total force.*?\n\s*\n?\s*([-\dE.+]+)\s+([-\dE.+]+)\s+([-\dE.+]+)", txt, re.S | re.I)
    return [float(m.group(i)) for i in (1, 2, 3)] if m else None


def read_frd(path: Path, m: Mesh) -> dict:
    lines = path.read_text().splitlines()
    disp, stress = {}, {}
    block = None
    for line in lines:
        if line.startswith(" -4"):
            block = line.split()[1]
            continue
        if line.startswith(" -3"):
            block = None
            continue
        if block and line.startswith(" -1"):
            nid = int(line[3:13])
            vals = [float(line[13 + 12 * k:25 + 12 * k]) for k in range((len(line) - 13) // 12)]
            if block == "DISP":
                disp[nid] = vals[:3]
            elif block == "STRESS":
                stress[nid] = vals[:6]
    ids = np.array(sorted(stress))
    S = np.array([stress[i] for i in ids])
    sxx, syy, szz, sxy, syz, szx = S.T
    vm = np.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3 * (sxy**2 + syz**2 + szx**2))
    U = np.array([disp[i] for i in ids])
    ix = m.idx()
    xyz = np.array([m.nodes[ix[i]] for i in ids])
    k = int(np.argmax(vm))
    # 99.5th percentile excludes single-node singularities at load/support edges
    return dict(vm_max=float(vm.max()), vm_p995=float(np.percentile(vm, 99.5)), vm_at=xyz[k].tolist(),
                umax=float(np.linalg.norm(U, axis=1).max()), n_nodes=len(m.ids), n_elems=len(m.elems),
                _vm=vm, _ids=ids, _xyz=xyz, _U=U)


def render(m: Mesh, res: dict, path: Path, title: str, allow: float, view=(25, -60), scale=None):
    """Surface plot of von Mises stress on the deformed boundary (matplotlib)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    faces = boundary_faces(m)
    if len(faces) > 60000:  # keep matplotlib responsive: plot a uniform subset plus the most stressed faces
        vmd = dict(zip(res["_ids"], res["_vm"]))
        fv = np.array([max(vmd.get(n, 0) for n in f[:3]) for f in faces])
        top = np.argsort(fv)[-15000:]
        rest = np.random.default_rng(0).choice(len(faces), 45000, replace=False)
        faces = faces[np.unique(np.concatenate([top, rest]))]
    vm = dict(zip(res["_ids"], res["_vm"]))
    U = dict(zip(res["_ids"], res["_U"]))
    ix = m.idx()
    umax = res["umax"] or 1.0
    size = np.ptp(m.nodes, axis=0).max()
    s = scale if scale is not None else 0.05 * size / umax
    tris, vals = [], []
    for f in faces:
        c = [m.nodes[ix[n]] + s * np.array(U.get(n, (0, 0, 0))) for n in f[:3]]
        tris.append(c)
        vals.append(np.mean([vm.get(n, 0) for n in f[:3]]))
    vals = np.array(vals)
    fig = plt.figure(figsize=(7.5, 5.6), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    cmap = plt.get_cmap("turbo")
    norm = plt.Normalize(0, max(allow, np.percentile(vals, 99.5)))
    pc = Poly3DCollection(tris, facecolors=cmap(norm(vals)), edgecolor="none", linewidth=0)
    ax.add_collection3d(pc)
    P = m.nodes
    ctr = P.mean(axis=0)
    r = np.ptp(P, axis=0).max() / 2
    ax.set_xlim(ctr[0] - r, ctr[0] + r); ax.set_ylim(ctr[1] - r, ctr[1] + r); ax.set_zlim(ctr[2] - r, ctr[2] + r)
    ax.view_init(*view)
    ax.set_axis_off()
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cb.set_label("von Mises (MPa)")
    ax.set_title(f"{title}\nmax {res['vm_p995']:.1f} MPa (99.5 pct), allowable {allow:.0f} MPa; deformation x{s:.0f}", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
