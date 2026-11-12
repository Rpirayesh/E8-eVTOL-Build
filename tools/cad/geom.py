"""Geometry helpers shared by the part generators (millimetres)."""
from __future__ import annotations

import math

import numpy as np
from build123d import (Axis, Box, Cylinder, Edge, Face, Location, Plane, Pos, Rot, Solid,
                       Vector, Wire, extrude)
from shapely.geometry import Polygon


# --------------------------------------------------------------------------- airfoils
def naca4(code: str, chord: float, n: int = 70) -> np.ndarray:
    """Closed NACA 4-digit profile (x, z), TE -> upper -> LE -> lower, cosine spacing.

    The trailing edge is given a 0.6 mm thickness so printed and machined parts
    have a real edge rather than a knife edge.
    """
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    beta = np.linspace(0, np.pi, n)
    x = (1 - np.cos(beta)) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4)
    if m == 0:
        yc = np.zeros_like(x)
        dyc = np.zeros_like(x)
    else:
        yc = np.where(x < p, m / p**2 * (2 * p * x - x**2), m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2))
        dyc = np.where(x < p, 2 * m / p**2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x))
    th = np.arctan(dyc)
    yt = np.maximum(yt, 0.3 / chord * np.clip(x, 0, 1))  # finite TE thickness
    xu, zu = x - yt * np.sin(th), yc + yt * np.cos(th)
    xl, zl = x + yt * np.sin(th), yc - yt * np.cos(th)
    pts = np.vstack([np.column_stack([xu[::-1], zu[::-1]]), np.column_stack([xl[1:], zl[1:]])]) * chord
    # drop duplicated TE point if closed
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    return pts


def camber_z(code: str, chord: float, x: float) -> float:
    m, p = int(code[0]) / 100, int(code[1]) / 10
    xc = x / chord
    if m == 0:
        return 0.0
    if xc < p:
        return chord * m / p**2 * (2 * p * xc - xc**2)
    return chord * m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * xc - xc**2)


def thickness_at(pts: np.ndarray, x: float) -> tuple[float, float]:
    """Lower and upper z of a closed profile at chordwise station x."""
    poly = Polygon(pts)
    from shapely.geometry import LineString
    cut = poly.intersection(LineString([(x, -1e4), (x, 1e4)]))
    zs = [c[1] for c in cut.coords] if hasattr(cut, "coords") else [c[1] for g in cut.geoms for c in g.coords]
    return min(zs), max(zs)


def offset2d(pts: np.ndarray, d: float) -> np.ndarray:
    """Inward (d<0) or outward offset of a closed 2-D profile."""
    poly = Polygon(pts).buffer(d, join_style=2, mitre_limit=3.0)
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return np.array(poly.exterior.coords)[:-1]


def clip2d(pts: np.ndarray, xmin=-1e9, xmax=1e9, zmin=-1e9, zmax=1e9) -> np.ndarray:
    from shapely.geometry import box
    poly = Polygon(pts).intersection(box(xmin, zmin, xmax, zmax))
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return np.array(poly.exterior.coords)[:-1]


# --------------------------------------------------------------------------- faces / solids
def face_xz(pts: np.ndarray, y: float = 0.0) -> Face:
    """Planar face in the XZ plane (at span station y) from 2-D (x, z) points."""
    verts = [Vector(float(p[0]), y, float(p[1])) for p in pts]
    return Face(Wire.make_polygon(verts, close=True))


def face_yz(pts: np.ndarray, x: float = 0.0) -> Face:
    verts = [Vector(x, float(p[0]), float(p[1])) for p in pts]
    return Face(Wire.make_polygon(verts, close=True))


def face_xy(pts: np.ndarray, z: float = 0.0) -> Face:
    verts = [Vector(float(p[0]), float(p[1]), z) for p in pts]
    return Face(Wire.make_polygon(verts, close=True))


def prism_y(pts: np.ndarray, y0: float, y1: float) -> Solid:
    """Extrude an XZ profile from span station y0 to y1."""
    return extrude(face_xz(pts, y0), y1 - y0, dir=(0, 1, 0))


