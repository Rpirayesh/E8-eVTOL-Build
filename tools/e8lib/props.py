"""Propeller and lift-motor performance from manufacturer data.

Hover performance uses the T-Motor MN5008 KV340 + P18x6.1 bench table directly
(electrical input power versus thrust), so motor and ESC losses are included.

Forward-flight performance of the pusher uses APC's published PER3 tables
(Ct, Cp versus advance ratio at several rpm).  APC tables are the manufacturer's
own blade-element predictions, not wind-tunnel measurements; they are used here
because they are the best openly available forward-flight data for these props.
"""
from __future__ import annotations

import csv
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "design" / "data"
CACHE = ROOT / ".cache"
G = 9.80665


def _read_csv(path: Path) -> dict[str, np.ndarray]:
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for key in rows[0]:
        try:
            out[key] = np.array([float(r[key]) for r in rows])
        except ValueError:
            out[key] = np.array([r[key] for r in rows])
    return out


@dataclass
class LiftRotor:
    """MN5008 KV170 + T-Motor P18x6.1 on 12S, from the manufacturer bench table.

    Between bench rows, power and torque are interpolated in log(thrust) with a
    monotone cubic (PCHIP), which follows the P ~ T^1.5 trend of a rotor.
    """

    table: dict[str, np.ndarray]
    diameter_m: float = 18 * 0.0254

    @classmethod
    def load(cls, filename: str = "mn5008_kv170_p18x6.1_12s.csv") -> "LiftRotor":
        return cls(_read_csv(DATA / filename))

    def _interp(self, thrust_n: float, key: str) -> float:
        t = self.table["thrust_g"] * G / 1000
        f = PchipInterpolator(np.log(t), np.log(self.table[key]))
        return float(np.exp(f(np.log(thrust_n))))

    @property
    def max_thrust_n(self) -> float:
        return float(self.table["thrust_g"].max()) * G / 1000

    def electrical_power_w(self, thrust_n: float) -> float:
        """Interpolated electrical input power (ESC input) at a thrust."""
        t = self.table["thrust_g"] * G / 1000
        if thrust_n > t.max():
            raise ValueError(f"thrust {thrust_n:.1f} N above bench maximum {t.max():.1f} N")
        if thrust_n < t[0]:
            # Below the first table row, scale with ideal momentum theory P ~ T^1.5.
            return float(self.table["power_w"][0] * (thrust_n / t[0]) ** 1.5)
        return self._interp(thrust_n, "power_w")

    def rpm(self, thrust_n: float) -> float:
        return self._interp(max(thrust_n, 1e-3), "rpm")

    def torque_nm(self, thrust_n: float) -> float:
        return self._interp(max(thrust_n, 1e-3), "torque_nm")

    def figure_of_merit(self, thrust_n: float, rho: float = 1.225) -> float:
        """FM = ideal induced power / shaft power, shaft power from torque x speed."""
        area = np.pi * self.diameter_m**2 / 4
        p_ideal = thrust_n**1.5 / np.sqrt(2 * rho * area)
        p_shaft = self.torque_nm(thrust_n) * self.rpm(thrust_n) * 2 * np.pi / 60
        return float(p_ideal / p_shaft)


def apc_file(name: str) -> Path:
    """Download (once) and return an APC PER3 performance file, e.g. '17x10E'."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"PER3_{name}.dat"
    if not path.exists():
        url = f"https://www.apcprop.com/files/PER3_{name}.dat"
        subprocess.run(["curl", "-sSfL", "-o", str(path), url], check=True)
    return path


@dataclass
class APCProp:
    name: str
    diameter_m: float
    rpm: np.ndarray       # (n_rpm,)
    J: list[np.ndarray]   # per rpm
    Ct: list[np.ndarray]
    Cp: list[np.ndarray]

    @classmethod
    def load(cls, name: str) -> "APCProp":
        text = apc_file(name).read_text(errors="ignore")
        diameter_in = float(re.match(r"\s*([\d.]+)x", text.strip()).group(1))
        blocks = re.split(r"PROP RPM =\s*", text)[1:]
        rpms, Js, Cts, Cps = [], [], [], []
        for block in blocks:
            lines = block.splitlines()
            rpm = float(lines[0].split()[0])
            rows = []
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 15:
                    try:
                        rows.append([float(p) for p in parts[:5]])
                    except ValueError:
                        continue
            if len(rows) < 3:
                continue
            arr = np.array(rows)
            rpms.append(rpm)
            Js.append(arr[:, 1])
            Cts.append(arr[:, 3])
            Cps.append(arr[:, 4])
        return cls(name, diameter_in * 0.0254, np.array(rpms), Js, Cts, Cps)

    def coefficients(self, rpm: float, J: float) -> tuple[float, float]:
        """Ct, Cp at (rpm, J), linear in rpm between tabulated rpm blocks."""
        i = int(np.clip(np.searchsorted(self.rpm, rpm) - 1, 0, len(self.rpm) - 2))
        w = np.clip((rpm - self.rpm[i]) / (self.rpm[i + 1] - self.rpm[i]), 0, 1)
        vals = []
        for k in (i, i + 1):
            jmax = self.J[k][-1]
            jj = min(J, jmax)
            ct = np.interp(jj, self.J[k], self.Ct[k])
            cp = np.interp(jj, self.J[k], self.Cp[k])
            if J > jmax:  # beyond windmill point: no thrust
                ct = -1.0
            vals.append((ct, cp))
        ct = (1 - w) * vals[0][0] + w * vals[1][0]
        cp = (1 - w) * vals[0][1] + w * vals[1][1]
        return float(ct), float(cp)

    def thrust_power(self, rpm: float, V: float, rho: float = 1.225) -> tuple[float, float]:
        n = rpm / 60
        D = self.diameter_m
        ct, cp = self.coefficients(rpm, V / (n * D))
        return ct * rho * n**2 * D**4, cp * rho * n**3 * D**5

    def operating_point(self, thrust_n: float, V: float, rho: float = 1.225) -> dict:
        """Find rpm giving the required thrust at airspeed V; return shaft power etc."""
        lo, hi = self.rpm[0], self.rpm[-1]
        f = lambda r: self.thrust_power(r, V, rho)[0] - thrust_n
        if f(hi) < 0:
            raise ValueError(f"{self.name}: cannot produce {thrust_n:.1f} N at {V:.1f} m/s")
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid
        rpm = 0.5 * (lo + hi)
        T, P = self.thrust_power(rpm, V, rho)
        return {"rpm": rpm, "thrust_n": T, "shaft_w": P, "eta_prop": T * V / P if P > 0 else 0.0,
                "torque_nm": P / (rpm * 2 * np.pi / 60)}


@dataclass
class Motor:
    """Steady brushless DC model: V = I*R + w/Kv, Q = (I - I0)/Kv (SI Kv)."""

    kv_rpm_per_v: float
    r_ohm: float
    i0_a: float
    mass_kg: float

    def electrical(self, torque_nm: float, rpm: float) -> dict:
        kv = self.kv_rpm_per_v * 2 * np.pi / 60  # rad/s/V
        current = torque_nm * kv + self.i0_a
        voltage = current * self.r_ohm + (rpm * 2 * np.pi / 60) / kv
        p_in = voltage * current
        p_out = torque_nm * rpm * 2 * np.pi / 60
        return {"current_a": current, "voltage_v": voltage, "power_w": p_in,
                "eta_motor": p_out / p_in if p_in > 0 else 0.0}
