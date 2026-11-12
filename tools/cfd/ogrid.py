"""Structured 2-D O-grid around an airfoil, written directly as an OpenFOAM polyMesh.

The grid is one cell thick in z (front/back = empty).  Wall-normal spacing grows
geometrically from `ds_wall` to a circular far field of radius `R_far` chords.
Interior points are smoothed with Laplace iterations, keeping the first
`n_fixed` wall layers orthogonal.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def resample_surface(pts: np.ndarray, n: int, te_cluster: float = 0.3) -> np.ndarray:
    """Re-distribute a closed TE->upper->LE->lower->TE profile with n points,
    clustered at the leading and trailing edges (cosine in arc length per side)."""
    pts = np.asarray(pts, float)
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    i_le = int(np.argmin(pts[:, 0]))
    s_le, s_tot = s[i_le], s[-1]
    nh = n // 2
    t = (1 - np.cos(np.linspace(0, np.pi, nh + 1))) / 2
    t = (1 - te_cluster) * t + te_cluster * np.linspace(0, 1, nh + 1)
    su = s_le * t
    sl = s_le + (s_tot - s_le) * t
    snew = np.concatenate([su, sl[1:-1]])
    return np.column_stack([np.interp(snew, s, pts[:, 0]), np.interp(snew, s, pts[:, 1])])


def build_ogrid(surf: np.ndarray, nj: int, ds_wall: float, R_far: float, chord: float,
                n_fixed: int = 25, smooth_iter: int = 400) -> np.ndarray:
    """Return grid X[ni, nj, 2] (periodic in i, j=0 on the wall)."""
    ni = len(surf)
    # outward normals (profile is clockwise: TE->upper->LE->lower)
    tang = np.roll(surf, -1, axis=0) - np.roll(surf, 1, axis=0)
    nrm = np.column_stack([tang[:, 1], -tang[:, 0]])
    nrm /= np.linalg.norm(nrm, axis=1)[:, None]
    # make sure normals point outward (away from the centroid)
    c = surf.mean(axis=0)
    if np.mean(np.sum((surf - c) * nrm, axis=1)) < 0:
        nrm = -nrm
    # geometric stretching to reach R_far*chord
    target = R_far * chord
    lo, hi = 1.0001, 1.5
    for _ in range(100):
        r = 0.5 * (lo + hi)
        L = ds_wall * (r ** (nj - 1) - 1) / (r - 1)
        lo, hi = (r, hi) if L < target else (lo, r)
    d = ds_wall * (r ** np.arange(nj) - 1) / (r - 1)
    # far-field circle points matched by arc-length fraction
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([surf, surf[:1]]), axis=0), axis=1))])
    frac = s[:-1] / s[-1]
    i_te = 0
    ang0 = np.arctan2(surf[i_te, 1] - c[1], surf[i_te, 0] - c[0])
    theta = ang0 + 2 * np.pi * frac  # same winding as the surface (TE->upper->LE)
    upper_first = surf[ni // 4, 1] > c[1]
    if not upper_first:
        theta = ang0 - 2 * np.pi * frac
    far = c + target * np.column_stack([np.cos(theta), np.sin(theta)])
    X = np.zeros((ni, nj, 2))
    for j in range(nj):
        f = (d[j] / target) ** 0.6
        near = surf + nrm * d[j]
        X[:, j] = (1 - f) * near + f * far
    # Laplace smoothing of the interior (periodic in i)
    # smoothing weight ramps in over 30 layers beyond the frozen near-wall layers
    ramp = np.clip((np.arange(nj) - n_fixed) / 30.0, 0, 1)[None, n_fixed:-1, None]
    for _ in range(smooth_iter):
        Xn = X.copy()
        # spacing-weighted radial average keeps the wall-normal stretching;
        # the circumferential average removes crossing grid lines
        a = np.linalg.norm(X[:, n_fixed + 1:] - X[:, n_fixed:-1], axis=2)
        b = np.linalg.norm(X[:, n_fixed:-1] - X[:, n_fixed - 1:-2], axis=2)
        w_out = (b / (a + b))[..., None]
        radial = w_out * X[:, n_fixed + 1:] + (1 - w_out) * X[:, n_fixed - 1:-2]
        circ = 0.5 * (np.roll(X, 1, 0)[:, n_fixed:-1] + np.roll(X, -1, 0)[:, n_fixed:-1])
        Xn[:, n_fixed:-1] = X[:, n_fixed:-1] + 0.3 * ramp * (0.5 * radial + 0.5 * circ - X[:, n_fixed:-1])
        if inverted_cells(Xn) > 0:  # never accept a step that folds the grid
            break
        X = Xn
    return X


def build_ogrid_march(surf: np.ndarray, nj: int, ds_wall: float, R_far: float, chord: float) -> np.ndarray:
    """Normal-marching O-grid: each layer is offset along the smoothed normals of the
    previous one, giving near-orthogonal cells; layer smoothing grows with distance
    so the grid becomes a uniform near-circle in the far field."""
    ni = len(surf)
    target = R_far * chord
    lo, hi = 1.0001, 1.5
    for _ in range(100):
        r = 0.5 * (lo + hi)
        L = ds_wall * (r ** (nj - 1) - 1) / (r - 1)
        lo, hi = (r, hi) if L < target else (lo, r)
    d = ds_wall * (r ** np.arange(nj) - 1) / (r - 1)
    c = surf.mean(axis=0)
    X = np.zeros((ni, nj, 2))
    X[:, 0] = surf
    layer = surf.copy()
    for j in range(1, nj):
        tang = np.roll(layer, -1, axis=0) - np.roll(layer, 1, axis=0)
        nrm = np.column_stack([tang[:, 1], -tang[:, 0]])
        nrm /= np.linalg.norm(nrm, axis=1)[:, None]
        if np.mean(np.sum((layer - c) * nrm, axis=1)) < 0:
            nrm = -nrm
        # blend toward the radial direction far away (keeps the outer boundary round)
        rad = layer - c
        rad /= np.linalg.norm(rad, axis=1)[:, None]
        f = (d[j] / target) ** 0.5
        dirv = (1 - f) * nrm + f * rad
        dirv /= np.linalg.norm(dirv, axis=1)[:, None]
        new = layer + dirv * (d[j] - d[j - 1])
        # smoothing grows with distance from the wall (equalises spacing, opens the TE fan)
        eps = min(0.45, 0.02 + 0.6 * (d[j] / chord) ** 0.5)
        for _ in range(3 if d[j] < 0.05 * chord else 8):
            disp = 0.5 * (np.roll(new, 1, 0) + np.roll(new, -1, 0)) - new
            if d[j] < 0.5 * chord:  # tangential only near the body: no curvature shrink into the wall
                disp -= np.sum(disp * dirv, axis=1)[:, None] * dirv
            new = new + eps * disp
        X[:, j] = new
        layer = new
    return X


def inverted_cells(X: np.ndarray) -> int:
    """Number of quads whose orientation differs from the majority."""
    A, B = X[:, :-1], np.roll(X, -1, 0)[:, :-1]
    Cc, D = np.roll(X, -1, 0)[:, 1:], X[:, 1:]
    area = (Cc - A)[..., 0] * (D - B)[..., 1] - (Cc - A)[..., 1] * (D - B)[..., 0]
    sign = np.sign(np.median(area))
    return int(np.sum(area * sign <= 0))


def write_polymesh(X: np.ndarray, case: Path, dz: float = 0.01) -> dict:
    """Write an O-grid X[ni, nj, 2] as a one-cell-thick polyMesh."""
    ni, nj, _ = X.shape
    pm = case / "constant" / "polyMesh"
    pm.mkdir(parents=True, exist_ok=True)
    pid = lambda i, j, k: k * ni * nj + j * ni + (i % ni)
    pts = np.zeros((2 * ni * nj, 3))
    for k, z in enumerate((0.0, dz)):
        for j in range(nj):
            for i in range(ni):
                pts[pid(i, j, k)] = (X[i, j, 0], X[i, j, 1], z)
    cid = lambda i, j: j * ni + (i % ni)
    nc = ni * (nj - 1)
    faces, owner, neigh = [], [], []
    # internal faces: radial (between i and i+1) and circumferential (between j and j+1)
    for j in range(nj - 1):
        for i in range(ni):
            # face between cell (i-1,j) and (i,j): points at i, j..j+1
            a, b = cid(i - 1, j), cid(i, j)
            f = [pid(i, j, 0), pid(i, j, 1), pid(i, j + 1, 1), pid(i, j + 1, 0)]
            o, n = (a, b) if a < b else (b, a)
            if o != a:
                f = f[::-1]
            faces.append(f); owner.append(o); neigh.append(n)
    for j in range(1, nj - 1):
        for i in range(ni):
            a, b = cid(i, j - 1), cid(i, j)
            f = [pid(i, j, 0), pid(i + 1, j, 0), pid(i + 1, j, 1), pid(i, j, 1)]
            faces.append(f); owner.append(a); neigh.append(b)
    # OpenFOAM requires internal faces in upper-triangular order
    order = sorted(range(len(faces)), key=lambda k: (owner[k], neigh[k]))
    faces = [faces[k] for k in order]; owner = [owner[k] for k in order]; neigh = [neigh[k] for k in order]
    # orientation: face normal must point from owner to neighbour
    P = pts
    def centroid(c):
        j, i = divmod(c, ni)
        q = [pid(i, j, 0), pid(i + 1, j, 0), pid(i + 1, j + 1, 0), pid(i, j + 1, 0)]
        return P[q].mean(axis=0) + np.array([0, 0, dz / 2])
    cents = np.array([centroid(c) for c in range(nc)])
    def fnormal(f):
        p = P[f]
        return np.cross(p[2] - p[0], p[3] - p[1])
    for k, f in enumerate(faces):
        if np.dot(fnormal(f), cents[neigh[k]] - cents[owner[k]]) < 0:
            faces[k] = f[::-1]
    n_internal = len(faces)
    patches = []
    # wall (j=0)
    start = len(faces)
    for i in range(ni):
        f = [pid(i, 0, 0), pid(i, 0, 1), pid(i + 1, 0, 1), pid(i + 1, 0, 0)]
        c = cid(i, 0)
        if np.dot(fnormal(f), P[f].mean(axis=0) - cents[c]) < 0:
            f = f[::-1]
        faces.append(f); owner.append(c)
    patches.append(("airfoil", "wall", start, ni))
    start = len(faces)
    for i in range(ni):
        f = [pid(i, nj - 1, 0), pid(i + 1, nj - 1, 0), pid(i + 1, nj - 1, 1), pid(i, nj - 1, 1)]
        c = cid(i, nj - 2)
        if np.dot(fnormal(f), P[f].mean(axis=0) - cents[c]) < 0:
            f = f[::-1]
        faces.append(f); owner.append(c)
    patches.append(("farfield", "patch", start, ni))
    for name, k in (("back", 0), ("front", 1)):
        start = len(faces)
        for j in range(nj - 1):
            for i in range(ni):
                f = [pid(i, j, k), pid(i + 1, j, k), pid(i + 1, j + 1, k), pid(i, j + 1, k)]
                c = cid(i, j)
                if np.dot(fnormal(f), P[f].mean(axis=0) - cents[c]) < 0:
                    f = f[::-1]
                faces.append(f); owner.append(c)
        patches.append((name, "empty", start, nc))

    hdr = lambda cls, obj, note="": ("FoamFile\n{\n    version 2.0;\n    format ascii;\n    class " + cls +
                                     ";\n    location \"constant/polyMesh\";\n    object " + obj + ";\n" + note + "}\n\n")
    with open(pm / "points", "w") as fh:
        fh.write(hdr("vectorField", "points"))
        fh.write(f"{len(P)}\n(\n" + "\n".join(f"({p[0]:.10g} {p[1]:.10g} {p[2]:.10g})" for p in P) + "\n)\n")
    with open(pm / "faces", "w") as fh:
        fh.write(hdr("faceList", "faces"))
        fh.write(f"{len(faces)}\n(\n" + "\n".join("4(" + " ".join(map(str, f)) + ")" for f in faces) + "\n)\n")
    note = f"    note \"nPoints:{len(P)} nCells:{nc} nFaces:{len(faces)} nInternalFaces:{n_internal}\";\n"
    with open(pm / "owner", "w") as fh:
        fh.write(hdr("labelList", "owner", note))
        fh.write(f"{len(owner)}\n(\n" + "\n".join(map(str, owner)) + "\n)\n")
    with open(pm / "neighbour", "w") as fh:
        fh.write(hdr("labelList", "neighbour", note))
        fh.write(f"{len(neigh)}\n(\n" + "\n".join(map(str, neigh)) + "\n)\n")
    with open(pm / "boundary", "w") as fh:
        fh.write(hdr("polyBoundaryMesh", "boundary"))
        fh.write(f"{len(patches)}\n(\n")
        for name, typ, st, n in patches:
            extra = "        inGroups List<word> 1(wall);\n" if typ == "wall" else ""
            fh.write(f"    {name}\n    {{\n        type {typ};\n{extra}        nFaces {n};\n        startFace {st};\n    }}\n")
        fh.write(")\n")
    return dict(cells=nc, ni=ni, nj=nj)
