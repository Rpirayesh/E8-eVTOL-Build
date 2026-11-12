"""Build every part of the subscale E8, export manufacturing and viewer files.

    python tools/build_cad.py

Outputs
  cad/parts/<ID>/<ID>.step|.stl     one per unique part (print / machine files, mm)
  cad/assembly/E8S_assembly.step    full assembly
  cad/mass_properties.json          CAD mass, CG and comparison with the sizing budget
  docs/models/*.glb, docs/data/parts.json   browser viewer content
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from build123d import Compound, Location, export_step, export_stl

sys.path.insert(0, str(Path(__file__).parent))
from cad import parts as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COMP = json.loads((ROOT / "design" / "components.json").read_text())

COTS_MASS = {  # part id -> kg per instance (manufacturer data)
    "MOT-L": COMP["lift_motor"]["mass_kg"], "PROP-CW": COMP["lift_prop"]["mass_kg"] / 2,
    "PROP-CCW": COMP["lift_prop"]["mass_kg"] / 2, "ESC-L": COMP["lift_esc"]["mass_kg"],
    "MOT-P": COMP["cruise_motor"]["mass_kg"], "PROP-P": COMP["cruise_prop"]["mass_kg"], "SPIN": 0.012,
    "BAT": COMP[P.SEL["design"]["battery"]]["mass_kg"], "FC": COMP["flight_controller"]["mass_kg"],
    "GPS": COMP["gps"]["mass_kg"], "SRV": COMP["servo"]["mass_kg"],
}
COLORS = {  # RGBA for the viewer, by material / role
    "LW-PLA (foamed)": [236, 238, 241, 255], "PETG": [70, 120, 200, 255], "PETG-CF": [55, 58, 64, 255],
    "PA6-CF": [45, 47, 52, 255], "TPU 95A": [230, 110, 40, 255], "6061-T6 aluminium": [176, 182, 190, 255],
    "Birch plywood": [214, 178, 120, 255], "Carbon fibre tube": [28, 28, 30, 255], "Carbon fibre rod": [28, 28, 30, 255],
    "purchased": [200, 60, 60, 255],
}
PURCHASED_COLORS = {"BAT": [240, 190, 40, 255], "MOT-L": [150, 30, 30, 255], "MOT-P": [150, 30, 30, 255],
                    "PROP-CW": [20, 20, 22, 255], "PROP-CCW": [20, 20, 22, 255], "PROP-P": [20, 20, 22, 255],
                    "ESC-L": [40, 80, 160, 255], "FC": [30, 30, 30, 255], "GPS": [30, 30, 30, 255],
                    "SRV": [30, 30, 120, 255], "SPIN": [200, 200, 205, 255]}


def part_mass(p: P.Part) -> float:
    if p.pid in COTS_MASS:
        return COTS_MASS[p.pid]
    rho = P.DENSITY.get(p.material, 1.2)  # g/cm^3
    wall = p.settings.get("print_wall_mm")
    if wall:
        return p.solid.area * wall * rho / 1e6  # printed hollow: surface area x wall
    vol_cm3 = p.solid.volume / 1000
    if p.process == "FDM" and "infill" in p.settings and p.material != "LW-PLA (foamed)":
        return vol_cm3 * rho * 0.85 / 1000  # thin-walled printed parts are mostly perimeters
    return vol_cm3 * rho / 1000


def tess(solid, tol=0.15, ang=0.25):
    verts, faces = solid.tessellate(tol, ang)
    v = np.array([[p.X, p.Y, p.Z] for p in verts], dtype=np.float32)
    f = np.array(faces, dtype=np.int64)
    return trimesh.Trimesh(v, f, process=False)


def loc_matrix(loc: Location) -> np.ndarray:
    return np.array([[loc.wrapped.Transformation().Value(i, j) for j in range(1, 5)] for i in range(1, 4)] + [[0, 0, 0, 1]])


CAL_GROUPS = {
    "wing_printed": ("W-R", "W-C", "W-O", "W-A1", "W-A2", "AIL", "W-T", "W-TP"),
    "spars": ("SP-MC", "SP-RC", "SP-MO", "SP-RO", "SP-MJ", "SP-RJ"),
    "clamps": ("RIB-B", "SAD-U", "SAD-L"),
    "nacelles": ("NAC-U", "NAC-L"),
    "tail": ("TB-S", "TB-P", "HS", "HS-C", "ELV", "HS-SP", "FIN", "RUD"),
    "fuselage": ("FUS-0", "FUS-1", "FUS-2", "FUS-3", "FUS-4", "FUS-5", "FUS-6", "FUS-H", "BH-1", "BH-2", "BH-3",
                 "BH-4", "BH-5", "BH-6", "SC-1", "SC-2", "TRAY", "DECK", "GPS-M", "FW"),
    "gear": ("LG-S", "LG-P", "LG-T", "LG-F", "LG-TP", "LG-FP"),
    "booms": ("BM-F", "BM-R", "BM-S", "BM-NC"),
}


def write_calibration(meta):
    """Coefficients for the sizing mass model, measured from this CAD build."""
    tot = {k: sum(m["mass_g_each"] * m["qty"] for m in meta if m["id"] in ids) / 1000 for k, ids in CAL_GROUPS.items()}
    g = P.SEL["geometry"]
    cal = {
        "_source": "tools/build_cad.py: measured from the CAD of the selected design",
        "wing_printed_kg_per_m2": tot["wing_printed"] / g["S"],
        "spars_kg_per_m_span": tot["spars"] / P.SEL["design"]["span_m"],
        "clamps_kg_total": tot["clamps"],
        "nacelle_kg_each": tot["nacelles"] / 8,
        "tail_kg": tot["tail"],
        "fuselage_kg": tot["fuselage"],
        "gear_kg": tot["gear"],
        "booms_kg_per_m": tot["booms"] / (2 * g["boom_len"]),
    }
    (ROOT / "design" / "mass_calibration.json").write_text(json.dumps(cal, indent=1))
    print("calibration:", json.dumps({k: round(v, 4) for k, v in cal.items() if k[0] != "_"}))


def main():
    t0 = time.time()
    groups = [P.wing_parts, P.boom_parts, P.nacelle_parts, P.fuselage_parts, P.tail_parts, P.gear_parts, P.hardware_parts]
    parts: list[P.Part] = []
    for g in groups:
        parts += g()
    print(f"generated {len(parts)} unique parts in {time.time() - t0:.1f} s")

    out_parts = ROOT / "cad" / "parts"
    out_models = ROOT / "docs" / "models"
    out_parts.mkdir(parents=True, exist_ok=True)
    out_models.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)

    scene = trimesh.Scene()
    meta, placed = [], []
    total_m, mx = 0.0, np.zeros(3)
    for p in parts:
        mass = part_mass(p)
        com = p.solid.center()
        com = np.array([com.X, com.Y, com.Z])
        files = {}
        if not p.purchased or p.process == "COTS-cut":
            d = out_parts / p.pid
            d.mkdir(exist_ok=True)
            # manufacturing files in the part's own frame, moved so its bounding box starts at the origin
            bb = p.solid.bounding_box()
            local = p.solid.translate((-bb.min.X, -bb.min.Y, -bb.min.Z))
            export_step(local, str(d / f"{p.pid}.step"))
            export_stl(local, str(d / f"{p.pid}.stl"), tolerance=0.03, angular_tolerance=0.15)
            files = {"step": f"cad/parts/{p.pid}/{p.pid}.step", "stl": f"cad/parts/{p.pid}/{p.pid}.stl"}
        mesh = tess(p.solid)
        color = PURCHASED_COLORS.get(p.pid) if p.purchased and p.process == "COTS" else COLORS.get(p.material, [180, 180, 180, 255])
        mesh.visual.face_colors = color
        glb_name = f"{p.pid}.glb"
        mesh.export(out_models / glb_name)
        inst = []
        for k, loc in enumerate(p.placements):
            M = loc_matrix(loc)
            node = f"{p.pid}#{k}"
            scene.add_geometry(mesh, node_name=node, geom_name=p.pid, transform=M)
            c = (M @ np.append(com, 1.0))[:3]
            total_m += mass
            mx += mass * c
            inst.append(M.tolist())
            placed.append(p.solid.moved(loc))
        bb = p.solid.bounding_box()
        meta.append(dict(id=p.pid, name=p.name, group=p.group, process=p.process, material=p.material,
                         qty=len(p.placements), mass_g_each=round(mass * 1000, 1),
                         size_mm=[round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)],
                         notes=p.notes, settings=p.settings, files=files, glb=f"models/{glb_name}",
                         color=color, instances=inst, purchased=p.purchased))
    scene.export(out_models / "E8S_assembly.glb")
    cg = mx / total_m
    print(f"exported in {time.time() - t0:.1f} s; CAD mass {total_m:.3f} kg, CG {cg.round(1)} mm")

    asm = Compound(children=placed)
    (ROOT / "cad" / "assembly").mkdir(parents=True, exist_ok=True)
    export_step(asm, str(ROOT / "cad" / "assembly" / "E8S_assembly.step"))

    # group masses for the sizing calibration
    by_group = {}
    for m in meta:
        by_group.setdefault(m["group"], 0.0)
        by_group[m["group"]] += m["mass_g_each"] * m["qty"] / 1000
    budget = P.SEL["mass"]
    mp = dict(cad_mass_kg=total_m, cg_mm=cg.tolist(), cg_target_mm=P.SEL["geometry"]["x_cg_target"] * 1000,
              sizing_mass_kg=budget["total_kg"], by_group_kg=by_group,
              note="CAD mass excludes harness, connectors, fasteners, adhesive, receiver/telemetry/airspeed/power module "
                   "and growth; those remain sizing allowances.",
              parts=[{k: m[k] for k in ("id", "name", "qty", "mass_g_each", "process", "material")} for m in meta])
    (ROOT / "cad" / "mass_properties.json").write_text(json.dumps(mp, indent=1))
    (ROOT / "docs" / "data" / "parts.json").write_text(json.dumps(dict(parts=meta, mass=mp, design=P.SEL["design"]), indent=1))
    print(json.dumps(by_group, indent=1))
    write_calibration(meta)
    print(f"done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