def prism_x(pts: np.ndarray, x0: float, x1: float) -> Solid:
    return extrude(face_yz(pts, x0), x1 - x0, dir=(1, 0, 0))


def prism_z(pts: np.ndarray, z0: float, z1: float) -> Solid:
    return extrude(face_xy(pts, z0), z1 - z0, dir=(0, 0, 1))


def loft_sections(sections: list[np.ndarray], stations: list[float], axis: str = "x") -> Solid:
    """Loft closed sections (same point count) placed along an axis."""
    wires = []
    for pts, s in zip(sections, stations):
        if axis == "x":
            verts = [Vector(s, float(p[0]), float(p[1])) for p in pts]
        elif axis == "y":
            verts = [Vector(float(p[0]), s, float(p[1])) for p in pts]
        else:
            verts = [Vector(float(p[0]), float(p[1]), s) for p in pts]
        wires.append(Wire.make_polygon(verts, close=True))
    return Solid.make_loft(wires, ruled=False)


def superellipse(w: float, h: float, zc: float = 0.0, n: float = 2.6, npts: int = 72) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, npts, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    y = w / 2 * np.sign(c) * np.abs(c) ** (2 / n)
    z = zc + h / 2 * np.sign(s) * np.abs(s) ** (2 / n)
    return np.column_stack([y, z])


def circle(r: float, cy: float = 0.0, cz: float = 0.0, npts: int = 48) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, npts, endpoint=False)
    return np.column_stack([cy + r * np.cos(t), cz + r * np.sin(t)])


def rounded_rect(a: float, b: float, r: float, ca: float = 0.0, cb: float = 0.0) -> np.ndarray:
    from shapely.geometry import box
    poly = box(ca - a / 2 + r, cb - b / 2 + r, ca + a / 2 - r, cb + b / 2 - r).buffer(r, quad_segs=6)
    return np.array(poly.exterior.coords)[:-1]


def cyl_x(r: float, x0: float, x1: float, y: float = 0.0, z: float = 0.0) -> Solid:
    return Solid.make_cylinder(r, x1 - x0, Plane(origin=(x0, y, z), z_dir=(1, 0, 0)))


def cyl_y(r: float, y0: float, y1: float, x: float = 0.0, z: float = 0.0) -> Solid:
    return Solid.make_cylinder(r, y1 - y0, Plane(origin=(x, y0, z), z_dir=(0, 1, 0)))


def cyl_z(r: float, z0: float, z1: float, x: float = 0.0, y: float = 0.0) -> Solid:
    return Solid.make_cylinder(r, z1 - z0, Plane(origin=(x, y, z0), z_dir=(0, 0, 1)))


def tube_x(ro: float, ri: float, x0: float, x1: float, y: float = 0.0, z: float = 0.0) -> Solid:
    return cyl_x(ro, x0, x1, y, z) - cyl_x(ri, x0 - 1, x1 + 1, y, z)


def tube_y(ro: float, ri: float, y0: float, y1: float, x: float = 0.0, z: float = 0.0) -> Solid:
    return cyl_y(ro, y0, y1, x, z) - cyl_y(ri, y0 - 1, y1 + 1, x, z)


def box(x0, x1, y0, y1, z0, z1) -> Solid:
    return Solid.make_box(x1 - x0, y1 - y0, z1 - z0, Plane(origin=(x0, y0, z0)))


def arc_slot_z(r_in: float, r_out: float, ang_c: float, half_ang: float, z0: float, z1: float, cx=0.0, cy=0.0, width=3.4) -> Solid:
    """Radial slot (for an unknown bolt circle between r_in and r_out) at angle ang_c (deg)."""
    a = math.radians(ang_c)
    L = r_out - r_in
    pts = rounded_rect(L + width, width, width / 2 - 0.01)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    pts = (pts + np.array([(r_in + r_out) / 2, 0])) @ rot.T + np.array([cx, cy])
    return prism_z(pts, z0, z1)
