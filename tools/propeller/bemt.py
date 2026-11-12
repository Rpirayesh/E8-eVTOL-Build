"""Blade-element momentum theory (BEMT) and Adkins-Liebeck minimum-induced-loss design.

At each radial station the axial induced velocity v_i is found by a bracketed root
solve of  blade-element thrust = momentum thrust  (Prandtl tip/hub loss), which is
robust from static thrust to forward flight.  Swirl is neglected (small for these
lightly loaded props).  Section polars come from NeuralFoil, tabulated once.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import brentq

RHO, NU = 1.225, 1.46e-5


@lru_cache(maxsize=None)
def polar_table(airfoil: str):
    import aerosandbox as asb
    import neuralfoil as nf
    alphas = np.arange(-20, 25.01, 0.5)
    res = np.geomspace(2e4, 2e6, 12)
    A, Rg = np.meshgrid(alphas, res, indexing="ij")
    r = nf.get_aero_from_airfoil(asb.Airfoil(airfoil), alpha=A.ravel(), Re=Rg.ravel(), model_size="large")
    cl = np.asarray(r["CL"]).reshape(A.shape)
    cd = np.asarray(r["CD"]).reshape(A.shape)
    fcl = RegularGridInterpolator((alphas, np.log(res)), cl, bounds_error=False, fill_value=None)
    fcd = RegularGridInterpolator((alphas, np.log(res)), cd, bounds_error=False, fill_value=None)
    return fcl, fcd


def polar(airfoil, alpha_deg, re):
    fcl, fcd = polar_table(airfoil)
    pts = np.column_stack([np.clip(np.atleast_1d(alpha_deg), -20, 25), np.log(np.clip(np.atleast_1d(re), 2e4, 2e6))])
    return fcl(pts), np.clip(fcd(pts), 0.006, None)


@dataclass
class Blade:
    R: float                 # tip radius (m)
    r: np.ndarray            # stations (m)
    chord: np.ndarray        # (m)
    beta: np.ndarray         # geometric pitch angle (rad), relative to the rotor plane
    B: int = 2
    airfoil: str = "clarky"
    hub_r: float = 0.02


def _station(bl: Blade, k: int, V: float, om: float):
    r, c, beta = bl.r[k], bl.chord[k], bl.beta[k]

    def elems(vi):
        va, vt = V + vi, om * r
        phi = math.atan2(va, vt)
        W = math.hypot(va, vt)
        cl, cd = polar(bl.airfoil, math.degrees(beta - phi), W * c / NU)
        cl, cd = float(cl[0]), float(cd[0])
        s = max(abs(math.sin(phi)), 1e-4)
        ft = bl.B / 2 * (bl.R - r) / (r * s)
        fh = bl.B / 2 * (r - bl.hub_r) / (r * s)
        F = (2 / math.pi) ** 2 * math.acos(math.exp(-min(ft, 50))) * math.acos(math.exp(-min(fh, 50)))
        dT = 0.5 * RHO * W**2 * c * bl.B * (cl * math.cos(phi) - cd * math.sin(phi))
        dQ = 0.5 * RHO * W**2 * c * bl.B * (cl * math.sin(phi) + cd * math.cos(phi)) * r
        return dT, dQ, F, phi, cl

    g = lambda vi: elems(vi)[0] - 4 * math.pi * r * RHO * max(elems(vi)[2], 1e-3) * (V + vi) * vi
    hi = 5.0
    while g(hi) > 0 and hi < 400:
        hi *= 2
    vi = brentq(g, 0.0, hi, xtol=1e-6) if g(0.0) > 0 else 0.0
    dT, dQ, F, phi, cl = elems(vi)
    return dT, dQ, vi, cl


def solve(bl: Blade, V: float, rpm: float) -> dict:
    om = rpm * 2 * math.pi / 60
    out = np.array([_station(bl, k, V, om) for k in range(len(bl.r))])
    dT, dQ = out[:, 0], out[:, 1]
    T, Q = np.trapezoid(dT, bl.r), np.trapezoid(dQ, bl.r)
    P = Q * om
    n, D = rpm / 60, 2 * bl.R
    return dict(T=T, Q=Q, P=P, eta=T * V / P if P > 0 else 0.0, J=V / (n * D), Ct=T / (RHO * n**2 * D**4),
                Cp=P / (RHO * n**3 * D**5), dT_per_blade=dT / bl.B, dQ_per_blade=dQ / bl.B, cl=out[:, 3])


def adkins_liebeck(R, hub_r, B, V, rpm, T_req, airfoil="clarky", cl_d=0.7, alpha_d=4.0, cd_d=0.012, n=25) -> Blade:
    """Minimum-induced-loss blade (Adkins & Liebeck, J. Propulsion & Power 10(5), 1994)."""
    om = rpm * 2 * math.pi / 60
    lam = V / (om * R)
    xi = np.linspace(hub_r / R * 1.15, 0.99, n)
    eps = cd_d / cl_d
    zeta = 0.1
    for _ in range(100):
        phi_t = math.atan(lam * (1 + zeta / 2))
        phi = np.arctan(math.tan(phi_t) / xi)
        F = 2 / math.pi * np.arccos(np.exp(-B / 2 * (1 - xi) / math.sin(phi_t)))
        x = om * xi * R / V
        G = F * x * np.cos(phi) * np.sin(phi)
        I1p = 4 * xi * G * (1 - eps * np.tan(phi))
        I2p = lam * (I1p / (2 * xi)) * (1 + eps / np.tan(phi)) * np.sin(phi) * np.cos(phi)
        I1, I2 = np.trapezoid(I1p, xi), np.trapezoid(I2p, xi)
        Tc = 2 * T_req / (RHO * V**2 * math.pi * R**2)
        z_new = I1 / (2 * I2) - math.sqrt((I1 / (2 * I2)) ** 2 - Tc / I2)
        if abs(z_new - zeta) < 1e-8:
            zeta = z_new
            break
        zeta = z_new
    a = zeta / 2 * np.cos(phi) ** 2 * (1 - eps * np.tan(phi))
    W = V * (1 + a) / np.sin(phi)
    Wc = 4 * math.pi * lam * G * V * R * zeta / (cl_d * B)
    chord = Wc / W
    beta = phi + math.radians(alpha_d)
    return Blade(R=R, r=xi * R, chord=chord, beta=beta, B=B, airfoil=airfoil, hub_r=hub_r)


def apc_like(D_in: float, pitch_in: float, B: int = 2, n: int = 25) -> Blade:
    """Approximate APC thin-electric planform: chord peaks ~0.11 D at 0.3 R; constant
    geometric pitch.  Used only to check the BEMT method against APC's published data."""
    R = D_in * 0.0254 / 2
    xi = np.linspace(0.15, 0.99, n)
    c_over_R = 0.10 + 0.10 * np.sin(np.pi * np.clip((xi - 0.1) / 0.95, 0, 1)) ** 0.8 - 0.07 * xi**4
    r = xi * R
    beta = np.arctan(pitch_in * 0.0254 / (2 * math.pi * r))
    return Blade(R=R, r=r, chord=c_over_R * R, beta=beta, B=B, airfoil="clarky", hub_r=0.15 * R)
