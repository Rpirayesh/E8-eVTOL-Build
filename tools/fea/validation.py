"""Verification of the structural tools against closed-form solutions.

V1  CalculiX C3D10: cantilever bar, tip load, mesh-convergence study (deflection, stress).
V2  Frame solver: cantilever tube with tip load and point mass (deflection, stress,
    first bending frequency) vs Euler-Bernoulli and the Dunkerley/Rayleigh result.
V3  Cross-check: the same tube in CalculiX C3D10 vs the frame solver.

    python tools/fea/validation.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cad.geom import box, tube_x  # noqa: E402
from fea import ccx  # noqa: E402
from fea.frame import Frame, Section  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "fea" / "validation"
WORK = ROOT / ".cache" / "fea" / "validation"


def v1():
    L, b, h, P = 200.0, 20.0, 10.0, 100.0
    mat = ccx.MATERIALS["6061-T6"]
    I = b * h**3 / 12
    G = mat.E / (2 * (1 + mat.nu))
    d_eb = P * L**3 / (3 * mat.E * I)
    d_tim = d_eb + P * L / (5 / 6 * G * b * h)
    sig_mid = P * (L / 2) * (h / 2) / I
    rows = []
    for hmax in (5.0, 3.0, 2.0, 1.25):
        m = ccx.mesh_solid(box(0, L, -b / 2, b / 2, -h / 2, h / 2), WORK / f"v1_{hmax}", hmax, hmax / 3)
        fixed = m.ids[m.nodes[:, 0] < 1e-6]
        faces = ccx.boundary_faces(m)
        cent, nrm, _ = ccx.face_props(m, faces)
        tip = faces[cent[:, 0] > L - 1e-6]
        res = ccx.solve(m, mat, fixed, ccx.traction_loads(m, tip, np.array([0, 0, -P])), "v1")
        # tip deflection at the neutral axis and bending stress at mid-span top fibre
        ix = m.idx()
        tipn = [k for k, i in enumerate(res["_ids"]) if abs(res["_xyz"][k][0] - L) < 1e-6]
        d = -np.mean([res["_U"][k][2] for k in tipn])
        mid = [k for k, i in enumerate(res["_ids"]) if abs(res["_xyz"][k][0] - L / 2) < hmax and res["_xyz"][k][2] > h / 2 - 1e-6]
        s_mid = np.mean([res["_vm"][k] for k in mid])
        rows.append(dict(hmax_mm=hmax, elems=res["n_elems"], tip_mm=d, sigma_mid_mpa=s_mid,
                         err_tip_pct=100 * (d - d_tim) / d_tim, err_sigma_pct=100 * (s_mid - sig_mid) / sig_mid,
                         reaction_N=res["reaction"]))
        print("V1", rows[-1])
    return dict(case="cantilever 200x20x10 6061, 100 N tip", tip_euler_mm=d_eb, tip_timoshenko_mm=d_tim,
                sigma_mid_mpa=sig_mid, mesh_study=rows)


def v2():
    ro, ri, L, P, m_tip = 0.015, 0.0135, 1.0, 50.0, 0.3
    E, G, rho = 70e9, 5e9, 1550.0
    s = Section.pipe(ro, ri, E, G, rho)
    f = Frame()
    a = f.node((0, 0, 0))
    b = f.node((L, 0, 0))
    f.beam(a, b, s, n=40)
    f.add_mass(b, m_tip)
    F = np.zeros(6 * len(f.nodes))
    F[6 * b + 2] = -P
    u, _ = f.solve_static(F, list(range(6)))
    d = -u[6 * b + 2]
    st = f.stresses(u)
    d_an = P * L**3 / (3 * E * s.Iy)
    sig_an = P * L * ro / s.Iy
    freqs, _ = f.modes(4, fixed_dofs=list(range(6)))
    # first bending frequency: exact cantilever with tip mass (characteristic equation)
    mu = rho * s.A * L
    from scipy.optimize import brentq
    ratio = m_tip / mu
    fn = lambda bl: 1 + math.cos(bl) * math.cosh(bl) + ratio * bl * (math.cos(bl) * math.sinh(bl) - math.sin(bl) * math.cosh(bl))
    bl = brentq(fn, 0.5, 1.875)
    f_an = bl**2 / (2 * math.pi) * math.sqrt(E * s.Iy / (rho * s.A * L**4))
    out = dict(case="cantilever CF tube 30x27, 1 m, 50 N tip, 0.3 kg tip mass", tip_mm=d * 1000, tip_analytic_mm=d_an * 1000,
               sigma_mpa=st[0]["sigma"] / 1e6, sigma_analytic_mpa=sig_an / 1e6, f1_hz=float(freqs[0]), f1_analytic_hz=f_an)
    print("V2", out)
    return out


def v3():
    """30x27 tube, 300 mm, 100 N tip: CalculiX solid vs frame (shear-flexible solid is slightly softer)."""
    ro, ri, L, P = 15.0, 13.5, 300.0, 100.0
    mat = ccx.MATERIALS["6061-T6"]
    m = ccx.mesh_solid(tube_x(ro, ri, 0, L), WORK / "v3", 1.5, 0.5)
    fixed = m.ids[m.nodes[:, 0] < 1e-6]
    faces = ccx.boundary_faces(m)
    cent, _, _ = ccx.face_props(m, faces)
    tip = faces[cent[:, 0] > L - 1e-6]
    res = ccx.solve(m, mat, fixed, ccx.traction_loads(m, tip, np.array([0, 0, -P])), "v3")
    tipn = [k for k, i in enumerate(res["_ids"]) if abs(res["_xyz"][k][0] - L) < 1e-6]
    d_solid = -np.mean([res["_U"][k][2] for k in tipn])
    s = Section.pipe(ro / 1000, ri / 1000, mat.E * 1e6, mat.E * 1e6 / (2 * (1 + mat.nu)), 2700)
    f = Frame()
    a, b = f.node((0, 0, 0)), f.node((L / 1000, 0, 0))
    f.beam(a, b, s, n=20)
    F = np.zeros(6 * len(f.nodes))
    F[6 * b + 2] = -P
    u, _ = f.solve_static(F, list(range(6)))
    out = dict(case="6061 tube 30x27, 300 mm, 100 N tip", tip_ccx_mm=d_solid, tip_frame_mm=-u[6 * b + 2] * 1000,
               diff_pct=100 * (d_solid - (-u[6 * b + 2] * 1000)) / (-u[6 * b + 2] * 1000), elems=res["n_elems"])
    print("V3", out)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = dict(V1=v1(), V2=v2(), V3=v3())
    (OUT / "validation.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
