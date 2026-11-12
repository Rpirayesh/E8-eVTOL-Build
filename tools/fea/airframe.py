"""Global airframe beam model of the E8-S: load cases, inertia relief, modes, sizing.

    python tools/fea/airframe.py                 # analyse the current design
    python tools/fea/airframe.py --size-spar     # pick the lightest main spar that passes

Members: wing main + rear spars (CF tubes), a skin torsion-box line (printed LW-PLA
skin, Bredt), booms (CF tubes), H-tail spar, fuselage beam and stiff fittings.
All loads are ultimate (limit x 1.5).  Results -> analysis/fea/airframe/.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fea.frame import Frame, Section  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SEL = json.loads((ROOT / "design" / "selected_design.json").read_text())
OUT = ROOT / "analysis" / "fea" / "airframe"
G0 = 9.80665

# ---------------------------------------------------------------- materials (SI)
CF = dict(E=70e9, G=5e9, rho=1550.0, allow=250e6)   # roll-wrapped 3K/UD tube, ultimate design allowable
LWPLA = dict(E=1.2e9, G=0.43e9, rho=620.0, tau_allow=3.0e6)  # foamed LW-PLA skin
STIFF = Section(A=1e-3, Iy=1e-6, Iz=1e-6, J=2e-6, E=70e9, G=27e9, rho=0.0, c=0.02, name="fitting (rigid)")
ULT = 1.5

# geometry (m)
g = SEL["geometry"]
d = SEL["design"]
c = d["chord_m"]
HALF = d["span_m"] / 2
YB = g["rotor_y"]
X_MAIN, Z_MAIN = 0.084, 0.049
X_REAR, Z_REAR = 0.195, 0.045
X_BOX = 0.14
Z_FUS = -0.105
ROTOR_X = [round(x, 4) for x in g["rotor_x"]]
FUS_X = (-0.42, 0.83)
TAIL_X = round(g["tail_le"] + 0.04, 4)
SADDLE = (0.07, 0.22)
LEG_X = (-0.15, 0.42)


def tube(od_mm, id_mm, mat=CF, name=""):
    return Section.pipe(od_mm / 2000, id_mm / 2000, mat["E"], mat["G"], mat["rho"], name)


def skin_box_section() -> Section:
    """Printed skin as a closed torsion box (Bredt), negligible bending stiffness."""
    A_enc = 0.1028 * c**2 * 0.92          # enclosed area inside the skin mid-line
    perim = 2.04 * c
    t = 0.6e-3
    J = 4 * A_enc**2 / (perim / t)
    return Section(A=perim * t, Iy=1e-12, Iz=1e-12, J=J, E=LWPLA["E"], G=LWPLA["G"], rho=0.0, c=0.0, name="skin box")


def build(main=(20.0, 18.0), rear=(10.0, 8.0), boom=(25.0, 22.0)):
    f = Frame()
    S_main, S_rear, S_boom = tube(*main, name="main spar"), tube(*rear, name="rear spar"), tube(*boom, name="boom")
    S_stab = tube(6.0, 0.0, name="stab spar")
    S_box = skin_box_section()
    # 1 mm LW-PLA superellipse shell (0.24 x 0.26 m): thin elliptical ring, I ~ pi t b^2 (3a + b) / 4
    S_fus = Section(A=1.6e-3, Iy=6.5e-6, Iz=6.0e-6, J=1.2e-5, E=1.2e9, G=0.43e9, rho=0.0, c=0.13, name="fuselage shell")
    tags = {}
    # --- wing stations: tips, segment joints, boom ribs, root cradles
    ys = sorted(set(np.round(np.r_[np.linspace(-HALF, HALF, 57), [-YB, YB, -0.10, 0.10, 0.0]], 4)))
    main_n = [f.node((X_MAIN, y, Z_MAIN)) for y in ys]
    rear_n = [f.node((X_REAR, y, Z_REAR)) for y in ys]
    box_n = [f.node((X_BOX, y, (Z_MAIN + Z_REAR) / 2)) for y in ys]
    for i in range(len(ys) - 1):
        f.beam(main_n[i], main_n[i + 1], S_main, tag="main spar")
        f.beam(rear_n[i], rear_n[i + 1], S_rear, tag="rear spar")
        f.beam(box_n[i], box_n[i + 1], S_box, tag="skin box")
    # printed ribs at every station tie the spars to the box (chordwise in-plane stiff)
    for i in range(len(ys)):
        f.beam(main_n[i], box_n[i], STIFF, tag="rib", vref=(0, 1, 0))
        f.beam(box_n[i], rear_n[i], STIFF, tag="rib", vref=(0, 1, 0))
    # --- fuselage beam with cradle posts at the two spar bulkheads
    fx = sorted(set(np.round(np.r_[np.linspace(*FUS_X, 26), [X_MAIN, X_REAR]], 4)))
    fus_n = [f.node((x, 0.0, Z_FUS)) for x in fx]
    for i in range(len(fx) - 1):
        f.beam(fus_n[i], fus_n[i + 1], S_fus, tag="fuselage", vref=(0, 1, 0))
    for (xs, zs, line) in ((X_MAIN, Z_MAIN, main_n), (X_REAR, Z_REAR, rear_n)):
        nf = fus_n[fx.index(xs)]
        for yy in (-0.10, 0.10):
            f.beam(nf, line[ys.index(yy)], STIFF, tag="bulkhead")
    # --- booms
    bx = sorted(set(np.round(np.r_[np.linspace(g["boom_front"], g["boom_aft"], 49), ROTOR_X, SADDLE, LEG_X, [TAIL_X]], 4)))
    booms = {}
    for side in (-1, 1):
        bn = [f.node((x, side * YB, 0.0)) for x in bx]
        for i in range(len(bx) - 1):
            f.beam(bn[i], bn[i + 1], S_boom, tag="boom", vref=(0, 0, 1))
        booms[side] = bn
        # saddle: both saddle ends tied to the rib (spar nodes at the boom station)
        iy = ys.index(side * YB)
        for xs in SADDLE:
            nb = bn[bx.index(xs)]
            f.beam(nb, main_n[iy], STIFF, tag="saddle/rib")
            f.beam(nb, rear_n[iy], STIFF, tag="saddle/rib")
    # --- H-tail spar between boom ends
    ts = [booms[-1][bx.index(TAIL_X)]] + [f.node((TAIL_X, y, 0.0)) for y in np.linspace(-YB, YB, 13)[1:-1]] + \
        [booms[1][bx.index(TAIL_X)]]
    for i in range(len(ts) - 1):
        f.beam(ts[i], ts[i + 1], S_stab, tag="stab spar")
    model = dict(f=f, ys=ys, main=main_n, rear=rear_n, box=box_n, fx=fx, fus=fus_n, bx=bx, booms=booms, tail=ts)
    add_masses(model)
    return model


def add_masses(m):
    f = m["f"]
    items = SEL["mass"]["items"]
    # per-rotor unit: motor + prop + ESC + nacelle
    unit = sum(items[k]["kg"] for k in ("lift motors", "lift props", "lift ESCs", "motor nacelles (printed)")) / 8
    for side in (-1, 1):
        for x in ROTOR_X:
            f.add_mass(m["booms"][side][m["bx"].index(x)], unit)
        # boom tube mass along the boom
        bm = items["booms (CF tube)"]["kg"] / 2
        nb = m["booms"][side]
        for n in nb:
            f.add_mass(n, bm / len(nb))
        f.add_mass(nb[m["bx"].index(TAIL_X)], items["H-tail + fins"]["kg"] / 2)
        f.add_mass(nb[m["bx"].index(SADDLE[0])], items["boom-wing fittings"]["kg"] / 4)
        f.add_mass(nb[m["bx"].index(SADDLE[1])], items["boom-wing fittings"]["kg"] / 4)
        for x in LEG_X:
            f.add_mass(nb[m["bx"].index(x)], items["landing gear"]["kg"] / 4)
    # wing printed structure + spars: distributed along the span (on the box line)
    wm = items["wing (printed LW-PLA)"]["kg"] + items["wing spars"]["kg"]
    for n in m["box"]:
        f.add_mass(n, wm / len(m["box"]))
    # aileron servos at the outer panels
    # fuselage-carried items placed at their x along the fuselage beam
    fus_items = ["fuselage shell + frames", "pusher motor", "pusher prop + ESC", "avionics", "harness + PDB",
                 "fasteners + adhesive", "growth (10 % of empty)", "battery", "servos"]
    for k in fus_items:
        x = items[k]["x"]
        i = int(np.argmin([abs(xx - x) for xx in m["fx"]]))
        f.add_mass(m["fus"][i], items[k]["kg"])


# ---------------------------------------------------------------- load cases
def rotor_nodes(m):
    out = []
    for r in SEL["layout"]:
        x = round(r["x"] + g["x_cg_target"], 4)
        side = 1 if r["y"] > 0 else -1
        out.append((r["name"], m["booms"][side][m["bx"].index(x)], r["spin"]))
    return out


T_MAX = 40.2         # N, MN5008 KV170 + P18x6.1 at 100 % (bench 4.10 kgf)
Q_PER_T = 0.87 / 40.2  # motor torque / thrust at full power (bench)


def lc_rotors(m, thrusts: dict) -> np.ndarray:
    f = m["f"]
    F = np.zeros(6 * len(f.nodes))
    for name, n, spin in rotor_nodes(m):
        T = thrusts.get(name, 0.0) * ULT
        F[6 * n + 2] += T
        F[6 * n + 5] += -spin * Q_PER_T * T  # reaction torque on the airframe
    return F


def lc_lift(m, n_load: float) -> np.ndarray:
    """Wing lift for load factor n (ultimate) with a Schrenk span distribution, plus pusher thrust."""
    f = m["f"]
    F = np.zeros(6 * len(f.nodes))
    W = SEL["mass"]["total_kg"] * G0
    L = n_load * ULT * W
    ys = np.array(m["ys"])
    ell = np.sqrt(np.clip(1 - (ys / HALF) ** 2, 0, 1)) * 4 / math.pi
    sch = 0.5 * (ell + 1.0)
    w = np.gradient(ys)
    share = sch * w / np.sum(sch * w)
    for k, n in enumerate(m["main"]):
        F[6 * n + 2] += L * share[k] * 0.75
    for k, n in enumerate(m["rear"]):
        F[6 * n + 2] += L * share[k] * 0.25
    # pusher thrust ~ cruise drag at the fuselage tail
    D = SEL["mission"]["cruise"]["drag_n"] * ULT
    F[6 * m["fus"][-1] + 0] -= D
    return F


def lc_landing(m, g_load: float, legs: str = "all") -> np.ndarray:
    f = m["f"]
    F = np.zeros(6 * len(f.nodes))
    W = SEL["mass"]["total_kg"] * G0
    sides = (-1, 1) if legs == "all" else (1,)
    nlegs = 2 * len(sides)
    for s in sides:
        for x in LEG_X:
            F[6 * m["booms"][s][m["bx"].index(x)] + 2] += g_load * ULT * W / nlegs
    return F


def load_cases(m):
    names = [r["name"] for r in SEL["layout"]]
    ro = SEL["rotor_out"]
    worst = max(ro, key=lambda r: r.get("max_thrust_frac", 0))
    cases = {
        "LC1 hover 1 g (limit, for deflection)": lc_rotors(m, {n: SEL["mission"]["hover"]["thrust_per_rotor_n"] for n in names}) / ULT,
        "LC2 all rotors 100 %": lc_rotors(m, {n: T_MAX for n in names}),
        "LC3 pitch: front 100 %, rear 0": lc_rotors(m, {n: T_MAX for n in names if n[2] in "12"}),
        "LC4 roll: starboard 100 %, port 0": lc_rotors(m, {n: T_MAX for n in names if n[1] == "S"}),
        "LC5 yaw: CCW rotors 100 %, CW 0": lc_rotors(m, {r["name"]: T_MAX for r in SEL["layout"] if r["spin"] > 0}),
        "LC6 gust/manoeuvre +4 g": lc_lift(m, 4.0),
        "LC7 negative gust -2 g": lc_lift(m, -2.0),
        "LC8 landing 4 g, all legs": lc_landing(m, 4.0, "all"),
        "LC9 landing 4 g, one boom": lc_landing(m, 4.0, "one"),
    }
    # rotor-out: hover thrust re-allocated with the worst rotor failed, at 1.3 g (climb-out)
    T_ro = {n: SEL["mission"]["hover"]["thrust_per_rotor_n"] * 1.3 for n in names}
    T_ro[worst["failed"]] = 0.0
    cases[f"LC10 rotor {worst['failed']} failed, 1.3 g"] = lc_rotors(m, T_ro)
    return cases


# ---------------------------------------------------------------- analysis
def analyse(m, verbose=True):
    f = m["f"]
    support = m["fus"][m["fx"].index(X_MAIN)]
    results = {}
    S_box = skin_box_section()
    A_enc = 0.1028 * c**2 * 0.92
    for name, F in load_cases(m).items():
        u, info = f.solve_inertia_relief(F, support)
        st = f.stresses(u)
        groups = {}
        for s in st:
            grp = s["tag"]
            if grp in ("rib", "bulkhead", "saddle/rib", "tail block"):
                continue
            gmax = groups.setdefault(grp, dict(sigma=0.0, tau=0.0, M=0.0, T=0.0))
            gmax["sigma"] = max(gmax["sigma"], s["sigma"])
            gmax["M"] = max(gmax["M"], s["M"])
            gmax["T"] = max(gmax["T"], s["T"])
        if "skin box" in groups:
            groups["skin box"]["tau"] = groups["skin box"]["T"] / (2 * A_enc * 0.6e-3)
        disp = u.reshape(-1, 6)[:, :3]
        rel = disp - disp[support]
        # boom root loads (at the saddle ends) for the local fitting FEA
        fl = f.element_forces(u)
        boom_root = 0.0
        for (a, b, s, v, tag), e in zip(f.elems, fl):
            # boom roots just outside the saddle: element ending at the front end, starting at the rear end
            if tag == "boom" and (np.isclose(f.nodes[b][0], SADDLE[0]) or np.isclose(f.nodes[a][0], SADDLE[1])):
                boom_root = max(boom_root, abs(e[4]), abs(e[10]), abs(e[5]), abs(e[11]))
        results[name] = dict(groups=groups, max_disp_mm=float(np.max(np.linalg.norm(rel, axis=1)) * 1000),
                             wing_tip_mm=float((rel[m["main"][-1], 2]) * 1000),
                             boom_root_moment_nm=float(boom_root), accel_g=(info["accel"] / G0).tolist(),
                             alpha_rad_s2=info["alpha"].tolist(), residual_reaction_n=float(np.linalg.norm(info["reaction"][:3])))
        if verbose:
            gs = ", ".join(f"{k} {v['sigma'] / 1e6:.0f} MPa" for k, v in groups.items() if k not in ("skin box", "fuselage"))
            print(f"{name:38s} {gs}; skin tau {groups['skin box']['tau'] / 1e6:.2f} MPa; tip {results[name]['wing_tip_mm']:.1f} mm")
    return results


def margins(results):
    allow = {"main spar": CF["allow"], "rear spar": CF["allow"], "boom": CF["allow"], "stab spar": CF["allow"]}
    out = {}
    for grp, a in allow.items():
        worst = max(results.items(), key=lambda kv: kv[1]["groups"].get(grp, {}).get("sigma", 0))
        s = worst[1]["groups"][grp]["sigma"]
        out[grp] = dict(max_sigma_mpa=s / 1e6, case=worst[0], allowable_mpa=a / 1e6, MS=a / s - 1)
    worst = max(results.items(), key=lambda kv: kv[1]["groups"]["skin box"]["tau"])
    t = worst[1]["groups"]["skin box"]["tau"]
    out["wing skin (torsion)"] = dict(max_tau_mpa=t / 1e6, case=worst[0], allowable_mpa=LWPLA["tau_allow"] / 1e6,
                                      MS=LWPLA["tau_allow"] / t - 1)
    return out


def node_groups(m) -> dict:
    grp = {}
    for n in m["main"] + m["rear"] + m["box"]:
        grp[n] = "wing"
    for side in (-1, 1):
        for n in m["booms"][side]:
            grp[n] = "booms"
    for n in m["fus"]:
        grp[n] = "fuselage"
    for n in m["tail"][1:-1]:
        grp[n] = "tail"
    return grp


def modal(m, n=24):
    f = m["f"]
    freqs, V = f.modes(n)
    _, M = f.assemble()
    Md = M.diagonal()
    grp = node_groups(m)
    modes = []
    for k, fr in enumerate(freqs):
        if fr < 1.0:
            continue
        ke = {}
        for node in range(len(f.nodes)):
            e = float(np.sum(Md[6 * node:6 * node + 3] * V[6 * node:6 * node + 3, k] ** 2))
            ke[grp.get(node, "other")] = ke.get(grp.get(node, "other"), 0.0) + e
        tot = sum(ke.values())
        modes.append(dict(f_hz=float(fr), energy={kk: round(v / tot, 3) for kk, v in sorted(ke.items(), key=lambda kv: -kv[1])}))
    hover_rpm = SEL["mission"]["hover"]["rpm"]
    return dict(modes=modes, rotor_1P_hover_hz=hover_rpm / 60, blade_pass_2P_hover_hz=2 * hover_rpm / 60,
                rotor_1P_range_hz=[2800 / 60, 5963 / 60], note="free-free (in flight); energy = kinetic-energy fraction by component")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size-spar", action="store_true")
    ap.add_argument("--boom-study", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.boom_study:
        rows = []
        for bo in [(25, 22), (30, 28), (30, 27), (35, 33), (40, 38)]:
            mdl = build(main=(25, 22), rear=(12, 10), boom=bo)
            md = modal(mdl, 8)
            ms = margins(analyse(mdl, verbose=False))
            rows.append(dict(boom=bo, kg_per_m=np.pi / 4 * (bo[0] ** 2 - bo[1] ** 2) * 1e-6 * CF["rho"],
                             modes_hz=[x["f_hz"] for x in md["modes"][:5]], MS={k: v["MS"] for k, v in ms.items()}))
            print(rows[-1])
        (OUT / "boom_study.json").write_text(json.dumps(rows, indent=1))
        return
    if args.size_spar:
        cands = [(20, 18), (22, 20), (25, 22), (28, 25), (30, 27), (32, 29), (35, 32)]
        rears = [(10, 8), (12, 10), (14, 12)]
        rows = []
        for mo in cands:
            for ro_ in rears:
                mdl = build(main=mo, rear=ro_, boom=(30.0, 27.0))
                r = analyse(mdl, verbose=False)
                ms = margins(r)
                mass = sum(np.pi / 4 * (a**2 - b**2) * 1e-6 * CF["rho"] for a, b in (mo, ro_)) * 2 * HALF
                rows.append(dict(main=mo, rear=ro_, spar_mass_kg=mass, **{k: v["MS"] for k, v in ms.items()}))
                print(mo, ro_, f"{mass:.3f} kg", {k: round(v["MS"], 2) for k, v in ms.items()})
        # Require a +25 % margin at ultimate load (hand-built composite joints, tube variability);
        # among candidates within 60 g of the lightest, prefer one sharing the boom tube stock.
        MS_MIN, COMMON_STOCK, TOL_KG = 0.25, (30, 27), 0.060
        ok = [r for r in rows if min(r["main spar"], r["rear spar"], r["wing skin (torsion)"]) >= MS_MIN]
        lightest = min(ok, key=lambda r: r["spar_mass_kg"])
        common = [r for r in ok if tuple(r["main"]) == COMMON_STOCK and r["spar_mass_kg"] <= lightest["spar_mass_kg"] + TOL_KG]
        best = min(common, key=lambda r: r["spar_mass_kg"]) if common else lightest
        rule = f"min MS >= {MS_MIN}; prefer boom stock {COMMON_STOCK} within {TOL_KG * 1000:.0f} g of the lightest"
        (OUT / "spar_sizing.json").write_text(json.dumps(dict(candidates=rows, lightest=lightest, selected=best, rule=rule), indent=1))
        print("lightest:", lightest)
        print("selected:", best)
        return
    from cad.parts import C as CADC
    mdl = build(main=(CADC.main_spar_od, CADC.main_spar_id), rear=(CADC.rear_spar_od, CADC.rear_spar_id),
                boom=(CADC.boom_od, CADC.boom_id))
    r = analyse(mdl)
    ms = margins(r)
    md = modal(mdl)
    print(json.dumps(ms, indent=1))
    print(json.dumps(md, indent=1))
    (OUT / "results.json").write_text(json.dumps(dict(cases=r, margins=ms, modes=md,
                                                      sections=dict(main=(CADC.main_spar_od, CADC.main_spar_id),
                                                                    rear=(CADC.rear_spar_od, CADC.rear_spar_id),
                                                                    boom=(CADC.boom_od, CADC.boom_id)),
                                                      materials=dict(CF=CF, LWPLA=LWPLA), ultimate_factor=ULT), indent=1))


if __name__ == "__main__":
    main()
