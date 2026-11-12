"""Outer-mould-line solids for CFD, built from the same parameters as the CAD parts.

Internal structure is omitted; each region is a closed solid in millimetres.
Regions: fuselage, wing, tail, booms, rotors (nacelles + motors + stopped blades), gear.
"""
from __future__ import annotations

import math

import numpy as np
from build123d import Axis, Pos, Solid

from . import parts as P
from .geom import circle, cyl_x, cyl_z, loft_sections, naca4, prism_y, prism_z, superellipse

C = P.C


def fuselage() -> Solid:
    xs = list(np.linspace(C.fus_x[0], C.fus_x[1], 8)) + list(np.linspace(C.fus_x[1] + 40, 420, 4)) + \
        list(np.linspace(460, C.fus_x[-1], 6))
    body = loft_sections([P.fus_section(x) for x in xs], xs, "x")
    za = P._tail_axis_z()
    spinner = Solid.make_cone(21.0, 3.0, 40, P.Plane(origin=(C.fus_x[-1], 0, za), z_dir=(1, 0, 0)))
    hub = cyl_x(21.0, C.fus_x[-1] - 2, C.fus_x[-1] + 2, 0, za)
    _, top = P.thickness_at(P.FOIL, 150)
    mast = (cyl_z(4.0, 0, 110) + cyl_z(25.0, 110, 125)).moved(P.wing_loc(0) * Pos(150, 0, top - 1))
    return body + spinner + hub + mast


def wing(half: bool = False) -> Solid:
    y0 = 0.0 if half else -P.HALF + C.tip_len
    w = prism_y(P.FOIL, y0, P.HALF - C.tip_len)
    tip = loft_sections([P.FOIL, P.FOIL * np.array([1.0, 0.55]), P.FOIL * np.array([0.92, 0.18]) + np.array([12, 0])],
                        [P.HALF - C.tip_len, P.HALF - 0.4 * C.tip_len, P.HALF], axis="y")
    w = w + tip
    if not half:
        w = w + tip.mirror(P.Plane.XZ)
    return w.moved(P.wing_loc(0))


def tail() -> Solid:
    R = C.boom_od / 2
    span_h = 2 * C.boom_y
    stab = prism_y(P.TAILFOIL, -span_h / 2, span_h / 2).moved(Pos(C.tail_le, 0, 0))
    root_c, tip_c, sweep, h = 170.0, 105.0, 55.0, 230.0
    fin = loft_sections([naca4("0010", root_c, 50), naca4("0010", tip_c, 50) + np.array([sweep, 0])], [0.0, h], "z")
    out = stab
    for y in (-C.boom_y, C.boom_y):
        out = out + fin.moved(Pos(C.boom_aft - 170.0, y, R + 3.0))
        out = out + cyl_x(R + 5.0, C.boom_aft - 180, C.boom_aft, y, 0)
    return out


def booms() -> Solid:
    R = C.boom_od / 2
    out = None
    for y in (-C.boom_y, C.boom_y):
        b = cyl_x(R, C.boom_front, C.boom_aft - 180, y, 0)
        b = b + Solid.make_cone(R, 4.0, 30, P.Plane(origin=(C.boom_front, y, 0), z_dir=(-1, 0, 0)))
        b = b + (P.box(P.SADDLE_X0, P.SADDLE_X1, y - 18, y + 18, -R - 5, P.SADDLE_TOP))
        out = b if out is None else out + b
    return out


def rotors(blade_angle_deg: float = 45.0) -> Solid:
    """Stopped lift rotors: nacelle (upper + ESC pod), motor and blades at a fixed azimuth."""
    R = C.boom_od / 2
    xs_p = np.linspace(-P.NAC_LEN / 2, P.NAC_LEN / 2, 40)
    half = 30.0 * np.sqrt(np.clip(1 - (2 * xs_p / P.NAC_LEN) ** 2, 0, 1)) ** 0.7
    plan = np.vstack([np.column_stack([xs_p, half]), np.column_stack([xs_p[::-1], -half[::-1]])])
    plan = np.array([p for i, p in enumerate(plan) if i == 0 or not np.allclose(p, plan[i - 1])])
    nac = prism_z(plan, -2.0, P.SEAT_Z) + cyl_z(29.0, P.SEAT_Z - 4, P.SEAT_Z)
    pod = prism_z(superellipse(100.0, 44.0, 0.0, 3.2, 64), -R - 24, 0.0)
    mot = cyl_z(27.8, P.SEAT_Z, P.SEAT_Z + 26) + cyl_z(20.0, P.SEAT_Z + 26, P.SEAT_Z + 32) + cyl_z(3.0, P.SEAT_Z + 32, P.SEAT_Z + 42)
    unit = nac + pod + mot
    out = None
    for (x, y, spin) in P.rotor_spins():
        blades = P._prop_blade(18, 6.1, 14, 34, ccw=spin > 0).rotate(Axis.Z, blade_angle_deg)
        u = (unit + blades.moved(Pos(0, 0, P.SEAT_Z + 36))).moved(Pos(x, y, 0))
        out = u if out is None else out + u
    return out


def gear() -> Solid:
    R = C.boom_od / 2
    out = None
    for y, s in ((C.boom_y, 1), (-C.boom_y, -1)):
        for x in P.LEG_X:
            dirv = (0, s * math.sin(math.radians(P.LEG_SPLAY)), -math.cos(math.radians(P.LEG_SPLAY)))
            L = (-C.ground_z - R - 4 - 15) / math.cos(math.radians(P.LEG_SPLAY))
            leg = Solid.make_cylinder(6.0, L, P.Plane(origin=(x, y, -R + 4), z_dir=dirv))
            end = np.array([x, y, -R + 4]) + L * np.array(dirv)
            foot = cyl_z(16.0, end[2] - 8, end[2] + 8, end[0], end[1])  # TPU foot as a disc for the CFD surface
            sock = cyl_x(R + 4.5, x - 20, x + 20, y, 0)
            g = leg + foot + sock
            out = g if out is None else out + g
    return out


REGIONS = {"fuselage": fuselage, "wing": wing, "tail": tail, "booms": booms, "rotors": rotors, "gear": gear}
