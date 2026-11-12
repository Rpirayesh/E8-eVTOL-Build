"""Parametric subscale E8 lift+cruise demonstrator: geometry, mass, aero, performance.

Coordinate system (metres): x aft from the wing leading edge, y to starboard, z up.
The design is a twin-boom lift+cruise layout: eight fixed lift rotors on two
longitudinal booms (four per side), a high-mounted wing, an H-tail joining the
boom ends and a pusher propeller at the fuselage tail.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from .props import APCProp, LiftRotor, Motor, G

ROOT = Path(__file__).resolve().parents[2]
RHO = 1.225
NU = 1.46e-5

COMPONENTS = json.loads((ROOT / "design" / "components.json").read_text())


@dataclass
class Design:
    span_m: float = 2.6
    chord_m: float = 0.30
    battery: str = "battery_16000"
    n_battery: int = 2
    cruise_ms: float = 22.0
    boom_y_m: float = 0.60
    fuselage_len_m: float = 1.25
    fuselage_w_m: float = 0.24
    fuselage_h_m: float = 0.26
    static_margin: float = 0.15
    rotor_gap_m: float = 0.06       # clearance between disc and wing / adjacent disc
    cd0_override: float | None = None  # from CFD when available

    # derived (filled by build())
    geom: dict = field(default_factory=dict)
    mass: dict = field(default_factory=dict)


LIFT = LiftRotor.load()
PUSHER = APCProp.load("17x10E")
# AT4130 KV230 calibrated to the 17x10 12S bench point (43.62 V, 55.63 A,
# 7891 rpm, 2.101 Nm): effective Kv 246 rpm/V and 0.209 Ohm including ESC and
# wiring.  Check against the 16x8 point: model 40.6 A / 43.6 V vs bench 38.3 A / 43.8 V.
PUSHER_MOTOR = Motor(kv_rpm_per_v=246.0, r_ohm=0.209, i0_a=1.4, mass_kg=0.408)
SERIES_PACKS = 2  # two 6S packs in series form the 12S bus
# APC static prediction vs bench: thrust -9.5 %, power -19 %.  Use a 15 % power
# penalty in cruise (conservative; static is APC's least accurate regime).
APC_POWER_FACTOR = 1.15


def naca4_thickness(t: float, x: np.ndarray) -> np.ndarray:
    return 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)


def cf_turb(re: float) -> float:
    """Mixed laminar/turbulent flat-plate skin friction (Prandtl-Schlichting, 10 % laminar)."""
    return 0.455 / np.log10(re) ** 2.58 * 0.95


MIN_TAIL_CHORD = 0.11  # buildable printed stabiliser with a 35 % elevator


def _layout(d: Design, x_cg: float) -> dict:
    R = LIFT.diameter_m / 2
    c = d.chord_m
    # Rotor pattern is symmetric about the CG; the inner pair must clear the wing.
    a = max(x_cg + R + d.rotor_gap_m, c - x_cg + R + d.rotor_gap_m)
    pitch = 2 * R + d.rotor_gap_m
    xs = x_cg + np.array([-(a + pitch), -a, a, a + pitch])
    tail_le = xs[3] + R + 0.05
    boom_front = xs[0] - 0.05
    boom_aft = tail_le + MIN_TAIL_CHORD + 0.06
    g = dict(S=d.span_m * c, AR=d.span_m / c, rotor_x=xs.tolist(), rotor_y=d.boom_y_m, rotor_R=R,
             boom_front=boom_front, boom_aft=boom_aft, boom_len=boom_aft - boom_front,
             tail_le=tail_le, tail_span=2 * d.boom_y_m, x_cg_target=x_cg,
             fus_nose=-0.42, wing_z=0.10, boom_z=0.0)
    g["fus_tail"] = g["fus_nose"] + d.fuselage_len_m
    return g


def build(d: Design) -> Design:
    """Lay out rotors and tail so that the CG gives the target static margin.

    The tail chord is sized for the static margin; if that chord is below the
    buildable minimum the minimum is used and the CG target moves aft instead.
    Fixed-point iteration because the tail position depends on the rotor layout.
    """
    c = d.chord_m
    x_cg = 0.30 * c
    for _ in range(30):
        d.geom = _layout(d, x_cg)
        ct = max(size_tail(d), MIN_TAIL_CHORD)
        d.geom["tail_chord"] = ct
        x_new = neutral_point(d, ct) - d.static_margin * c
        if abs(x_new - x_cg) < 1e-5:
            break
        x_cg = 0.5 * (x_cg + x_new)
    d.geom["x_np"] = neutral_point(d, d.geom["tail_chord"])
    d.mass = mass_buildup(d)
    return d


def neutral_point(d: Design, tail_chord: float) -> float:
    """Return neutral point x (m) using the classic tail-volume expression."""
    g = d.geom
    c = d.chord_m
    S = g["S"]
    a_w = 2 * np.pi * g["AR"] / (2 + np.sqrt(4 + g["AR"] ** 2))
    St = g["tail_span"] * tail_chord
    ARt = g["tail_span"] / tail_chord
    a_t = 2 * np.pi * ARt / (2 + np.sqrt(4 + ARt**2))
    lt = g["tail_le"] + 0.25 * tail_chord - 0.25 * c
    deps = 2 * a_w / (np.pi * g["AR"])
    Vh = St * lt / (S * c)
    # Fuselage + booms destabilising contribution (Gilruth-type estimate)
    Kf = 0.006
    dCm_fus = Kf * (d.fuselage_w_m**2 * d.fuselage_len_m + 2 * 0.025**2 * g["boom_len"]) / (S * c) * 57.3 / a_w
    hn = 0.25 + 0.9 * Vh * (a_t / a_w) * (1 - deps) - dCm_fus
    return hn * c


def size_tail(d: Design) -> float:
    target = d.geom["x_cg_target"] + d.static_margin * d.chord_m
    chords = np.linspace(0.06, 0.30, 241)
    xn = np.array([neutral_point(d, ct) for ct in chords])
    return float(np.interp(target, xn, chords))


def mass_calibration() -> dict:
    """Mass coefficients measured from the CAD (design/mass_calibration.json), if built."""
    path = ROOT / "design" / "mass_calibration.json"
    return json.loads(path.read_text()) if path.exists() else {}


def mass_buildup(d: Design) -> dict:
    g = d.geom
    C = COMPONENTS
    bat = C[d.battery]
    S = g["S"]
    St = g["tail_span"] * g["tail_chord"]
    cal = mass_calibration()
    wing_kg_m2 = cal.get("wing_printed_kg_per_m2", 0.95)
    spar_kg_m = cal.get("spars_kg_per_m_span", C["spar_tube"]["mass_kg_per_m"] + C["rear_spar_tube"]["mass_kg_per_m"])
    boom_kg_m = cal.get("booms_kg_per_m", C["boom_tube"]["mass_kg_per_m"])
    tail_kg = cal.get("tail_kg", 0.95 * St + 2 * 0.95 * 0.035 + C["rear_spar_tube"]["mass_kg_per_m"] * g["tail_span"])
    fus_kg = cal.get("fuselage_kg", 0.55 + 0.42 * d.fuselage_len_m)
    items = {
        # name: (kg, x, z)
        "lift motors": (8 * C["lift_motor"]["mass_kg"], np.mean(g["rotor_x"]), 0.05),
        "lift props": (4 * C["lift_prop"]["mass_kg"], np.mean(g["rotor_x"]), 0.09),
        "lift ESCs": (8 * C["lift_esc"]["mass_kg"], np.mean(g["rotor_x"]), 0.0),
        "motor nacelles (printed)": (8 * cal.get("nacelle_kg_each", 0.040), np.mean(g["rotor_x"]), 0.02),
        "booms (CF tube)": (2 * g["boom_len"] * boom_kg_m, 0.5 * (g["boom_front"] + g["boom_aft"]), 0.0),
        "boom-wing fittings": (cal.get("clamps_kg_total", 4 * 0.055), 0.5 * d.chord_m, 0.02),
        "wing (printed LW-PLA)": (wing_kg_m2 * S, 0.42 * d.chord_m, g["wing_z"]),
        "wing spars": (spar_kg_m * d.span_m, 0.35 * d.chord_m, g["wing_z"]),
        "H-tail + fins": (tail_kg, g["tail_le"] + 0.4 * g["tail_chord"], 0.08),
        "fuselage shell + frames": (fus_kg, g["fus_nose"] + 0.45 * d.fuselage_len_m, -0.05),
        "landing gear": (cal.get("gear_kg", 0.28), 0.3 * d.chord_m, -0.20),
        "pusher motor": (C["cruise_motor"]["mass_kg"], g["fus_tail"] - 0.06, -0.02),
        "pusher prop + ESC": (C["cruise_prop"]["mass_kg"] + C["cruise_esc"]["mass_kg"], g["fus_tail"] - 0.05, -0.02),
        "avionics": (sum(C[k]["mass_kg"] for k in ("flight_controller", "gps", "airspeed", "power_sensor", "telemetry", "receiver", "bec")), -0.15, 0.02),
        "servos": (5 * C["servo"]["mass_kg"], 0.6, 0.05),
        "harness + PDB": (C["harness"]["mass_kg"], 0.15, -0.05),
        "fasteners + adhesive": (0.15, 0.2, 0.0),
    }
    empty = sum(v[0] for v in items.values())
    items["growth (10 % of empty)"] = (0.10 * empty, g["x_cg_target"], 0.0)
    # Battery placed to put the CG exactly on target (it slides on its tray).
    mb = d.n_battery * bat["mass_kg"]
    m_other = sum(v[0] for v in items.values())
    mx_other = sum(v[0] * v[1] for v in items.values())
    x_bat = (g["x_cg_target"] * (m_other + mb) - mx_other) / mb
    items["battery"] = (mb, x_bat, -0.08)
    total = sum(v[0] for v in items.values())
    zcg = sum(v[0] * v[2] for v in items.values()) / total
    return {"items": {k: {"kg": round(v[0], 4), "x": round(v[1], 4), "z": round(v[2], 3)} for k, v in items.items()},
            "total_kg": total, "x_battery": x_bat, "z_cg": zcg}


def drag_area(d: Design) -> dict:
    """Zero-lift drag area build-up D/q (m^2) at cruise speed."""
    g = d.geom
    V = d.cruise_ms
    c = d.chord_m
    S = g["S"]
    ff_wing = 1 + 0.6 / 0.3 * 0.15 + 100 * 0.15**4  # Raymer form factor, t/c 0.15, (x/c)m 0.3
    wing = cf_turb(V * c / NU) * ff_wing * 2.04 * (S - d.fuselage_w_m * c)
    lt = d.fuselage_len_m
    fineness = lt / np.sqrt(d.fuselage_w_m * d.fuselage_h_m)
    ff_fus = 1 + 60 / fineness**3 + fineness / 400
    swet_fus = np.pi * np.sqrt(d.fuselage_w_m * d.fuselage_h_m) * lt * 0.85
    fus = cf_turb(V * lt / NU) * ff_fus * swet_fus
    tail = cf_turb(V * g["tail_chord"] / NU) * (1 + 1.2 * 0.10) * 2.04 * (g["tail_span"] * g["tail_chord"] + 2 * 0.035)
    booms = 2 * cf_turb(V * g["boom_len"] / NU) * 1.05 * np.pi * 0.025 * g["boom_len"]
    # Stopped lift rotors: motor bell above a streamlined printed nacelle (bell
    # side-on CD 0.9 over its exposed 20 mm height), blade at ~12 deg pitch
    # (planform area x CD 0.15) and the faired nacelle (CD 0.15 on frontal area).
    motor = 0.9 * 0.0556 * 0.020
    blade = 0.15 * (2 * 0.229 * 0.030)
    mount = 0.15 * 0.040 * 0.060
    rotors = 8 * (motor + blade + mount)
    gear = 4 * 0.6 * 0.012 * 0.15
    pusher_hub = 0.004
    base = dict(wing=wing, fuselage=fus, tail=tail, booms=booms, stopped_rotors=rotors,
                landing_gear=gear, pusher_hub=pusher_hub)
    total = sum(base.values()) * 1.10  # 10 % interference/excrescence
    base["interference_10pct"] = total - sum(base.values())
    base["total"] = total
    return base


def cruise(d: Design, V: float | None = None) -> dict:
    g = d.geom
    V = V or d.cruise_ms
    W = d.mass["total_kg"] * G
    S = g["S"]
    q = 0.5 * RHO * V**2
    CL = W / (q * S)
    e = 0.80
    if d.cd0_override is not None:
        cd0 = d.cd0_override
    else:
        d_saved = d.cruise_ms
        d.cruise_ms = V
        cd0 = drag_area(d)["total"] / S
        d.cruise_ms = d_saved
    CD = cd0 + CL**2 / (np.pi * e * g["AR"])
    D = q * S * CD
    op = PUSHER.operating_point(D, V)
    shaft = op["shaft_w"] * APC_POWER_FACTOR
    el = PUSHER_MOTOR.electrical(shaft / (op["rpm"] * 2 * np.pi / 60), op["rpm"])
    p_elec = el["power_w"] + 8.0  # avionics + servos
    return dict(V=V, CL=CL, CD0=cd0, CD=CD, LD=CL / CD, drag_n=D, prop_rpm=op["rpm"],
                eta_prop=op["eta_prop"] / APC_POWER_FACTOR, eta_motor=el["eta_motor"],
                motor_current=el["current_a"], motor_voltage=el["voltage_v"], p_elec_w=p_elec)


def hover(d: Design, mass_factor: float = 1.0) -> dict:
    W = d.mass["total_kg"] * G * mass_factor
    T = W / 8
    p = 8 * LIFT.electrical_power_w(T) + 8.0
    return dict(thrust_per_rotor_n=T, p_elec_w=p, rpm=LIFT.rpm(T), torque_nm=LIFT.torque_nm(T),
                throttle_frac_thrust=T / LIFT.max_thrust_n, tw_ratio=8 * LIFT.max_thrust_n / W,
                fm=LIFT.figure_of_merit(T))


def rotor_layout(d: Design) -> list[dict]:
    """Rotor positions relative to CG and spin direction (+1 = CCW seen from above)."""
    g = d.geom
    # Alternate along each boom, mirror across the centreline: diagonal pairs counter-rotate.
    spins_port = [+1, -1, +1, -1]
    out = []
    for side, sy in (("port", -1), ("stbd", +1)):
        for i, x in enumerate(g["rotor_x"]):
            spin = spins_port[i] * (1 if side == "port" else -1)
            out.append(dict(name=f"R{('P' if sy < 0 else 'S')}{i + 1}", x=x - g["x_cg_target"], y=sy * d.boom_y_m, spin=spin))
    return out


def rotor_out(d: Design) -> list[dict]:
    """Minimise the maximum rotor thrust with one rotor failed (vertical, roll, pitch, yaw trim)."""
    rotors = rotor_layout(d)
    W = d.mass["total_kg"] * G
    k = LIFT.torque_nm(W / 8) / (W / 8)  # torque/thrust ratio (m)
    tmax = LIFT.max_thrust_n
    res_all = []
    for fail in range(8):
        idx = [i for i in range(8) if i != fail]
        n = len(idx)
        # variables: T_i (n), s (max thrust); minimise s
        cvec = np.zeros(n + 1)
        cvec[-1] = 1
        Aeq = np.zeros((4, n + 1))
        beq = np.array([W, 0, 0, 0])
        for j, i in enumerate(idx):
            r = rotors[i]
            Aeq[0, j] = 1
            Aeq[1, j] = r["y"]
            Aeq[2, j] = r["x"]
            Aeq[3, j] = r["spin"] * k
        Aub = np.zeros((n, n + 1))
        for j in range(n):
            Aub[j, j] = 1
            Aub[j, -1] = -1
        sol = linprog(cvec, A_ub=Aub, b_ub=np.zeros(n), A_eq=Aeq, b_eq=beq,
                      bounds=[(0, tmax)] * n + [(0, None)], method="highs")
        if not sol.success:
            res_all.append(dict(failed=rotors[fail]["name"], feasible=False))
            continue
        tm = sol.x[-1]
        res_all.append(dict(failed=rotors[fail]["name"], feasible=True, max_thrust_n=tm,
                            max_thrust_frac=tm / tmax,
                            max_motor_power_w=LIFT.electrical_power_w(min(tm, tmax))))
    return res_all


def mission(d: Design, hover_s: float = 120.0, transition_wh: float = 8.0, reserve_soc: float = 0.20) -> dict:
    bat = COMPONENTS[d.battery]
    v_nom = 3.7 * bat["cells"] * SERIES_PACKS
    strings = d.n_battery // SERIES_PACKS
    e_nom = strings * bat["capacity_ah"] * v_nom
    usable = e_nom * (1 - reserve_soc) * 0.95  # 5 % for voltage sag / ageing
    h = hover(d)
    e_hover = h["p_elec_w"] * hover_s / 3600
    cr = cruise(d)
    e_cruise = usable - e_hover - transition_wh
    t_cruise = e_cruise / cr["p_elec_w"] * 3600
    i_hover = h["p_elec_w"] / (v_nom * 0.95)
    return dict(e_nom_wh=e_nom, e_usable_wh=usable, e_hover_wh=e_hover, hover_current_a=i_hover,
                c_rate_hover=i_hover / (strings * bat["capacity_ah"]), e_cruise_wh=e_cruise,
                cruise_min=t_cruise / 60, range_km=t_cruise * cr["V"] / 1000, cruise=cr, hover=h)


def best_cruise_speed(d: Design) -> float:
    """Speed for maximum range (minimum electrical energy per metre) above 1.3 Vstall."""
    vs = stall_speed(d)
    speeds = np.arange(max(14.0, 1.3 * vs), 34.01, 0.5)
    epm = [cruise(d, v)["p_elec_w"] / v for v in speeds]
    return float(speeds[int(np.argmin(epm))])


def stall_speed(d: Design, clmax: float = 1.25) -> float:
    return float(np.sqrt(2 * d.mass["total_kg"] * G / (RHO * d.geom["S"] * clmax)))


def summary(d: Design) -> dict:
    m = mission(d)
    ro = rotor_out(d)
    return dict(design={k: v for k, v in asdict(d).items() if k not in ("geom", "mass")},
                geometry=d.geom, mass=d.mass, mission=m, stall_ms=stall_speed(d),
                rotor_out=ro, drag_buildup=drag_area(d))
