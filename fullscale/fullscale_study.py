"""Full-scale two-seat E8: lift + cruise with a rear pusher, compared with the original tilt-rotor point.

    python fullscale/fullscale_study.py

Starts from the assumptions of the E8 concept study (two 95 kg occupants, eight
1.7 m rotors, MGM COMPRO REB 50 motors, Molicel P50B cells, 0.92 drive efficiency,
1.5 kW auxiliaries).  Changes: lift rotors are fixed (no tilt mechanisms) and stop
in cruise; a pusher propeller provides cruise thrust.  Drag of the stopped rotors is
scaled from the subscale OpenFOAM result.  This is an engineering study, not a
build-ready design.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, linprog

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fullscale" / "results"
G0, RHO = 9.80665, 1.225

# Original concept (E8 concept assembly 0.1) for comparison
ORIGINAL = dict(config="8 tilting rotors, no pusher", mass_kg=1054.8, cruise_kph=140, wing_m2=12.0, span_m=9.0,
                hover_kw=210.6, cruise_kw=86.4, range_km=26.27, battery_kwh=46.08,
                note="values from aircraft/DESIGN_REPORT.md of the E8 Design Explorer repository")

A = dict(occupants=2, person_kg=95, rotor_D=1.7, n_rotor=8, rotor_y=3.3, rotor_x=(-4.45, -2.1, 2.1, 4.45),
         eta_drive=0.92, aux_kw=1.5, fm=0.70, cell_wh=18.0, cell_kg=0.071, cell_ah=5.0, pack_overhead=0.2226,
         series=160, start_soc=0.90, reserve_soc=0.20, hover_min=3.0, transition_kwh=2.0,
         motor_cont_kw=30.0, motor_peak_kw=50.0, cl_max=1.5, oswald=0.80, f_body_m2=0.55,
         eta_pusher=0.82)
# Fixed masses (kg) from the original budget, without the tilt mechanisms
FIXED = {"fuselage frame, floor, shell": 90, "booms, outriggers, fittings": 110, "lift propellers + hubs": 16,
         "HV protection, harness": 18, "cooling": 12, "landing gear": 20, "avionics": 10, "seats, restraints": 18,
         "safety equipment": 12, "lift motors (8 x 12)": 96, "lift inverters (8 x 4)": 32, "growth allowance": 99}
PUSHER_FIXED_KG = {"pusher propeller 1.8 m + hub": 9, "pusher mount and shaft": 6}
MOTOR_KW_PER_KG = 5.0      # continuous, axial-flux class (sized to 1.25 x cruise shaft power)
INVERTER_KW_PER_KG = 15.0


def stopped_rotor_drag_area() -> float:
    """Drag area (m^2) of the eight stopped lift rotors + nacelles, scaled from the subscale CFD."""
    path = ROOT / "analysis" / "cfd" / "cruise3d" / "results.json"
    scale = A["rotor_D"] / (18 * 0.0254)
    if path.exists():
        sub = json.loads(path.read_text())["drag_area_by_region_m2"]["rotors"]
        src = "subscale OpenFOAM (rotors region), scaled by length^2"
    else:
        sub = 0.0274
        src = "subscale component build-up, scaled by length^2"
    return sub * scale**2, src


def wing_mass(S, b):
    return 95.0 * (S / 14) ** 0.9 * (b / 10) ** 0.6


def evaluate(S, b, V_kph, n_par):
    cells = A["series"] * n_par
    m_bat = cells * A["cell_kg"] * (1 + A["pack_overhead"])
    m_base = sum(FIXED.values()) + sum(PUSHER_FIXED_KG.values()) + A["occupants"] * A["person_kg"] + m_bat + wing_mass(S, b)
    m_push = 0.0
    for _ in range(30):  # pusher motor + inverter sized to 1.25 x cruise shaft power
        m = m_base + m_push
        W = m * G0
        r = _cruise(W, S, b, V_kph)
        m_push_new = 1.25 * r["shaft_kw"] * (1 / MOTOR_KW_PER_KG + 1 / INVERTER_KW_PER_KG)
        if abs(m_push_new - m_push) < 1e-3:
            break
        m_push = m_push_new
    m = m_base + m_push
    W = m * G0
    # hover (momentum theory with a measured-class figure of merit)
    area = A["n_rotor"] * math.pi * A["rotor_D"] ** 2 / 4
    p_hover = W ** 1.5 / math.sqrt(2 * RHO * area) / A["fm"] / A["eta_drive"] / 1000 + A["aux_kw"]
    per_motor = (p_hover - A["aux_kw"]) * A["eta_drive"] / A["n_rotor"]
    cr = _cruise(W, S, b, V_kph)
    D, V, AR = cr["D"], V_kph / 3.6, b**2 / S
    p_cruise = cr["shaft_kw"] / A["eta_drive"] + A["aux_kw"]
    e_nom = cells * A["cell_wh"] / 1000
    e_avail = e_nom * (A["start_soc"] - A["reserve_soc"])
    e_hover = p_hover * A["hover_min"] / 60
    t_cruise = (e_avail - e_hover - A["transition_kwh"]) / p_cruise
    rng = t_cruise * V_kph
    v_stall = math.sqrt(2 * W / (RHO * S * A["cl_max"]))
    return dict(S=S, b=b, V_kph=V_kph, n_par=n_par, mass_kg=m, battery_kg=m_bat, battery_kwh=e_nom, hover_kw=p_hover,
                per_motor_kw=per_motor, cruise_kw=p_cruise, LD=W / D, drag_n=D, range_km=rng, stall_ms=v_stall,
                pusher_shaft_kw=cr["shaft_kw"], pusher_system_kg=m_push + sum(PUSHER_FIXED_KG.values()),
                ok=(per_motor <= A["motor_cont_kw"] and v_stall <= 0.75 * V and AR >= 6 and b <= 11))


def _cruise(W, S, b, V_kph):
    V = V_kph / 3.6
    q = 0.5 * RHO * V**2
    CL = W / (q * S)
    f_rot, _ = stopped_rotor_drag_area()
    cd0_wing = 0.012
    D = q * (A["f_body_m2"] + f_rot + S * cd0_wing) + q * S * CL**2 / (math.pi * A["oswald"] * b**2 / S)
    return dict(D=D, shaft_kw=D * V / A["eta_pusher"] / 1000)


def rotor_out(mass_kg, k_qt=0.1):
    xs, y = A["rotor_x"], A["rotor_y"]
    rot = [(x, s * y, sp) for s in (-1, 1) for x, sp in zip(xs, (1, -1, 1, -1) if s < 0 else (-1, 1, -1, 1))]
    W = mass_kg * G0
    res = []
    for fail in range(8):
        idx = [i for i in range(8) if i != fail]
        n = len(idx)
        c = np.zeros(n + 1); c[-1] = 1
        Aeq = np.zeros((4, n + 1))
        for j, i in enumerate(idx):
            x, yy, sp = rot[i]
            Aeq[:, j] = [1, yy, x, sp * k_qt]
        Aub = np.hstack([np.eye(n), -np.ones((n, 1))])
        sol = linprog(c, A_ub=Aub, b_ub=np.zeros(n), A_eq=Aeq, b_eq=[W, 0, 0, 0], bounds=[(0, None)] * (n + 1), method="highs")
        T = sol.x[-1]
        Ad = math.pi * A["rotor_D"] ** 2 / 4
        p = T ** 1.5 / math.sqrt(2 * RHO * Ad) / A["fm"] / 1000
        res.append(dict(failed=fail, max_thrust_kn=T / 1000, shaft_kw=p))
    return res


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [evaluate(S, b, V, n) for S, b, V, n in itertools.product(np.arange(8, 16.1, 1.0), np.arange(8, 11.01, 0.5),
                                                                       np.arange(140, 241, 10), (12, 16, 20))]
    feas = [r for r in rows if r["ok"]]
    pareto = {}
    for r in feas:
        if r["V_kph"] not in pareto or r["range_km"] > pareto[r["V_kph"]]["range_km"]:
            pareto[r["V_kph"]] = r
    target_speed = 180
    best = pareto[target_speed]
    ro = rotor_out(best["mass_kg"])
    f_rot, src = stopped_rotor_drag_area()
    out = dict(assumptions=A, fixed_masses=FIXED, pusher_fixed_masses=PUSHER_FIXED_KG, stopped_rotor_drag_area_m2=f_rot, drag_source=src,
               selected=best, pareto=sorted(pareto.values(), key=lambda r: r["V_kph"]), original=ORIGINAL,
               rotor_out=ro, rotor_out_note="minimum peak thrust allocation with one lift rotor failed; compare with the 30 kW continuous motor screen")
    (OUT / "results.json").write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
    P = sorted(pareto.values(), key=lambda r: r["V_kph"])
    ax.plot([r["V_kph"] for r in P], [r["range_km"] for r in P], marker="o", label="lift + cruise with pusher (this study)")
    ax.scatter([ORIGINAL["cruise_kph"]], [ORIGINAL["range_km"]], color="C3", zorder=3, label="original tilt-rotor point")
    ax.set_xlabel("Cruise speed (km/h)"); ax.set_ylabel("Range to 20 % reserve (km)"); ax.grid(alpha=.3); ax.legend(frameon=False)
    ax.set_title("Full-scale two-seat E8: range vs cruise speed")
    fig.tight_layout(); fig.savefig(OUT / "range_vs_speed.png")
    print(json.dumps(best, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("rotor-out max shaft kW:", round(max(r["shaft_kw"] for r in ro), 1))


if __name__ == "__main__":
    main()
