"""Parametric part generators for the E8 subscale demonstrator (millimetres).

Frame: x aft from the wing leading edge, y to starboard, z up, boom axes at z = 0.
Every generator returns a build123d solid in its *own* frame plus the list of
assembly placements.  Dimensions derive from design/selected_design.json.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from build123d import Location, Pos, Rot, Solid, Compound, mirror, Plane

from .geom import (arc_slot_z, box, camber_z, circle, clip2d, cyl_x, cyl_y, cyl_z, face_xz, loft_sections,
                   naca4, offset2d, prism_x, prism_y, prism_z, rounded_rect, superellipse, thickness_at,
                   tube_x, tube_y)

ROOT = Path(__file__).resolve().parents[2]
SEL = json.loads((ROOT / "design" / "selected_design.json").read_text())


# ============================================================================ configuration
@dataclass
class Cfg:
    g = SEL["geometry"]
    d = SEL["design"]
    chord: float = round(SEL["design"]["chord_m"] * 1000, 1)
    span: float = round(SEL["design"]["span_m"] * 1000, 1)
    airfoil: str = "4415"
    incidence_deg: float = 1.5
    wing_z: float = 38.0            # chord-line height at the main spar pivot
    boom_y: float = SEL["geometry"]["rotor_y"] * 1000
    boom_od: float = 30.0           # 30 x 27 CF tube: see analysis/fea/airframe/boom_study.json
    boom_id: float = 27.0
    rotor_x: list = field(default_factory=lambda: [round(v * 1000, 1) for v in SEL["geometry"]["rotor_x"]])
    boom_front: float = round(SEL["geometry"]["boom_front"] * 1000, 1)
    boom_aft: float = round(SEL["geometry"]["boom_aft"] * 1000, 1)
    tail_le: float = round(SEL["geometry"]["tail_le"] * 1000, 1)
    tail_chord: float = round(SEL["geometry"]["tail_chord"] * 1000, 1)
    main_spar_x: float = 84.0       # 28 % chord
    rear_spar_x: float = 195.0      # 65 % chord
    main_spar_od: float = 30.0      # sized by tools/fea/airframe.py --size-spar (same stock as booms)
    main_spar_id: float = 27.0
    rear_spar_od: float = 12.0
    rear_spar_id: float = 10.0
    hinge_x_frac: float = 0.73
    skin: float = 0.6               # printed LW-PLA skin (one foamed perimeter)
    fus_x: tuple = (-420.0, -250.0, -50.0, 84.0, 195.0, 420.0, 640.0, 830.0)
    fus_w: float = SEL["design"]["fuselage_w_m"] * 1000
    fus_h: float = SEL["design"]["fuselage_h_m"] * 1000
    fus_top: float = 25.0
    fus_skin: float = 1.0
    bulkhead_t: tuple = (3.0, 3.0, 6.0, 6.0, 3.0, 3.0)
    ground_z: float = -315.0
    rib_t: float = 6.0              # aluminium boom rib plate
    tip_len: float = 30.0


C = Cfg()
FOIL = naca4(C.airfoil, C.chord)
TAILFOIL = naca4("0010", C.tail_chord)
MAIN_SPAR_Z = camber_z(C.airfoil, C.chord, C.main_spar_x)
REAR_SPAR_Z = camber_z(C.airfoil, C.chord, C.rear_spar_x)
HALF = C.span / 2


def wing_loc(y: float) -> Location:
    """Wing-local (LE origin, chord line z=0) to aircraft frame at span station y."""
    return Pos(C.main_spar_x, y, C.wing_z) * Rot(0, C.incidence_deg, 0) * Pos(-C.main_spar_x, 0, 0)


def wing_to_global(x: float, z: float) -> tuple[float, float]:
    a = math.radians(C.incidence_deg)
    dx, dz = x - C.main_spar_x, z
    return C.main_spar_x + dx * math.cos(a) + dz * math.sin(a), C.wing_z - dx * math.sin(a) + dz * math.cos(a)


MAIN_SPAR_G = wing_to_global(C.main_spar_x, MAIN_SPAR_Z)
REAR_SPAR_G = wing_to_global(C.rear_spar_x, REAR_SPAR_Z)

# Span layout (half wing, from the centreline)
ROOT_HALF = C.fus_w / 2                                       # W-R spans +/- fuselage half width
RIB_Y0 = C.boom_y - C.rib_t / 2
RIB_Y1 = C.boom_y + C.rib_t / 2
WC_SPAN = (RIB_Y0 - ROOT_HALF) / 2                            # two centre segments per side
OUTER_SPAN = (HALF - C.tip_len - RIB_Y1) / 4                  # four outer segments per side


@dataclass
class Part:
    pid: str
    name: str
    group: str
    process: str          # FDM, CNC, COTS, COTS-cut
    material: str
    solid: Solid
    placements: list
    notes: str = ""
    settings: dict = field(default_factory=dict)
    purchased: bool = False


DENSITY = {  # g/cm^3 of the printed / machined part (effective)
    "LW-PLA (foamed)": 0.62, "PETG": 1.27, "PETG-CF": 1.30, "PA6-CF": 1.15, "TPU 95A": 1.21,
    "6061-T6 aluminium": 2.70, "Birch plywood": 0.68, "Carbon fibre tube": 1.55, "Carbon fibre rod": 1.55,
}

FDM_LW = {"printer": "any FDM with >= 256 mm Z and 0.4 mm nozzle", "material": "LW-PLA (foaming, ~230 C for ~50 % expansion)",
          "walls": "1 perimeter (0.6 mm foamed skin is modelled)", "infill": "0 % (internal ribs/webs are modelled)",
          "layer": "0.25 mm", "orientation": "stand on root rib (span vertical)", "supports": "none"}
FDM_STRUCT = {"printer": "FDM with hardened nozzle", "material": "PA6-CF or PETG-CF, dried",
              "walls": "5 perimeters", "infill": "40 % gyroid", "layer": "0.2 mm", "supports": "as needed",
              "post": "heat-set M3 inserts where noted"}
FDM_SHELL = {"printer": "any FDM", "material": "LW-PLA (fuselage) or PETG (nose/tail where impact-prone)",
             "walls": "2 perimeters (1.0 mm)", "infill": "0 %", "layer": "0.25 mm", "supports": "tree, under flanges"}


# ============================================================================ wing parts
def _wing_skin(span: float, hinge_cut: bool = False) -> Solid:
    """Printed wing segment: skin, end ribs, spar sleeves and shear webs."""
    outer = FOIL if not hinge_cut else clip2d(FOIL, xmax=C.hinge_x_frac * C.chord - 1.0)
    inner = offset2d(outer, -C.skin)
    seg = prism_y(outer, 0, span) - prism_y(inner, 0, span)
    # one end rib (1.2 mm) per segment with lightening windows; the neighbour's rib closes the joint
    rib = 1.2
    for y0 in (0.0,):
        r = prism_y(inner, y0, y0 + rib)
        for xa, xb in ((25, 70), (100, 180), (210, 255)):
            if hinge_cut and xb > C.hinge_x_frac * C.chord - 6:
                continue
            lo, hi = thickness_at(FOIL, (xa + xb) / 2)
            win = clip2d(offset2d(inner, -6.0), xmin=xa, xmax=xb)
            if len(win) > 2:
                r = r - prism_y(win, y0 - 1, y0 + rib + 1)
        seg = seg + r
    # spar sleeves + vertical shear webs at both spars
    for xs, zs, ro in ((C.main_spar_x, MAIN_SPAR_Z, C.main_spar_od / 2), (C.rear_spar_x, REAR_SPAR_Z, C.rear_spar_od / 2)):
        lo, hi = thickness_at(FOIL, xs)
        web = prism_y(np.array([[xs - 0.3, lo], [xs + 0.3, lo], [xs + 0.3, hi], [xs - 0.3, hi]]), 0, span)
        seg = seg + (web & prism_y(outer, 0, span)) + tube_y(ro + 0.8, ro, 0, span, xs, zs)
        seg = seg - cyl_y(ro + 0.15, -1, span + 1, xs, zs)
    if hinge_cut:
        xh = C.hinge_x_frac * C.chord - 1.0
        lo, hi = thickness_at(FOIL, xh - 0.5)
        seg = seg + prism_y(np.array([[xh - 1.0, lo], [xh, lo], [xh, hi], [xh - 1.0, hi]]), 0, span)
    return seg


def _aileron(span: float, chord_frac_start: float, foil=None, chord=None) -> Solid:
    foil = FOIL if foil is None else foil
    chord = C.chord if chord is None else chord
    xh = chord_frac_start * chord
    aft = clip2d(foil, xmin=xh + 0.5)
    lo, hi = thickness_at(foil, xh + 0.5)
    r = (hi - lo) / 2
    zc = (hi + lo) / 2
    nose = circle(r, xh + 0.5 + r, zc, 32)
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    poly = unary_union([Polygon(aft), Polygon(nose)]).intersection(Polygon(foil).buffer(0))
    pts = np.array(poly.exterior.coords)[:-1]
    shell_in = offset2d(pts, -0.8)
    s = prism_y(pts, 0.5, span - 0.5) - prism_y(shell_in, 1.7, span - 1.7)
    return s


def wing_parts() -> list[Part]:
    parts = []
    # W-R root segment: across the fuselage, slots for the wing-carry bulkhead towers
    wr = _wing_skin(2 * ROOT_HALF)
    for xs, t in ((C.main_spar_x, C.bulkhead_t[2]), (C.rear_spar_x, C.bulkhead_t[3])):
        lo, _ = thickness_at(FOIL, xs)
        wr = wr - box(xs - t / 2 - 0.2, xs + t / 2 + 0.2, 2 * ROOT_HALF / 2 - 101, 2 * ROOT_HALF / 2 + 101, lo - 5, lo + 30)
    # GPS mast socket on top
    parts.append(Part("W-R", "Wing root segment", "Wing", "FDM", "LW-PLA (foamed)", wr,
                      [wing_loc(-ROOT_HALF)], "Carries the two bulkhead towers through lower-skin slots; bond to W-C with epoxy.", FDM_LW))
    wc = _wing_skin(WC_SPAN)
    parts.append(Part("W-C", "Wing centre segment", "Wing", "FDM", "LW-PLA (foamed)", wc,
                      [wing_loc(ROOT_HALF), wing_loc(ROOT_HALF + WC_SPAN),
                       wing_loc(-ROOT_HALF - WC_SPAN), wing_loc(-ROOT_HALF - 2 * WC_SPAN)],
                      "Four identical; slide on spars, bond to neighbours.", FDM_LW))
    wo = _wing_skin(OUTER_SPAN)
    parts.append(Part("W-O", "Outer wing segment", "Wing", "FDM", "LW-PLA (foamed)", wo,
                      [wing_loc(RIB_Y1), wing_loc(RIB_Y1 + OUTER_SPAN),
                       wing_loc(-RIB_Y1 - OUTER_SPAN), wing_loc(-RIB_Y1 - 2 * OUTER_SPAN)],
                      "Outer panels are removable: spar joiners slide into the centre spars.", FDM_LW))
    wa1 = _wing_skin(OUTER_SPAN, hinge_cut=True)
    # servo pocket (25 g servo 32 x 12 x 30) on the lower skin, centred in span
    lo, _ = thickness_at(FOIL, 150)
    wa1 = wa1 - box(150 - 17, 150 + 17, OUTER_SPAN / 2 - 7, OUTER_SPAN / 2 + 7, lo - 2, lo + 30)
    y_a1 = RIB_Y1 + 2 * OUTER_SPAN
    parts.append(Part("W-A1", "Aileron bay segment with servo pocket", "Wing", "FDM", "LW-PLA (foamed)", wa1,
                      [wing_loc(y_a1), wing_loc(-y_a1 - OUTER_SPAN)], "Servo pocket opens on the lower skin.", FDM_LW))
    wa2 = _wing_skin(OUTER_SPAN, hinge_cut=True)
    parts.append(Part("W-A2", "Aileron bay segment", "Wing", "FDM", "LW-PLA (foamed)", wa2,
                      [wing_loc(y_a1 + OUTER_SPAN), wing_loc(-y_a1 - 2 * OUTER_SPAN)], "", FDM_LW))
    ail = _aileron(OUTER_SPAN, C.hinge_x_frac)
    parts.append(Part("AIL", "Aileron segment", "Wing", "FDM", "LW-PLA (foamed)", ail,
                      [wing_loc(y_a1), wing_loc(y_a1 + OUTER_SPAN), wing_loc(-y_a1 - OUTER_SPAN), wing_loc(-y_a1 - 2 * OUTER_SPAN)],
                      "Two per side bonded on a 4 mm carbon torque rod; tape or printed pin hinge on the upper surface. Horn on the inner piece.",
                      {**FDM_LW, "orientation": "stand on end", "walls": "1 perimeter"}))
    # wing tip: loft to a thinned profile
    tip_sections = [FOIL, FOIL * np.array([1.0, 0.55]) + np.array([0, camber_z(C.airfoil, C.chord, 120) * 0.45]),
                    FOIL * np.array([0.92, 0.18]) + np.array([12, camber_z(C.airfoil, C.chord, 120) * 0.8])]
    tip = loft_sections(tip_sections, [0, C.tip_len * 0.6, C.tip_len], axis="y")
    tip = tip - cyl_y(C.main_spar_od / 2 + 0.15, -1, 12, C.main_spar_x, MAIN_SPAR_Z)
    tip_st = {**FDM_SHELL, "material": "LW-PLA", "walls": "1 perimeter", "infill": "0 %"}
    parts.append(Part("W-T", "Wing tip, starboard", "Wing", "FDM", "LW-PLA (foamed)", tip, [wing_loc(HALF - C.tip_len)],
                      "Printed hollow (slicer walls only).", {**tip_st, "print_wall_mm": 0.6}))
    parts.append(Part("W-TP", "Wing tip, port (mirror)", "Wing", "FDM", "LW-PLA (foamed)", mirror(tip, Plane.XZ),
                      [wing_loc(-HALF + C.tip_len)], "Printed hollow (slicer walls only).", {**tip_st, "print_wall_mm": 0.6}))
    # Aluminium boom rib (CNC): airfoil plate with spar bores and a tab into the saddle
    rib_out = offset2d(FOIL, -1.0)
    rib_pts = rib_out
    rib = prism_y(rib_pts, 0, C.rib_t)
    lo_m, _ = thickness_at(FOIL, C.main_spar_x)
    # tab below the lower surface reaching down into the saddle slot (to global z ~ 10)
    tab = prism_y(np.array([[SADDLE_X0 + 9, lo_m + 3], [SADDLE_X1 - 9, lo_m + 3], [SADDLE_X1 - 9, -26.0], [SADDLE_X0 + 9, -26.0]]), 0, C.rib_t)
    rib = rib + tab
    rib = rib - cyl_y(C.main_spar_od / 2 + 0.05, -1, C.rib_t + 1, C.main_spar_x, MAIN_SPAR_Z)
    rib = rib - cyl_y(C.rear_spar_od / 2 + 0.05, -1, C.rib_t + 1, C.rear_spar_x, REAR_SPAR_Z)
    for xa, xb in ((22, 62), (110, 170), (215, 268)):
        win = clip2d(offset2d(rib_out, -7.0), xmin=xa, xmax=xb)
        if len(win) > 2:
            rib = rib - prism_y(win, -1, C.rib_t + 1)
    # bolt holes to the saddle (2 x M5 cross bolts, along y)
    for xb in BOLT_X_RIB:
        rib = rib - cyl_y(2.6, -1, C.rib_t + 1, xb, -16.0)
    # wire pass-through for the boom power leads
    rib = rib - cyl_y(5.0, -1, C.rib_t + 1, 140, 5.0)
    parts.append(Part("RIB-B", "Boom rib (wing-boom load fitting)", "Wing", "CNC", "6061-T6 aluminium", rib,
                      [wing_loc(RIB_Y0), wing_loc(-RIB_Y1)],
                      f"2-D profile from 6 mm 6061-T6 plate: one setup, 6 mm flat end mill for the profile, 3 mm for windows, bore the spar holes to {C.main_spar_od + 0.05:.2f} / {C.rear_spar_od + 0.05:.2f} mm (helical interpolation).",
                      {"machine": "3-axis CNC", "stock": "6 mm 6061-T6 plate", "setups": 1,
                       "tools": "6 mm 2-flute carbide (profile, 12000 rpm, 1000 mm/min, 1 mm DOC), 3 mm (windows)",
                       "workholding": "screwed to spoilboard through tab holes, onion-skin 0.3 mm"}))
    # Spars and joiners (cut from stock)
    spar_len_c = 2 * RIB_Y1
    outer_len = HALF - C.tip_len + 10 - RIB_Y1
    for pid, name, ro, ri, y0, y1, xs, zs, qty_note in (
        ("SP-MC", f"Main spar, centre ({C.main_spar_od:.0f}x{C.main_spar_id:.0f} CF tube)", C.main_spar_od / 2, C.main_spar_id / 2, -RIB_Y1, RIB_Y1, C.main_spar_x, MAIN_SPAR_Z, ""),
        ("SP-RC", f"Rear spar, centre ({C.rear_spar_od:.0f}x{C.rear_spar_id:.0f} CF tube)", C.rear_spar_od / 2, C.rear_spar_id / 2, -RIB_Y1, RIB_Y1, C.rear_spar_x, REAR_SPAR_Z, ""),
    ):
        s = tube_y(ro, ri, y0, y1, xs, zs)
        parts.append(Part(pid, name, "Wing", "COTS-cut", "Carbon fibre tube", s, [wing_loc(0)],
                          f"Cut to {y1 - y0:.0f} mm.", {"cut": f"{y1 - y0:.0f} mm, fine-tooth saw or abrasive disc, wet; sand ends"}, purchased=True))
    for pid, name, ro, ri, xs, zs in (("SP-MO", f"Main spar, outer panel ({C.main_spar_od:.0f}x{C.main_spar_id:.0f} CF tube)", C.main_spar_od / 2, C.main_spar_id / 2, C.main_spar_x, MAIN_SPAR_Z),
                                      ("SP-RO", f"Rear spar, outer panel ({C.rear_spar_od:.0f}x{C.rear_spar_id:.0f} CF tube)", C.rear_spar_od / 2, C.rear_spar_id / 2, C.rear_spar_x, REAR_SPAR_Z)):
        s = tube_y(ro, ri, 0, outer_len, xs, zs)
        parts.append(Part(pid, name, "Wing", "COTS-cut", "Carbon fibre tube", s, [wing_loc(RIB_Y1), wing_loc(-RIB_Y1 - outer_len)],
                          f"Cut 2 to {outer_len:.0f} mm.", {"cut": f"{outer_len:.0f} mm x 2"}, purchased=True))
    for pid, name, ro, ri, xs, zs, L in (("SP-MJ", f"Main spar joiner ({C.main_spar_id:.0f}x{C.main_spar_id - 2:.0f} CF tube)", C.main_spar_id / 2 - 0.05, C.main_spar_id / 2 - 1.0, C.main_spar_x, MAIN_SPAR_Z, 300),
                                         ("SP-RJ", f"Rear spar joiner ({C.rear_spar_id:.0f} mm CF rod)", C.rear_spar_id / 2 - 0.05, 0.0, C.rear_spar_x, REAR_SPAR_Z, 200)):
        s = tube_y(ro, ri, 0, L, xs, zs) if ri > 0 else cyl_y(ro, 0, L, xs, zs)
        parts.append(Part(pid, name, "Wing", "COTS-cut", "Carbon fibre tube" if ri else "Carbon fibre rod", s,
                          [wing_loc(RIB_Y1 - L / 2), wing_loc(-RIB_Y1 - L / 2)],
                          "Bonded into the centre spar, slip fit in the outer spar; retained by an M3 nylon bolt.", {"cut": f"{L} mm x 2"}, purchased=True))
    return parts


# ============================================================================ boom / saddle parts
SADDLE_X0, SADDLE_X1 = 70.0, 220.0
BOLT_X_RIB = (105.0, 185.0)
BOLT_X_CLAMP = (78.0, 145.0, 212.0)
SADDLE_TOP = 26.0
BOOM_SPLIT_X = 145.0


def boom_parts() -> list[Part]:
    parts = []
    R = C.boom_od / 2
    # Saddle (upper half, aluminium): half bore, central slot for the rib tab, side pockets
    yb_bolt = R + 4.5
    w = 2 * (R + 9.0)
    sad = box(SADDLE_X0, SADDLE_X1, -w / 2, w / 2, 0.0, SADDLE_TOP)
    sad = sad - cyl_x(R + 0.1, SADDLE_X0 - 1, SADDLE_X1 + 1)
    sad = sad - box(SADDLE_X0 + 8, SADDLE_X1 - 8, -C.rib_t / 2 - 0.1, C.rib_t / 2 + 0.1, 10.0, SADDLE_TOP + 1)
    for xb in BOLT_X_RIB:  # cross bolts through the rib tab (M5)
        sad = sad - cyl_y(2.6, -w, w, xb, 17.0)
    for xb in BOLT_X_CLAMP:  # clamp bolts (M4) to the cap
        for yb in (-yb_bolt, yb_bolt):
            sad = sad - cyl_z(2.2, -1, SADDLE_TOP + 1, xb, yb)
    for xa, xb_ in ((BOLT_X_CLAMP[0] + 7, BOLT_X_RIB[0] - 7), (BOLT_X_RIB[0] + 7, BOLT_X_RIB[1] - 7), (BOLT_X_RIB[1] + 7, BOLT_X_CLAMP[-1] - 7)):
        for ys in (-1, 1):
            y_in, y_out = C.rib_t / 2 + 3.0, w / 2 - 3.0
            sad = sad - box(xa, xb_, min(ys * y_in, ys * y_out), max(ys * y_in, ys * y_out), 14.0, SADDLE_TOP + 1)
    # Lower cap (printed PA6-CF): half tube with bolt bosses
    cap = box(SADDLE_X0, SADDLE_X1, -w / 2, w / 2, -R - 5.0, 0.0) - cyl_x(R + 0.1, SADDLE_X0 - 1, SADDLE_X1 + 1)
    for xb in BOLT_X_CLAMP:
        for yb in (-yb_bolt, yb_bolt):
            cap = cap - cyl_z(2.2, -R - 7, 1, xb, yb)
    cap = cap.translate((0, 0, -0.2))  # 0.2 mm clamp gap between halves
    places = [Pos(0, C.boom_y, 0), Pos(0, -C.boom_y, 0)]
    cnc_saddle = {"machine": "3-axis CNC", "stock": f"6061-T6 bar {w + 2:.0f} x 30 x 170 mm", "setups": 2,
                  "ops": f"Op1 face, profile, side pockets 6 mm end mill, drill M4/M5; Op2 flip, 12 mm ball-nose half-bore R{R + 0.1:.1f} along x (0.5 mm step-over), slot {C.rib_t + 0.2:.1f} mm with 6 mm end mill",
                  "tolerance": f"half-bore R{R + 0.1:.1f} +0.05/-0; clamp gap 0.2 mm"}
    parts.append(Part("SAD-U", "Boom saddle, upper half", "Booms", "CNC", "6061-T6 aluminium", sad, places,
                      "Joins the boom halves (internal sleeve) and transfers boom loads into the boom rib via two M5 cross bolts.", cnc_saddle))
    parts.append(Part("SAD-L", "Boom saddle, lower cap", "Booms", "FDM", "PA6-CF", cap, places,
                      "6 x M4 x 45 socket cap screws + washers + nyloc; torque 1.5 N m.", {**FDM_STRUCT, "orientation": "flat face down", "infill": "60 % gyroid"}))
    # Booms (two halves per side) + sleeve
    bf = tube_x(R, C.boom_id / 2, C.boom_front, BOOM_SPLIT_X)
    br = tube_x(R, C.boom_id / 2, BOOM_SPLIT_X, C.boom_aft)
    sleeve = tube_x(C.boom_id / 2 - 0.05, C.boom_id / 2 - 1.05, BOOM_SPLIT_X - 75, BOOM_SPLIT_X + 75)
    parts.append(Part("BM-F", f"Front boom ({C.boom_od:.0f}x{C.boom_id:.0f} CF tube)", "Booms", "COTS-cut", "Carbon fibre tube", bf, places,
                      f"Cut to {BOOM_SPLIT_X - C.boom_front:.0f} mm; drill 8 mm wire exits under each motor.",
                      {"cut": f"{BOOM_SPLIT_X - C.boom_front:.0f} mm x 2"}, purchased=True))
    parts.append(Part("BM-R", f"Rear boom ({C.boom_od:.0f}x{C.boom_id:.0f} CF tube)", "Booms", "COTS-cut", "Carbon fibre tube", br, places,
                      f"Cut to {C.boom_aft - BOOM_SPLIT_X:.0f} mm.", {"cut": f"{C.boom_aft - BOOM_SPLIT_X:.0f} mm x 2"}, purchased=True))
    parts.append(Part("BM-S", f"Boom joint sleeve ({C.boom_id:.0f}x{C.boom_id - 2:.0f} CF tube)", "Booms", "COTS-cut", "Carbon fibre tube", sleeve, places,
                      "Bonded into the rear boom, slip fit into the front boom inside the saddle.", {"cut": "150 mm x 2"}, purchased=True))
    # Boom nose cap
    capn = Solid.make_cone(R, 4.0, 30, Plane(origin=(C.boom_front, 0, 0), z_dir=(-1, 0, 0)))
    plug = cyl_x(C.boom_id / 2 - 0.1, C.boom_front, C.boom_front + 15)
    parts.append(Part("BM-NC", "Boom nose cone", "Booms", "FDM", "PETG", capn + plug, places, "Press fit + CA.",
                      {**FDM_STRUCT, "material": "PETG", "infill": "20 %"}))
    return parts


# ============================================================================ motor nacelle (lift)
NAC_LEN = 96.0
SEAT_Z = R_TOP = 12.5 + 24.0  # motor seat plane above boom axis


def nacelle_parts() -> list[Part]:
    parts = []
    R = C.boom_od / 2
    # upper: hollow streamlined pedestal from the boom up to the motor seat
    xs_p = np.linspace(-NAC_LEN / 2, NAC_LEN / 2, 40)
    half = 30.0 * np.sqrt(np.clip(1 - (2 * xs_p / NAC_LEN) ** 2, 0, 1)) ** 0.7
    plan = np.vstack([np.column_stack([xs_p, half]), np.column_stack([xs_p[::-1], -half[::-1]])])
    plan = np.array([p for i, p in enumerate(plan) if i == 0 or not np.allclose(p, plan[i - 1])])
    ped = prism_z(plan, 0.0, SEAT_Z) - prism_z(offset2d(plan, -1.6), -1.0, SEAT_Z - 4.0)
    # internal structure: cross rib and a 36 mm column carrying the motor seat
    ped = ped + (box(-2, 2, -30, 30, 0, SEAT_Z) & prism_z(plan, 0, SEAT_Z))
    ped = ped + (cyl_z(18.0, 0, SEAT_Z) - cyl_z(16.0, -1, SEAT_Z))
    ped = ped + tube_x(R + 4.0, R, -NAC_LEN / 2 + 8, NAC_LEN / 2 - 8)
    for xb in (-35, 35):
        for yb in (-(R + 4.5), R + 4.5):
            ped = ped + cyl_z(4.0, 0, R + 8, xb, yb)
    ped = ped - cyl_x(R + 0.15, -NAC_LEN, NAC_LEN)
    ped = ped - box(-NAC_LEN, NAC_LEN, -40, 40, -40, 0.0)   # split line at boom axis
    # seat: Ø58 disc, centre bore Ø14, arc slots for 4 x M3 on PCD 25-34 mm (verify against motor)
    ped = ped + cyl_z(29.0, SEAT_Z - 4, SEAT_Z)
    ped = ped - cyl_z(7.0, R + 3, SEAT_Z + 1)
    for a in (45, 135, 225, 315):
        ped = ped - arc_slot_z(12.5, 17.0, a, 0, SEAT_Z - 30, SEAT_Z + 1)
        ped = ped - arc_slot_z(12.5, 17.0, a, 0, SEAT_Z - 30, SEAT_Z - 6, width=6.2)  # screw-head access from below
    # wire channel to boom
    ped = ped - cyl_z(4.0, 0, SEAT_Z, 18, 0)
    # clamp bolts (M3) through both halves
    for xb in (-35, 35):
        for yb in (-(R + 4.5), R + 4.5):
            ped = ped - cyl_z(1.7, -30, R + 9, xb, yb)
    lower = tube_x(R + 4.0, R, -NAC_LEN / 2 + 8, NAC_LEN / 2 - 8) - box(-NAC_LEN, NAC_LEN, -40, 40, 0.0, 40)
    pod_plan = superellipse(100.0, 44.0, 0.0, 3.2, 64)  # (x, y) planform enclosing the 70 x 32 x 15 ESC
    pod = prism_z(pod_plan, -R - 4 - 20, -R + 2)
    lower = lower + (pod - prism_z(offset2d(pod_plan, -1.6), -R - 22.4, -R + 1))
    lower = lower - box(40, 50, -12, 12, -R - 20, -R - 5)  # aft cooling exit
    lower = lower - cyl_x(R + 0.15, -NAC_LEN, NAC_LEN)
    for xb in (-35, 35):
        for yb in (-(R + 4.5), R + 4.5):
            lower = lower + cyl_z(4.0, -R - 6, 0, xb, yb)  # bolt bosses
            lower = lower - cyl_z(1.7, -40, 1, xb, yb)
    lower = lower.translate((0, 0, -0.2))
    places = []
    for y in (-C.boom_y, C.boom_y):
        for x in C.rotor_x:
            places.append(Pos(x, y, 0))
    parts.append(Part("NAC-U", "Lift motor nacelle, upper (motor pedestal)", "Propulsion", "FDM", "PA6-CF", ped, places,
                      "Motor seat with radial slots for 4 x M3 on any 25-34 mm bolt circle: confirm against the delivered MN5008 before printing.",
                      {**FDM_STRUCT, "orientation": "seat face down on the bed", "inserts": "none (through bolts)"}))
    parts.append(Part("NAC-L", "Lift motor nacelle, lower (ESC pod)", "Propulsion", "FDM", "PA6-CF", lower, places,
                      "Houses the FLAME 60A ESC in the rotor downwash; open aft end for cooling air.",
                      {**FDM_STRUCT, "orientation": "split face down"}))
    return parts


# ============================================================================ fuselage
def fus_section(x: float, inset: float = 0.0) -> np.ndarray:
    x0, x1 = C.fus_x[0], C.fus_x[1]
    xt0, xt1 = 420.0, C.fus_x[-1]
    W, H = C.fus_w, C.fus_h
    zc_mid = C.fus_top - H / 2
    if x < x1:
        s = (x - x0) / (x1 - x0)
        f = math.sqrt(max(1 - (1 - s) ** 2, 0))
        w = 44 + (W - 44) * f
        h = 44 + (H - 44) * f
        zc = zc_mid + 30 * (1 - f)
    elif x > xt0:
        s = (x - xt0) / (xt1 - xt0)
        w = W - (W - 72) * s**1.3
        h = H - (H - 72) * s**1.2
        top = C.fus_top - 10 * s
        zc = top - h / 2
    else:
        w, h, zc = W, H, zc_mid
    return superellipse(w - 2 * inset, h - 2 * inset, zc, 2.6, 72)


def _fus_shell(x0: float, x1: float, n: int = 6) -> Solid:
    xs = list(np.linspace(x0, x1, n))
    outer = loft_sections([fus_section(x) for x in xs], xs, "x")
    inner = loft_sections([fus_section(x, C.fus_skin) for x in xs], xs, "x")
    return outer - inner


def _flange(x: float, t: float, direction: int) -> Solid:
    """Inward bonding flange (8 mm) at a joint; direction +1 extends aft of x."""
    outer = fus_section(x, C.fus_skin - 0.01)
    inner = fus_section(x, C.fus_skin + 8.0)
    xa, xb = (x, x + 1.6) if direction > 0 else (x - 1.6, x)
    ring = prism_x(outer, xa, xb) - prism_x(inner, xa - 1, xb + 1)
    return ring


def _joint_holes(x: float) -> list[tuple[float, float]]:
    sec = fus_section(x, C.fus_skin + 4.0)
    idx = np.linspace(0, len(sec), 8, endpoint=False).astype(int)
    return [tuple(sec[i]) for i in idx]


def fuselage_parts() -> list[Part]:
    parts = []
    xs = C.fus_x
    names = ["Nose cone", "Fuselage section 1 (avionics / hatch)", "Fuselage section 2 (battery bay)",
             "Fuselage section 3 (wing carry)", "Fuselage section 4", "Fuselage section 5 (tail taper)", "Tail cone (pusher mount)"]
    ids = ["FUS-0", "FUS-1", "FUS-2", "FUS-3", "FUS-4", "FUS-5", "FUS-6"]
    for i in range(7):
        a = xs[i] + (C.bulkhead_t[i - 1] / 2 if i > 0 else 0)
        b = xs[i + 1] - (C.bulkhead_t[i] / 2 if i < 6 else 0)
        shell = _fus_shell(a, b)
        if i > 0:
            shell = shell + _flange(a, 1.6, +1)
        if i < 6:
            shell = shell + _flange(b, 1.6, -1)
        for xj, ok in ((a, i > 0), (b, i < 6)):
            if ok:
                for (yy, zz) in _joint_holes(xj):
                    shell = shell - cyl_x(1.7, xj - 3, xj + 3, yy, zz)
        if i == 0:
            # pitot / nose: flat tip with a 6 mm bore
            shell = shell - cyl_x(3.2, xs[0] - 1, xs[0] + 25, 0, fus_section(xs[0])[:, 1].mean())
        if i == 1:
            # hatch opening on top
            shell = shell - box(-232, -68, -75, 75, C.fus_top - 40, C.fus_top + 5)
        if i == 6:
            # firewall boss ring and motor exit
            xfw = 748.0
            ring = prism_x(fus_section(xfw, C.fus_skin - 0.01), xfw - 6, xfw) - prism_x(circle(45, 0, fus_section(xfw)[:, 1].mean() * 0 + _tail_axis_z(), 60), xfw - 7, xfw + 1)
            shell = shell + ring
            shell = shell - cyl_x(27.5, 800, xs[-1] + 2, 0, _tail_axis_z())
            # cooling inlets
            for zz in (-12.0, 12.0):
                shell = shell - box(700, 730, -60, 60, _tail_axis_z() + zz - 3, _tail_axis_z() + zz + 3)
        mat = "PETG" if i in (0, 6) else "LW-PLA (foamed)"
        st = {**FDM_SHELL, "material": mat, "orientation": "stand on the larger joint face"}
        if i == 6:
            st = {**FDM_STRUCT, "material": "PETG-CF", "infill": "n/a (shell)", "walls": "3 perimeters"}
        parts.append(Part(ids[i], names[i], "Fuselage", "FDM", "PETG-CF" if i == 6 else mat, shell, [Location()],
                          "Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.", st))
    # Hatch
    hatch = _fus_shell(-230, -70) & box(-230, -70, -73, 73, C.fus_top - 38, C.fus_top + 5)
    hatch = hatch + (box(-226, -74, -69, 69, C.fus_top - 6, C.fus_top - 4.5) & prism_x(fus_section(-150, 1.0), -240, -60))
    parts.append(Part("FUS-H", "Battery / avionics hatch", "Fuselage", "FDM", "LW-PLA (foamed)", hatch, [Location()],
                      "Two magnets forward, printed tongue aft.", FDM_SHELL))
    # Bulkheads
    bh_names = ["Bulkhead 1 (avionics)", "Bulkhead 2 (battery fwd)", "Bulkhead 3 (main spar carry)",
                "Bulkhead 4 (rear spar carry)", "Bulkhead 5", "Bulkhead 6 (tail)"]
    for i, xb in enumerate(xs[1:-1]):
        t = C.bulkhead_t[i]
        outer = fus_section(xb)
        frame_w = 20.0 if i in (2, 3) else 14.0  # wing-carry frames: wider band (BH-3 FEA)
        inner = fus_section(xb, frame_w)
        bh = prism_x(outer, xb - t / 2, xb + t / 2) - prism_x(inner, xb - t, xb + t)
        if i in (2, 3):
            # wing-carry tower with a spar cradle
            spar_z = MAIN_SPAR_G[1] if i == 2 else REAR_SPAR_G[1]
            r = (C.main_spar_od if i == 2 else C.rear_spar_od) / 2
            tower = box(xb - t / 2, xb + t / 2, -100, 100, C.fus_top - frame_w, spar_z + 0.0)
            bh = bh + tower
            bh = bh - cyl_x(r + 0.1, xb - t, xb + t, 0, spar_z)
            # lightening in the tower
            for yy in (-55, 55):
                bh = bh - cyl_x(14, xb - t, xb + t, yy, C.fus_top + (spar_z - C.fus_top) * 0.3)
            # cross beam under the battery to carry tray loads into the frame
        for (yy, zz) in _joint_holes(xb):
            bh = bh - cyl_x(1.7, xb - t, xb + t, yy, zz)
        mat = "Birch plywood"
        parts.append(Part(f"BH-{i + 1}", bh_names[i], "Fuselage", "CNC", mat, bh, [Location()],
                          f"{t:.0f} mm aircraft birch plywood ring frame." + (" Carries the wing: spar sits in the cradle under a printed cap." if i in (2, 3) else ""),
                          {"machine": "3-axis CNC router", "stock": f"{t:.0f} mm birch plywood (BS1088 / aircraft grade)",
                           "tools": "3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min", "setups": 1,
                           "workholding": "vacuum or screws in waste, 0.3 mm tabs"}))
    # spar caps (printed) on BH-3 / BH-4
    for i, (xb, sz, r) in enumerate(((xs[3], MAIN_SPAR_G[1], C.main_spar_od / 2), (xs[4], REAR_SPAR_G[1], C.rear_spar_od / 2))):
        t = C.bulkhead_t[2 + i]
        capw = 60.0
        cap = box(xb - t / 2 - 6, xb + t / 2 + 6, -capw / 2, capw / 2, sz, sz + r + 5) + \
            (cyl_x(r + 5, xb - t / 2 - 6, xb + t / 2 + 6, 0, sz) & box(xb - 20, xb + 20, -capw, capw, sz, sz + 30))
        cap = cap - cyl_x(r + 0.1, xb - 20, xb + 20, 0, sz) - box(xb - t / 2 - 0.1, xb + t / 2 + 0.1, -40, 40, sz - 30, sz + 0.0)
        for yy in (-22.0, 22.0):
            cap = cap - cyl_z(2.2, sz - 5, sz + r + 6, xb, yy)
        parts.append(Part(f"SC-{i + 1}", f"Spar cap ({'main' if i == 0 else 'rear'} spar)", "Fuselage", "FDM", "PA6-CF", cap,
                          [Location()], "Clamps the spar into the bulkhead cradle; 2 x M4 into heat-set inserts in printed tower blocks.", FDM_STRUCT))
    # Battery tray and avionics deck (CNC plywood)
    tray = box(-245, 415, -100, 100, C.fus_top - C.fus_h + 14, C.fus_top - C.fus_h + 17)
    for xx in (-200, -120, 250, 330):
        tray = tray - box(xx, xx + 50, -70, 70, -400, 400)
    for xx in (-70, 10, 90, 170):
        for yy in (-60, 60):
            tray = tray - box(xx, xx + 20, yy - 15, yy + 15, -400, 400)  # strap slots
    parts.append(Part("TRAY", "Battery tray", "Fuselage", "CNC", "Birch plywood", tray, [Location()],
                      "Carries four 6S packs (2 x 2) on velcro straps through the slots; rests on bulkhead rims.",
                      {"machine": "3-axis CNC router", "stock": "3 mm birch plywood", "setups": 1}))
    deck = box(-245, -55, -90, 90, -82, -79) - box(-200, -100, -20, 20, -100, 0)
    parts.append(Part("DECK", "Avionics deck", "Fuselage", "CNC", "Birch plywood", deck, [Location()],
                      "Pixhawk on 4 vibration dampers; receiver, telemetry and power module.", {"machine": "3-axis CNC router", "stock": "3 mm birch plywood"}))
    # Firewall (aluminium) for the pusher
    xfw = 748.0
    fw = prism_x(circle(47, 0, _tail_axis_z(), 72), xfw, xfw + 3)
    fw = fw - cyl_x(7.0, xfw - 1, xfw + 5, 0, _tail_axis_z())
    for a in (45, 135, 225, 315):
        ang = math.radians(a)
        for rr in np.linspace(12.5, 19, 6):
            fw = fw - cyl_x(1.7, xfw - 1, xfw + 5, rr * math.cos(ang), _tail_axis_z() + rr * math.sin(ang))
    for a in (0, 90, 180, 270):
        ang = math.radians(a)
        fw = fw - cyl_x(1.7, xfw - 1, xfw + 5, 41 * math.cos(ang), _tail_axis_z() + 41 * math.sin(ang))
    parts.append(Part("FW", "Pusher firewall plate", "Propulsion", "CNC", "6061-T6 aluminium", fw, [Location()],
                      "Bolts to the tail-cone boss ring (4 x M3 inserts). Motor cross-mount bolts on any 25-38 mm pattern (drilled pattern of holes).",
                      {"machine": "3-axis CNC", "stock": "3 mm 6061-T6 plate", "setups": 1}))
    # GPS mast
    mast = cyl_z(4.0, 0, 110) + cyl_z(22.0, 110, 114) + cyl_z(9.0, 0, 6)
    _, top = thickness_at(FOIL, 150)
    parts.append(Part("GPS-M", "GPS mast", "Fuselage", "FDM", "PETG", mast,
                      [wing_loc(0) * Pos(150, 0, top - 1)], "Raises the GPS above the wing and away from the ESC fields.",
                      {**FDM_STRUCT, "material": "PETG", "infill": "100 %"}))
    return parts


def _tail_axis_z() -> float:
    sec = fus_section(C.fus_x[-1] - 1)
    return float((sec[:, 1].max() + sec[:, 1].min()) / 2)


# ============================================================================ tail
def tail_parts() -> list[Part]:
    parts = []
    R = C.boom_od / 2
    ct = C.tail_chord
    blk_len = 180.0
    x1 = C.boom_aft
    x0 = x1 - blk_len
    # Tail block: sleeve over the boom end + fin socket (top) + stab socket (inboard)
    blk = tube_x(R + 5.0, R + 0.15, x0, x1)
    blk = blk + cyl_x(R + 5.0, x1 - 3, x1)
    # stab socket: NACA0010 section boss extending inboard 25 mm
    stab_pts = TAILFOIL + np.array([C.tail_le, 0])
    sock = prism_y(offset2d(stab_pts, 2.5), -(R + 25.0), -(R - 2.0))
    sock = sock - prism_y(offset2d(stab_pts, 0.15), -(R + 26.0), -(R + 3.0))
    blk = blk + sock
    # fin socket on top
    fin_root = naca4("0010", 170.0) + np.array([x1 - 170.0, 0])
    fsock = prism_z(offset2d(fin_root, 2.5), R - 2.0, R + 22.0) - prism_z(offset2d(fin_root, 0.15), R + 3.0, R + 23.0)
    blk = blk + fsock
    blk = blk - cyl_x(R + 0.15, x0 - 1, x1 - 3)
    for xb in (x0 + 15, x0 + 60):
        blk = blk - cyl_z(1.7, -R - 10, R + 10, xb, 0)
    blk_r = blk  # starboard; port is the mirror
    blk_l = mirror(blk_r, Plane.XZ)
    st = {**FDM_STRUCT, "orientation": "boom axis vertical"}
    parts.append(Part("TB-S", "Tail block, starboard", "Tail", "FDM", "PA6-CF", blk_r, [Pos(0, C.boom_y, 0)],
                      "Slides over the boom end; 2 x M3 cross bolts. Stab and fin sockets bonded.", st))
    parts.append(Part("TB-P", "Tail block, port (mirror)", "Tail", "FDM", "PA6-CF", blk_l, [Pos(0, -C.boom_y, 0)], "", st))
    # Horizontal stabiliser segments (between tail blocks)
    span_h = 2 * (C.boom_y - R - 3.0)
    n = 5
    seg_s = span_h / n
    hinge = 0.65 * ct
    outer = clip2d(TAILFOIL, xmax=hinge - 0.8)
    inner = offset2d(outer, -0.8)
    def hs_seg(pocket: bool):
        s = prism_y(outer, 0, seg_s) - prism_y(inner, 1.2, seg_s - 1.2)
        s = s + tube_y(3.0 + 1.0, 3.0, 0, seg_s, 0.30 * ct, 0) - cyl_y(3.1, -1, seg_s + 1, 0.30 * ct, 0)
        if pocket:
            s = s - box(20, 52, seg_s / 2 - 6, seg_s / 2 + 6, -10, 0.0)
        return s
    y0 = -C.boom_y + R + 3.0
    hs_places = [Pos(C.tail_le, y0 + k * seg_s, 0) for k in range(n) if k != 2]
    parts.append(Part("HS", "Horizontal stabiliser segment", "Tail", "FDM", "LW-PLA (foamed)", hs_seg(False), hs_places,
                      "Threaded on a 6 mm CF rod spar (1170 mm).", FDM_LW))
    parts.append(Part("HS-C", "Horizontal stabiliser centre (elevator servo)", "Tail", "FDM", "LW-PLA (foamed)", hs_seg(True),
                      [Pos(C.tail_le, y0 + 2 * seg_s, 0)], "Elevator servo pocket on the lower skin (servo partly protrudes into the stab; fair with tape).", FDM_LW))
    elev = _aileron(seg_s, 0.65, TAILFOIL, ct)
    parts.append(Part("ELV", "Elevator segment", "Tail", "FDM", "LW-PLA (foamed)", elev, [Pos(C.tail_le, y0 + k * seg_s, 0) for k in range(n)],
                      "Five segments on a 3 mm CF torque rod; horn on the centre piece.", FDM_LW))
    sp = cyl_y(3.0, 0, span_h + 40, 0.30 * ct, 0)
    parts.append(Part("HS-SP", "Stabiliser spar (6 mm CF rod)", "Tail", "COTS-cut", "Carbon fibre rod", sp,
                      [Pos(C.tail_le, y0 - 20, 0)], "", {"cut": f"{span_h + 40:.0f} mm"}, purchased=True))
    # Fin (tapered, swept) with rudder cut at 65 %
    h_fin = 230.0
    root_c, tip_c, sweep = 170.0, 105.0, 55.0
    def fin_profile(c, frac_cut):
        pts = naca4("0010", c)
        return clip2d(pts, xmax=frac_cut * c - 0.8)
    secs = []
    zs = [0.0, h_fin]
    secs_full = [naca4("0010", root_c, 50), naca4("0010", tip_c, 50) + np.array([sweep, 0])]
    fin_out = loft_sections([np.column_stack([s[:, 0], s[:, 1]]) for s in secs_full], zs, "z")
    # rudder split plane (x along chord at 65 %): approximate by a box cut along the hinge line
    hinge_root, hinge_tip = 0.65 * root_c, sweep + 0.65 * tip_c
    cutter = loft_sections([np.array([[hinge_root, -20], [400, -20], [400, 20], [hinge_root, 20]]),
                            np.array([[hinge_tip, -20], [400, -20], [400, 20], [hinge_tip, 20]])], [-1, h_fin + 1], "z")
    fin_fixed = fin_out - cutter
    rudder = fin_out & cutter
    fin_loc = [Pos(x1 - 170.0, C.boom_y, R + 3.0), Pos(x1 - 170.0, -C.boom_y, R + 3.0)]
    parts.append(Part("FIN", "Vertical fin", "Tail", "FDM", "LW-PLA (foamed)", fin_fixed, fin_loc,
                      "Printed hollow with 2 perimeters: 4 mm CF rod spar at 30 % chord; rudder servo at the root.",
                      {**FDM_LW, "walls": "2 perimeters", "infill": "0 %", "orientation": "root down", "print_wall_mm": 1.0}))
    parts.append(Part("RUD", "Rudder", "Tail", "FDM", "LW-PLA (foamed)", rudder, fin_loc, "",
                      {**FDM_LW, "walls": "2 perimeters", "orientation": "root down", "print_wall_mm": 1.0}))
    return parts


# ============================================================================ landing gear
LEG_X = (-150.0, 420.0)
LEG_SPLAY = 10.0


def gear_parts() -> list[Part]:
    parts = []
    R = C.boom_od / 2
    L = 40.0
    sock = tube_x(R + 4.5, R + 0.15, -L / 2, L / 2)
    # socket boss for a 12 mm leg, splayed outboard (built for the starboard side; port is mirror)
    bore = Solid.make_cylinder(6.1, 50.0, Plane(origin=(0, 0, -R + 2), z_dir=(0, math.sin(math.radians(LEG_SPLAY)), -math.cos(math.radians(LEG_SPLAY)))))
    boss = Solid.make_cylinder(10.0, 38.0, Plane(origin=(0, 0, -R + 4), z_dir=(0, math.sin(math.radians(LEG_SPLAY)), -math.cos(math.radians(LEG_SPLAY)))))
    s = sock + boss - bore - cyl_x(R + 0.15, -L, L)
    for xb in (-12, 12):
        s = s - cyl_z(1.7, -R - 12, R + 12, xb, 0)
    s_p = mirror(s, Plane.XZ)
    st = {**FDM_STRUCT, "orientation": "boom axis vertical"}
    parts.append(Part("LG-S", "Landing leg socket, starboard", "Landing gear", "FDM", "PA6-CF", s,
                      [Pos(x, C.boom_y, 0) for x in LEG_X], "Clamped to the boom with 2 x M3; leg bonded with epoxy.", st))
    parts.append(Part("LG-P", "Landing leg socket, port (mirror)", "Landing gear", "FDM", "PA6-CF", s_p,
                      [Pos(x, -C.boom_y, 0) for x in LEG_X], "", st))
    leg_len = (-C.ground_z - R - 4 - 15) / math.cos(math.radians(LEG_SPLAY))
    dirv = (0, math.sin(math.radians(LEG_SPLAY)), -math.cos(math.radians(LEG_SPLAY)))
    leg = Solid.make_cylinder(6.0, leg_len, Plane(origin=(0, 0, -R + 4), z_dir=dirv)) - \
        Solid.make_cylinder(5.0, leg_len + 2, Plane(origin=(0, 0, -R + 3), z_dir=dirv))
    end = np.array([0, 0, -R + 4]) + leg_len * np.array(dirv)
    foot = Solid.make_sphere(16.0).translate(tuple(end + np.array([0, 0, -1.0]))) - Solid.make_cylinder(6.1, 30, Plane(origin=tuple(end - 20 * np.array(dirv)), z_dir=dirv))
    foot = foot & box(-40, 40, -60, 80, C.ground_z, 0)
    legs_s = [Pos(x, C.boom_y, 0) for x in LEG_X]
    legs_p = [Pos(x, -C.boom_y, 0) * Rot(0, 0, 0) for x in LEG_X]
    parts.append(Part("LG-T", "Landing leg (12x10 CF tube)", "Landing gear", "COTS-cut", "Carbon fibre tube", leg, legs_s,
                      f"Cut 4 to {leg_len:.0f} mm.", {"cut": f"{leg_len:.0f} mm x 4"}, purchased=True))
    parts.append(Part("LG-F", "Landing foot", "Landing gear", "FDM", "TPU 95A", foot, legs_s,
                      "Shock-absorbing foot; 3 walls, 25 % gyroid.", {**FDM_STRUCT, "material": "TPU 95A", "infill": "25 % gyroid", "walls": "3"}))
    # port legs as mirrored solids
    parts.append(Part("LG-TP", "Landing leg (port)", "Landing gear", "COTS-cut", "Carbon fibre tube", mirror(leg, Plane.XZ), legs_p, "", {"cut": "same as LG-T"}, purchased=True))
    parts.append(Part("LG-FP", "Landing foot (port)", "Landing gear", "FDM", "TPU 95A", mirror(foot, Plane.XZ), legs_p, "", {**FDM_STRUCT, "material": "TPU 95A"}))
    return parts


def rotor_spins() -> list[tuple[float, float, int]]:
    """(x, y, spin) of each lift rotor in mm; spin +1 = CCW seen from above."""
    xcg = SEL["geometry"]["x_cg_target"]
    return [((r["x"] + xcg) * 1000, r["y"] * 1000, r["spin"]) for r in SEL["layout"]]


# ============================================================================ purchased hardware (visual + mass)
def _prop_blade(D_in: float, pitch_in: float, hub_r: float, chord_max: float, blades: int = 2, ccw: bool = False) -> Solid:
    R = D_in * 25.4 / 2
    rs = np.linspace(hub_r, R * 0.985, 10)
    secs, stations = [], []
    for r in rs:
        xr = r / R
        c = chord_max * (0.55 + 1.6 * xr * (1 - xr) ** 0.9) * (1.0 if xr < 0.97 else 0.6)
        c = max(c, 6.0)
        beta = math.atan(pitch_in * 25.4 / (2 * math.pi * r))
        t = c * (0.14 - 0.07 * xr)
        prof = naca4("4412", c, 30)
        prof = prof - np.array([0.35 * c, 0])
        prof[:, 1] *= t / (0.12 * c)
        ca, sa = math.cos(beta), math.sin(beta)
        rot = np.column_stack([prof[:, 0] * ca - prof[:, 1] * sa, prof[:, 0] * sa + prof[:, 1] * ca])
        if ccw:
            rot[:, 0] *= -1
        secs.append(rot)
        stations.append(r)
    blade = loft_sections(secs, stations, "y")  # blade along +y, section in x (tangential) / z (axial)
    out = blade
    for k in range(1, blades):
        out = out + blade.rotate(__import__("build123d").Axis.Z, 360 / blades * k)
    hub = cyl_z(hub_r + 2, -6, 8)
    return out + hub


def hardware_parts() -> list[Part]:
    parts = []
    R = C.boom_od / 2
    # MN5008: Ø55.6 x 32 bell on top of the seat
    mot = cyl_z(27.8, 0, 26) + cyl_z(20.0, 26, 32) + cyl_z(3.0, 32, 42)
    places = [Pos(x, y, SEAT_Z) for y in (-C.boom_y, C.boom_y) for x in C.rotor_x]
    parts.append(Part("MOT-L", "T-Motor MN5008 KV170 lift motor", "Propulsion", "COTS", "purchased", mot, places, "", {}, purchased=True))
    prop_cw = _prop_blade(18, 6.1, 14, 34)
    prop_ccw = _prop_blade(18, 6.1, 14, 34, ccw=True)
    sp = rotor_spins()
    cw_pl = [Pos(x, y, SEAT_Z + 36) for (x, y, s) in sp if s < 0]
    ccw_pl = [Pos(x, y, SEAT_Z + 36) for (x, y, s) in sp if s > 0]
    parts.append(Part("PROP-CW", "T-Motor P18x6.1 propeller (CW)", "Propulsion", "COTS", "purchased", prop_cw, cw_pl, "", {}, purchased=True))
    parts.append(Part("PROP-CCW", "T-Motor P18x6.1 propeller (CCW)", "Propulsion", "COTS", "purchased", prop_ccw, ccw_pl, "", {}, purchased=True))
    esc = box(-35, 35, -16, 16, -R - 21, -R - 6)
    parts.append(Part("ESC-L", "T-Motor FLAME 60A 12S ESC", "Propulsion", "COTS", "purchased", esc,
                      [Pos(x, y, 0) for y in (-C.boom_y, C.boom_y) for x in C.rotor_x], "", {}, purchased=True))
    za = _tail_axis_z()
    pm = cyl_x(25.0, 751, 830, 0, za) + cyl_x(3.0, 830, 860, 0, za)
    parts.append(Part("MOT-P", "T-Motor AT4130 KV230 pusher motor", "Propulsion", "COTS", "purchased", pm, [Location()], "", {}, purchased=True))
    pprop = _prop_blade(17, 10, 12, 40)
    from build123d import Axis
    pprop = pprop.rotate(Axis.Y, 90).translate((850, 0, za))
    parts.append(Part("PROP-P", "APC 17x10EP pusher propeller", "Propulsion", "COTS", "purchased", pprop, [Location()], "", {}, purchased=True))
    spinner = Solid.make_cone(21.0, 4.0, 40, Plane(origin=(852, 0, za), z_dir=(1, 0, 0)))
    parts.append(Part("SPIN", "Pusher spinner (45 mm)", "Propulsion", "COTS", "purchased", spinner, [Location()], "", {}, purchased=True))
    # Batteries: packs side by side (2 per 12S string), strings stacked; x from the CG solution
    bat_key = SEL["design"]["battery"]
    L, W, H = json.loads((ROOT / "design" / "components.json").read_text())[bat_key]["dims_mm"]
    n = SEL["design"]["n_battery"]
    xb = SEL["mass"]["x_battery"] * 1000
    zt = C.fus_top - C.fus_h + 17
    bat = box(-L / 2, L / 2, -W / 2, W / 2, 0, H)
    bpl = [Pos(xb, yy, zt + k * (H + 1)) for k in range(n // 2) for yy in (-(W / 2 + 1), W / 2 + 1)]
    parts.append(Part("BAT", f"Tattu {bat_key.split('_')[1]} mAh 6S LiPo", "Power", "COTS", "purchased", bat, bpl, "", {}, purchased=True))
    fc = box(-46, 46, -25.5, 25.5, 0, 28)
    parts.append(Part("FC", "Holybro Pixhawk 6X", "Avionics", "COTS", "purchased", fc, [Pos(-150, 0, -79)], "", {}, purchased=True))
    gps = cyl_z(25, 0, 15)
    _, top = thickness_at(FOIL, 150)
    parts.append(Part("GPS", "Holybro M10 GPS", "Avionics", "COTS", "purchased", gps, [wing_loc(0) * Pos(150, 0, top + 113)], "", {}, purchased=True))
    # Servos: ailerons (W-A1 pockets), elevator (HS-C), rudders (fin roots)
    servo = box(-16, 16, -6, 6, 0, 30)
    lo, _ = thickness_at(FOIL, 150)
    y_a1 = RIB_Y1 + 2 * OUTER_SPAN + OUTER_SPAN / 2
    s_pl = [wing_loc(y) * Pos(150, 0, lo + 1) for y in (y_a1, -y_a1)]
    s_pl += [Pos(C.tail_le + 36, 0, -24), Pos(C.boom_aft - 120, C.boom_y, C.boom_od / 2 + 5),
             Pos(C.boom_aft - 120, -C.boom_y, C.boom_od / 2 + 5)]
    parts.append(Part("SRV", "25 g metal-gear servo", "Avionics", "COTS", "purchased", servo, s_pl, "", {}, purchased=True))
    return parts
