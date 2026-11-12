"""Can the propellers be 3-D printed?  BEMT design + blade stress for printable materials.

    python tools/propeller/prop_study.py

1. Check BEMT against APC's published 17x10E data (one-parameter chord calibration).
2. Design a minimum-induced-loss 17" pusher blade for the 25 m/s cruise point.
3. Build the blade CAD (Clark Y sections, thickened root, 12 mm hub) -> STEP/STL.
4. Spanwise stresses (centrifugal + flap/lag bending) at the worst operating point,
   for printable materials, and a CalculiX solid check of the blade root.
Results -> analysis/propeller/, CAD -> cad/parts/PROP-PRINT/.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from propeller import bemt  # noqa: E402
from e8lib.props import APCProp  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "propeller"
SEL = json.loads((ROOT / "design" / "selected_design.json").read_text())

# Printed-material data (XY, dry). Fatigue allowable = endurance estimate at 1e7 cycles.
MATERIALS = {
    "PA6-CF (FDM)": dict(rho=1150, E=4.5e9, uts=70e6, fatigue=21e6),
    "PETG (FDM)": dict(rho=1270, E=2.0e9, uts=48e6, fatigue=12e6),
    "PLA (FDM)": dict(rho=1240, E=3.3e9, uts=55e6, fatigue=11e6),
    "Tough SLA resin": dict(rho=1170, E=2.2e9, uts=46e6, fatigue=12e6),
    "Carbon/nylon moulded (reference)": dict(rho=1400, E=12e9, uts=180e6, fatigue=60e6),
}
SF = 1.5
RAKE = 2.5  # deg forward rake (re-optimised in main)


def section_props(chord, tc):
    """Clark Y-like section: area, second moments about the centroidal chord axes (m^4), extreme fibres."""
    import aerosandbox as asb
    af = asb.Airfoil("clarky")
    pts = af.coordinates.copy()
    pts[:, 1] *= tc / 0.117
    pts *= chord
    x, y = pts[:, 0], pts[:, 1]
    xs, ys = np.roll(x, -1), np.roll(y, -1)
    cr = x * ys - xs * y
    A = 0.5 * np.sum(cr)
    cx = np.sum((x + xs) * cr) / (6 * A)
    cy = np.sum((y + ys) * cr) / (6 * A)
    Ixx = np.sum((y**2 + y * ys + ys**2) * cr) / 12 - A * cy**2   # flap (about chord axis)
    Iyy = np.sum((x**2 + x * xs + xs**2) * cr) / 12 - A * cx**2   # lag (about normal axis)
    return abs(A), abs(Ixx), abs(Iyy), max(abs(y - cy)), max(abs(x - cx))


def blade_stresses(bl: bemt.Blade, tc: np.ndarray, rpm: float, op: dict, mat: dict, rake_deg: float = 0.0):
    """Section stresses of a clamped, centrifugally tensioned blade.

    Flap moment M(r) = int_r^R q (r' - r) dr' - int_r^R dm om^2 r' (z(r') - z(r)) dr',
    where z = built-in rake + elastic flap deflection; the deflection follows from
    M / EI and is iterated to convergence (centrifugal stiffening and rake relief).
    The in-plane (lag) moment is taken without relief (conservative)."""
    om = rpm * 2 * math.pi / 60
    r = bl.r
    props = [section_props(c, t) for c, t in zip(bl.chord, tc)]
    A = np.array([p[0] for p in props])
    dm = mat["rho"] * A                                      # kg/m
    cf = dm * om**2 * r                                      # centrifugal force per unit length (N/m)
    N = np.array([np.trapezoid(cf[k:], r[k:]) for k in range(len(r))])
    fT, fQ = op["dT_per_blade"], op["dQ_per_blade"] / r      # N/m normal (thrust) and in-plane force
    EI = mat["E"] * np.array([p[1] for p in props])
    z_rake = (r - r[0]) * math.tan(math.radians(rake_deg))
    n = len(r)

    def integ(f):  # cumulative trapezoid from the root
        return np.concatenate([[0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(r))])

    def defl(M):   # clamped root: w'' = M / EI
        return integ(integ(M / EI))

    def cmom(z):   # centrifugal moment of heights z about each section
        return np.array([np.trapezoid(cf[k:] * (z[k:] - z[k]), r[k:]) for k in range(n)])

    M_aero = np.array([np.trapezoid(fT[k:] * (r[k:] - r[k]), r[k:]) for k in range(n)])
    H = np.column_stack([defl(e) for e in np.eye(n)])
    Cm = np.column_stack([cmom(e) for e in np.eye(n)])
    # w = H (M_aero - C (z_rake + w))  ->  (I + H C) w = H (M_aero - C z_rake)
    w = np.linalg.solve(np.eye(n) + H @ Cm, H @ (M_aero - Cm @ z_rake))
    Mf = M_aero - Cm @ (z_rake + w)
    Ml = np.array([np.trapezoid(fQ[k:] * (r[k:] - r[k]), r[k:]) for k in range(len(r))])
    sig = []
    for k, (Ak, Ixx, Iyy, cy, cx) in enumerate(props):
        # resolve the rotor-plane moments into section axes (pitch angle beta)
        b = bl.beta[k]
        m_flap = Mf[k] * math.cos(b) + Ml[k] * math.sin(b)
        m_lag = -Mf[k] * math.sin(b) + Ml[k] * math.cos(b)
        sig.append(N[k] / Ak + abs(m_flap) * cy / Ixx + abs(m_lag) * cx / Iyy)
    return np.array(sig), N, Mf, Ml, A, w


def thickness_distribution(bl: bemt.Blade) -> np.ndarray:
    """t/c 12 % outboard rising to 28 % at the root fairing into the hub."""
    xi = (bl.r - bl.r[0]) / (bl.R - bl.r[0])
    return 0.12 + 0.16 * np.clip(1 - xi / 0.35, 0, 1) ** 1.5


def blade_cad(bl: bemt.Blade, tc: np.ndarray, hub_r=0.016, bore=0.003):
    import aerosandbox as asb
    from build123d import Axis, Solid
    from cad.geom import cyl_z, loft_sections
    af = asb.Airfoil("clarky").repanel(n_points_per_side=40)
    secs, st = [], []
    for r, c, b, t in zip(bl.r, bl.chord, bl.beta, tc):
        p = af.coordinates.copy()[:-1]
        p[:, 1] *= t / 0.117
        p = (p - np.array([0.3, 0])) * c * 1000            # mm, pitch axis at 30 % chord
        ca, sa = math.cos(b), math.sin(b)
        secs.append(np.column_stack([p[:, 0] * ca - p[:, 1] * sa, p[:, 0] * sa + p[:, 1] * ca]))
        st.append(r * 1000)
    blade = loft_sections(secs, st, "y")
    prop = blade + blade.rotate(Axis.Z, 180)
    hub = cyl_z(hub_r * 1000, -9, 9) - cyl_z(bore * 1000, -10, 10)
    return prop + hub - cyl_z(bore * 1000, -10, 10)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}

    # 1. method check vs APC 17x10E (chord scale calibrated on the static point at 7000 rpm)
    apc = APCProp.load("17x10E")
    base = bemt.apc_like(17, 10)
    T_apc0, _ = apc.thrust_power(7000, 0.0)
    T_b0 = bemt.solve(base, 0.0, 7000)["T"]
    lo, hi = 0.5, 1.2
    for _ in range(25):
        s = 0.5 * (lo + hi)
        bl = bemt.Blade(base.R, base.r, base.chord * s, base.beta, base.B, base.airfoil, base.hub_r)
        if bemt.solve(bl, 0.0, 7000)["T"] > T_apc0:
            hi = s
        else:
            lo = s
    scale = 0.5 * (lo + hi)
    cal = bemt.Blade(base.R, base.r, base.chord * scale, base.beta, base.B, base.airfoil, base.hub_r)
    rows = []
    for rpm in (5000, 7000):
        for V in np.arange(0, 32.1, 4.0):
            b = bemt.solve(cal, float(V), rpm)
            T, P = apc.thrust_power(rpm, float(V))
            rows.append(dict(rpm=rpm, V=float(V), J=b["J"], T_bemt=b["T"], T_apc=T, P_bemt=b["P"], P_apc=P,
                             eta_bemt=b["eta"], eta_apc=T * V / P if P > 0 else 0.0))
    res["method_check"] = dict(chord_scale=scale, rows=rows,
                               note="APC PER3 data are APC's own predictions; geometry is approximate, so agreement is a method check, not a geometry match")
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=130)
    for rpm, ls in ((5000, "--"), (7000, "-")):
        sub = [r for r in rows if r["rpm"] == rpm]
        ax[0].plot([r["J"] for r in sub], [r["T_bemt"] for r in sub], ls, color="C0", label=f"BEMT {rpm} rpm")
        ax[0].plot([r["J"] for r in sub], [r["T_apc"] for r in sub], ls, color="C1", label=f"APC data {rpm} rpm")
        ax[1].plot([r["J"] for r in sub], [r["eta_bemt"] for r in sub], ls, color="C0")
        ax[1].plot([r["J"] for r in sub], [r["eta_apc"] for r in sub], ls, color="C1")
    ax[0].set_xlabel("Advance ratio J"); ax[0].set_ylabel("Thrust (N)"); ax[0].legend(frameon=False, fontsize=8); ax[0].grid(alpha=.3)
    ax[1].set_xlabel("Advance ratio J"); ax[1].set_ylabel("Efficiency"); ax[1].grid(alpha=.3); ax[1].set_ylim(0, 1)
    fig.suptitle("BEMT method check: APC 17x10E (one-point chord calibration)")
    fig.tight_layout(); fig.savefig(OUT / "bemt_vs_apc.png"); plt.close(fig)

    # 2. printable pusher: MIL design at the cruise point
    cr = SEL["mission"]["cruise"]
    T_cr, V_cr = cr["drag_n"], cr["V"]
    R, hub = 17 * 0.0254 / 2, 0.016
    rpm_d = 6200.0
    T_target = T_cr
    for _ in range(20):
        bl = bemt.adkins_liebeck(R, hub, 2, V_cr, rpm_d, T_target, cl_d=0.45)  # wide chord for printability
        T = bemt.solve(bl, V_cr, rpm_d)["T"]
        T_target *= T_cr / T
        if abs(T - T_cr) < 0.05:
            break
    mil = bemt.solve(bl, V_cr, rpm_d)
    res["mil_design"] = dict(rpm=rpm_d, thrust=mil["T"], power=mil["P"], eta=mil["eta"],
                             chord_mm=(bl.chord * 1000).tolist(), beta_deg=np.degrees(bl.beta).tolist(),
                             note="aerodynamic optimum (Adkins-Liebeck); too slender near the tip to print")
    # The printable blade is a copy of the APC 17x10 planform (calibrated above): cruise rpm for the cruise thrust
    bl = cal
    lo, hi = 3000.0, 9000.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if bemt.solve(bl, V_cr, mid)["T"] < T_cr else (lo, mid)
    rpm_d = 0.5 * (lo + hi)
    op_cr = bemt.solve(bl, V_cr, rpm_d)
    tc = thickness_distribution(bl)
    # worst structural point: full power static (transition), at the motor's peak (7900 rpm on 12S)
    rpm_max = 7900.0
    op_st = bemt.solve(bl, 0.0, rpm_max)
    res["printed_pusher"] = dict(design=dict(V=V_cr, rpm=rpm_d, thrust=op_cr["T"], power=op_cr["P"], eta=op_cr["eta"]),
                                 static_at_max_rpm=dict(rpm=rpm_max, thrust=op_st["T"], power=op_st["P"]),
                                 apc_17x10_cruise_eta=cr["eta_prop"],
                                 r_mm=(bl.r * 1000).tolist(), chord_mm=(bl.chord * 1000).tolist(),
                                 beta_deg=np.degrees(bl.beta).tolist(), t_over_c=tc.tolist())
    # 3. forward rake chosen to minimise the worse of the static (full power) and cruise stress
    global RAKE
    pa = MATERIALS["PA6-CF (FDM)"]
    scan = []
    for rk in np.arange(0.0, 8.01, 0.25):
        s_st = blade_stresses(bl, tc, rpm_max, op_st, pa, rk)[0].max()
        s_cr = blade_stresses(bl, tc, rpm_d, op_cr, pa, rk)[0].max()
        scan.append((max(s_st, s_cr), rk))
    RAKE = min(scan)[1]
    res["printed_pusher"]["rake_deg"] = RAKE
    verdict = {}
    fig, ax = plt.subplots(figsize=(7.5, 4.4), dpi=130)
    for name, mat in MATERIALS.items():
        sig, N, Mf, Ml, A, w = blade_stresses(bl, tc, rpm_max, op_st, mat, RAKE)
        smax = float(sig.max())
        ok = smax * SF <= mat["fatigue"]
        s_cr = blade_stresses(bl, tc, rpm_d, op_cr, mat, RAKE)[0].max()
        verdict[name] = dict(max_stress_mpa=smax / 1e6, cruise_stress_mpa=s_cr / 1e6, MS_fatigue_cruise=mat["fatigue"] / (SF * s_cr) - 1, at_r_mm=float(bl.r[int(np.argmax(sig))] * 1000),
                             fatigue_allowable_mpa=mat["fatigue"] / 1e6, uts_mpa=mat["uts"] / 1e6,
                             MS_fatigue=mat["fatigue"] / (SF * smax) - 1, MS_static=mat["uts"] / (SF * smax) - 1, acceptable=bool(ok),
                             centrifugal_root_n=float(N[0]))
        ax.plot(bl.r * 1000, sig / 1e6, label=name)
    ax.axhline(MATERIALS["PA6-CF (FDM)"]["fatigue"] / 1e6 / SF, color="k", ls="--", lw=0.8, label="PA6-CF fatigue allowable / 1.5")
    ax.set_xlabel("Radius (mm)"); ax.set_ylabel("Max section stress (MPa)"); ax.grid(alpha=.3); ax.legend(fontsize=7, frameon=False)
    ax.set_title(f"Printed 17-in pusher blade at {rpm_max:.0f} rpm static, T = {op_st['T']:.0f} N")
    fig.tight_layout(); fig.savefig(OUT / "printed_blade_stress.png"); plt.close(fig)
    res["printed_pusher"]["materials"] = verdict

    # reduced-rpm envelope: highest rpm at which PA6-CF passes the fatigue criterion
    mat = MATERIALS["PA6-CF (FDM)"]
    ok_rpm = None
    for rpm in np.arange(3000, 7901, 100):
        o = bemt.solve(bl, 0.0, float(rpm))
        s, *_ = blade_stresses(bl, tc, float(rpm), o, mat, RAKE)
        if s.max() * SF <= mat["fatigue"]:
            ok_rpm = (float(rpm), o["T"])
    res["printed_pusher"]["pa6cf_max_rpm_static"] = dict(rpm=ok_rpm[0], thrust_n=ok_rpm[1]) if ok_rpm else None

    # lift rotor: same check for an 18 x 6.1-like printed rotor at its 100 % point (5963 rpm, 40 N)
    lift = bemt.apc_like(18, 6.1)
    lift = bemt.Blade(lift.R, lift.r, lift.chord * scale, lift.beta, 2, "clarky", lift.hub_r)
    op_l = bemt.solve(lift, 0.0, 5963)
    tcl = thickness_distribution(lift)
    lv = {}
    for name, m in MATERIALS.items():
        s, *_ = blade_stresses(lift, tcl, 5963, op_l, m, RAKE)
        lv[name] = dict(max_stress_mpa=float(s.max()) / 1e6, MS_fatigue=m["fatigue"] / (SF * s.max()) - 1)
    res["printed_lift_rotor"] = dict(rpm=5963, thrust_n=op_l["T"], materials=lv)

    # 4. CAD of the printable pusher (for prototyping / ground test only)
    from build123d import export_step, export_stl
    d = ROOT / "cad" / "parts" / "PROP-PRINT"
    d.mkdir(parents=True, exist_ok=True)
    solid = blade_cad(bl, tc)
    export_step(solid, str(d / "PROP-PRINT.step"))
    export_stl(solid, str(d / "PROP-PRINT.stl"), tolerance=0.02, angular_tolerance=0.1)
    res["printed_pusher"]["cad"] = "cad/parts/PROP-PRINT/PROP-PRINT.step"
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=float))
    for k, v in verdict.items():
        print(f"{k:34s} max {v['max_stress_mpa']:6.1f} MPa  MS_fatigue {v['MS_fatigue']:+.2f}  MS_static {v['MS_static']:+.2f}")
    print("design:", res["printed_pusher"]["design"], "static:", res["printed_pusher"]["static_at_max_rpm"])
    print("PA6-CF allowed rpm:", res["printed_pusher"]["pa6cf_max_rpm_static"])
    print("lift rotor:", {k: round(v["MS_fatigue"], 2) for k, v in lv.items()})


if __name__ == "__main__":
    main()
