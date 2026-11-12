"""CalculiX FEA of the load-bearing printed and machined parts (ultimate loads).

    python tools/fea/parts_fea.py            # all cases
    python tools/fea/parts_fea.py NAC-U      # one case

Loads come from the bench data (rotor thrust / torque), the global airframe model
(boom root moments) and the landing / tail load estimates documented per case.
Margin of safety uses the 99.5th-percentile von Mises stress so that single-node
singularities at idealised supports do not govern.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad import parts as P  # noqa: E402
from fea import ccx  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "fea" / "parts"
WORK = ROOT / ".cache" / "fea" / "parts"
GLB = ROOT / "docs" / "models" / "fea"
SEL = P.SEL
ULT = 1.5
G0 = 9.80665
T_MAX, Q_MAX = 40.2, 0.87                        # MN5008 KV170 + P18x6.1 bench maximum
MTOW = SEL["mass"]["total_kg"]
AIRFRAME = json.loads((ROOT / "analysis" / "fea" / "airframe" / "results.json").read_text())
BOOM_M = max(c["boom_root_moment_nm"] for c in AIRFRAME["cases"].values())  # ultimate, N m


def part(pid):
    for fn in (P.wing_parts, P.boom_parts, P.nacelle_parts, P.fuselage_parts, P.tail_parts, P.gear_parts):
        for p in fn():
            if p.pid == pid:
                return p
    raise KeyError(pid)


def near_cyl(xyz, axis: str, center, r, tol=0.35):
    a = {"x": 0, "y": 1, "z": 2}[axis]
    o = [i for i in range(3) if i != a]
    d = np.hypot(xyz[:, o[0]] - center[0], xyz[:, o[1]] - center[1])
    return np.abs(d - r) < tol


def faces_where(m, pred):
    faces = ccx.boundary_faces(m)
    cent, nrm, _ = ccx.face_props(m, faces)
    return faces[pred(cent, nrm)]


def nodes_where(m, pred):
    return m.ids[pred(m.nodes)]


def case_nacelle():
    p = part("NAC-U")
    R = P.C.boom_od / 2
    m = ccx.mesh_solid(p.solid, WORK / "NAC-U", 2.5, 0.6)
    fixed = nodes_where(m, lambda X: near_cyl(X, "x", (0, 0), R + 0.15) & (X[:, 2] > -0.1))
    seat = faces_where(m, lambda c, n: (np.abs(c[:, 2] - P.SEAT_Z) < 0.05) & (n[:, 2] > 0.9))
    T, Q = ULT * T_MAX, ULT * Q_MAX
    cent, _, area = ccx.face_props(m, seat)
    r2 = np.sum((cent[:, 0] ** 2 + cent[:, 1] ** 2) * area)
    k = Q / r2
    loads = ccx.traction_loads(m, seat, per_face_fn=lambda c, n: np.array([-k * c[1], k * c[0], T / area.sum()]))
    return p, m, ccx.MATERIALS["PA6-CF"], fixed, loads, f"Thrust {T:.0f} N + motor torque {Q:.2f} N m (1.5 x bench maximum)", (25, -50)


def case_saddle():
    p = part("SAD-U")
    R = P.C.boom_od / 2
    m = ccx.mesh_solid(p.solid, WORK / "SAD-U", 3.0, 0.8)
    fixed = nodes_where(m, lambda X: np.any([near_cyl(X, "y", (xb, 17.0), 2.6) for xb in P.BOLT_X_RIB], axis=0))
    bore = faces_where(m, lambda c, n: near_cyl(c, "x", (0, 0), R + 0.1, 0.4) & (c[:, 2] > 0.5))
    x0, x1 = P.SADDLE_X0, P.SADDLE_X1
    L, xc = x1 - x0, 0.5 * (x0 + x1)
    cent, _, area = ccx.face_props(m, bore)
    V = ULT * 4 * T_MAX                       # all four rotors of one boom at full thrust
    M = BOOM_M * 1000                          # N mm (already ultimate)
    # vertical traction per unit length: uniform V/L plus linear couple 12 M (x - xc) / L^3
    width = area.sum() / L
    trac = lambda c, n: np.array([0, 0, (V / L + 12 * M * (c[0] - xc) / L**3) / width])
    loads = ccx.traction_loads(m, bore, per_face_fn=trac)
    return p, m, ccx.MATERIALS["6061-T6"], fixed, loads, f"Boom shear {V:.0f} N + boom moment {BOOM_M:.0f} N m (ultimate)", (20, -60)


def case_rib():
    p = part("RIB-B")
    m = ccx.mesh_solid(p.solid, WORK / "RIB-B", 3.0, 0.8)
    fixed = nodes_where(m, lambda X: near_cyl(X, "y", (P.C.main_spar_x, P.MAIN_SPAR_Z), P.C.main_spar_od / 2 + 0.05)
                        | near_cyl(X, "y", (P.C.rear_spar_x, P.REAR_SPAR_Z), P.C.rear_spar_od / 2 + 0.05))
    V = ULT * 4 * T_MAX
    d = (P.BOLT_X_RIB[1] - P.BOLT_X_RIB[0])
    F1 = V / 2 + BOOM_M * 1000 / d
    F2 = V / 2 - BOOM_M * 1000 / d
    loads = {}
    for xb, F in zip(P.BOLT_X_RIB, (F1, F2)):
        holes = faces_where(m, lambda c, n, xb=xb: near_cyl(c, "y", (xb, -16.0), 2.6, 0.4))
        for k, v in ccx.traction_loads(m, holes, np.array([0, 0, F])).items():
            loads[k] = loads.get(k, 0) + v
    return p, m, ccx.MATERIALS["6061-T6"], fixed, loads, f"Bolt loads {F1:.0f} / {F2:.0f} N from the saddle (ultimate)", (10, -80)


def case_cap():
    p = part("SAD-L")
    R = P.C.boom_od / 2
    m = ccx.mesh_solid(p.solid, WORK / "SAD-L", 3.0, 0.8)
    yb = R + 4.5
    fixed = nodes_where(m, lambda X: np.any([near_cyl(X, "z", (xb, s * yb), 2.2) for xb in P.BOLT_X_CLAMP for s in (-1, 1)], axis=0))
    bore = faces_where(m, lambda c, n: near_cyl(c, "x", (0, -0.2), R + 0.1, 0.4) & (c[:, 2] < -0.7))
    x0, x1 = P.SADDLE_X0, P.SADDLE_X1
    L, xc = x1 - x0, 0.5 * (x0 + x1)
    cent, _, area = ccx.face_props(m, bore)
    boom_kg = (SEL["mass"]["items"]["booms (CF tube)"]["kg"] + SEL["mass"]["items"]["lift motors"]["kg"] +
               SEL["mass"]["items"]["lift ESCs"]["kg"] + SEL["mass"]["items"]["motor nacelles (printed)"]["kg"] +
               SEL["mass"]["items"]["H-tail + fins"]["kg"]) / 2
    V = ULT * 4.0 * boom_kg * G0               # boom inertia in the +4 g case pulls the boom down
    M = 0.5 * BOOM_M * 1000
    width = area.sum() / L
    # contact pressure on the cap only where the boom pushes down (q > 0): one-sided, conservative
    trac = lambda c, n: np.array([0, 0, -max(V / L + 12 * M * (c[0] - xc) / L**3, 0.0) / width])
    loads = ccx.traction_loads(m, bore, per_face_fn=trac)
    return p, m, ccx.MATERIALS["PA6-CF"], fixed, loads, f"Boom inertia {V:.0f} N downward + half boom moment (ultimate)", (-20, -60)


def case_leg():
    p = part("LG-S")
    R = P.C.boom_od / 2
    m = ccx.mesh_solid(p.solid, WORK / "LG-S", 2.5, 0.6)
    fixed = nodes_where(m, lambda X: near_cyl(X, "x", (0, 0), R + 0.15))
    s = math.radians(P.LEG_SPLAY)
    axis = np.array([0, math.sin(s), -math.cos(s)])
    origin = np.array([0, 0, -R + 2])
    def on_leg_bore(c):
        v = c - origin
        t = v @ axis
        rad = np.linalg.norm(v - np.outer(t, axis), axis=1)
        return (np.abs(rad - 6.1) < 0.4) & (t > 3)
    bore = faces_where(m, lambda c, n: on_leg_bore(c))
    F = ULT * 4.0 * MTOW * G0 / 2               # 4 g landing on the two legs of one boom
    Fv = -F * axis + np.array([0.25 * F, 0, 0])  # along the leg into the socket + 25 % friction / drag
    loads = ccx.traction_loads(m, bore, Fv)
    return p, m, ccx.MATERIALS["PA6-CF"], fixed, loads, f"Landing {F:.0f} N along the leg + 25 % drag (4 g on one boom, ultimate)", (15, -30)


def case_bulkhead():
    p = part("BH-3")
    xb = P.C.fus_x[3]
    t = P.C.bulkhead_t[2]
    m = ccx.mesh_solid(p.solid, WORK / "BH-3", 4.0, 1.0)
    sz = P.MAIN_SPAR_G[1]
    fixed = nodes_where(m, lambda X: near_cyl(X, "x", (0, sz), P.C.main_spar_od / 2 + 0.1, 0.4))
    zbot = P.C.fus_top - P.C.fus_h
    rim = faces_where(m, lambda c, n: (c[:, 2] < zbot + 14.5) & (n[:, 2] > 0.7))
    fus_kg = sum(SEL["mass"]["items"][k]["kg"] for k in ("fuselage shell + frames", "battery", "avionics", "harness + PDB", "pusher motor", "pusher prop + ESC"))
    F = 0.6 * ULT * 4.0 * fus_kg * G0           # BH-3 carries 60 % of the fuselage contents in a 4 g landing
    loads = ccx.traction_loads(m, rim, np.array([0, 0, -F]))
    return p, m, ccx.MATERIALS["Birch ply"], fixed, loads, f"Fuselage contents {F:.0f} N hung from the main spar (4 g landing, ultimate)", (10, -10)


def case_firewall():
    p = part("FW")
    za = P._tail_axis_z()
    m = ccx.mesh_solid(p.solid, WORK / "FW", 2.0, 0.6)
    fixed = nodes_where(m, lambda X: np.any([near_cyl(X, "x", (41 * math.cos(math.radians(a)), za + 41 * math.sin(math.radians(a))), 1.7)
                                             for a in (0, 90, 180, 270)], axis=0))
    holes = faces_where(m, lambda c, n: (np.hypot(c[:, 1], c[:, 2] - za) > 11) & (np.hypot(c[:, 1], c[:, 2] - za) < 21) & (np.abs(n[:, 0]) < 0.3))
    T = ULT * 7.63 * G0                         # AT4130 + APC 17x10 bench static thrust 7.63 kgf
    Q = ULT * 2.10
    cent, _, area = ccx.face_props(m, holes)
    r2 = np.sum(((cent[:, 1]) ** 2 + (cent[:, 2] - za) ** 2) * area)
    k = Q / r2
    loads = ccx.traction_loads(m, holes, per_face_fn=lambda c, n: np.array([-T / area.sum(), -k * (c[2] - za), k * c[1]]))
    return p, m, ccx.MATERIALS["6061-T6"], fixed, loads, f"Pusher thrust {T:.0f} N + torque {Q:.1f} N m (1.5 x bench maximum)", (20, 30)


def case_tailblock():
    p = part("TB-S")
    R = P.C.boom_od / 2
    m = ccx.mesh_solid(p.solid, WORK / "TB-S", 2.5, 0.6)
    fixed = nodes_where(m, lambda X: near_cyl(X, "x", (0, 0), R + 0.15))
    q = 0.5 * 1.225 * 35.0**2                   # dive speed 35 m/s
    Lh = ULT * 1.0 * q * (P.C.boom_y * 2 * P.C.tail_chord * 1e-6) / 2
    Lv = ULT * 1.0 * q * 0.031
    stab = faces_where(m, lambda c, n: (c[:, 1] < -(R + 3.0) + 0.3) & (c[:, 1] > -(R + 26)) & (np.abs(n[:, 2]) > 0.6))
    fin = faces_where(m, lambda c, n: (c[:, 2] > R + 3.0) & (np.abs(n[:, 1]) > 0.6))
    loads = ccx.traction_loads(m, stab, np.array([0, 0, Lh]))
    for k, v in ccx.traction_loads(m, fin, np.array([0, Lv, 0])).items():
        loads[k] = loads.get(k, 0) + v
    return p, m, ccx.MATERIALS["PA6-CF"], fixed, loads, f"Stab {Lh:.0f} N + fin {Lv:.0f} N at 35 m/s, CL 1.0 (ultimate)", (20, -120)


def case_sparcap():
    p = part("SC-1")
    xb = P.C.fus_x[3]
    sz = P.MAIN_SPAR_G[1]
    m = ccx.mesh_solid(p.solid, WORK / "SC-1", 2.0, 0.5)
    fixed = nodes_where(m, lambda X: np.any([near_cyl(X, "z", (xb, yy), 2.2) for yy in (-22.0, 22.0)], axis=0))
    bore = faces_where(m, lambda c, n: near_cyl(c, "x", (0, sz), P.C.main_spar_od / 2 + 0.1, 0.4))
    fus_kg = sum(SEL["mass"]["items"][k]["kg"] for k in ("fuselage shell + frames", "battery", "avionics", "harness + PDB", "pusher motor", "pusher prop + ESC"))
    F = 0.6 * ULT * 3.0 * fus_kg * G0           # -2 g gust: fuselage inertia pushes the cradle up (1 + 2 g relative)
    loads = ccx.traction_loads(m, bore, np.array([0, 0, -F]))
    return p, m, ccx.MATERIALS["PA6-CF"], fixed, loads, f"Spar retention {F:.0f} N (negative-g case, ultimate)", (25, -40)


CASES = {"NAC-U": case_nacelle, "SAD-U": case_saddle, "RIB-B": case_rib, "SAD-L": case_cap, "LG-S": case_leg,
         "BH-3": case_bulkhead, "FW": case_firewall, "TB-S": case_tailblock, "SC-1": case_sparcap}


def export_glb(m, res, path, allow):
    faces = ccx.boundary_faces(m)
    ix = m.idx()
    vm = dict(zip(res["_ids"], res["_vm"]))
    verts, tris, cols = [], [], []
    import matplotlib
    cmap = matplotlib.colormaps["turbo"]
    vmax = max(allow, float(np.percentile(res["_vm"], 99.5)))
    for f in faces:
        base = len(verts)
        for n in f[:3]:
            verts.append(m.nodes[ix[n]])
            cols.append((np.array(cmap(min(vm.get(n, 0) / vmax, 1.0))) * 255).astype(np.uint8))
        tris.append([base, base + 1, base + 2])
    mesh = trimesh.Trimesh(np.array(verts), np.array(tris), vertex_colors=np.array(cols), process=False)
    mesh.export(path)


def main():
    which = sys.argv[1:] or list(CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    GLB.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for pid in which:
        p, m, mat, fixed, loads, desc, view = CASES[pid]()
        res = ccx.solve(m, mat, fixed, loads, "case")
        applied = np.sum(np.array(list(loads.values())), axis=0)
        ms = mat.allow / res["vm_p995"] - 1
        ccx.render(m, res, OUT / f"{pid}.png", f"{p.name} ({mat.name})", mat.allow, view)
        export_glb(m, res, GLB / f"{pid}.glb", mat.allow)
        summary[pid] = dict(part=p.name, material=mat.name, load_case=desc, elements=res["n_elems"],
                            vm_max_mpa=res["vm_max"], vm_p995_mpa=res["vm_p995"], allowable_mpa=mat.allow, MS=ms,
                            max_disp_mm=res["umax"], applied_force_n=applied.tolist(), reaction_n=res["reaction"],
                            image=f"analysis/fea/parts/{pid}.png", glb=f"models/fea/{pid}.glb", allowable_note=mat.note)
        print(f"{pid:6s} {res['n_elems']:7d} el  vm99.5 {res['vm_p995']:7.1f} MPa (max {res['vm_max']:7.1f})  "
              f"allow {mat.allow:5.0f}  MS {ms:+.2f}  umax {res['umax']:.3f} mm  F {np.round(applied, 1)} R {res['reaction']}")
        summary_path.write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
