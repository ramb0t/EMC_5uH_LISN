"""Software calibration for lvna.py captures.

A capture directory holds short/open/load/thru.npz (taken at the cable ends) and
fx_open/fx_short.npz (the SMA-to-banana adapter open in air, then shorted at its tip).
Port 1: SOL with ideal standards. Transmission: one-path enhanced response from the thru,
isolation from the load capture, S22 terms ignored. Adapter: open/short compensation.
"""
from pathlib import Path

import numpy as np


class Cal:
    def __init__(self, d):
        self.d = Path(d)
        sh, op, ld, th = (self.raw(n) for n in ("short", "open", "load", "thru"))
        self.f = ld["f"]
        self.ED = ld["s11"]
        a, b = sh["s11"] - self.ED, op["s11"] - self.ED
        self.ES = (a + b) / (b - a)
        self.ER = b * (1 - self.ES)
        self.EX = ld["s21"]
        EL = self.s11(th["s11"])
        self.ET = (th["s21"] - self.EX) * (1 - self.ES * EL)
        self.Zo = z(self.s11(self.raw("fx_open")["s11"]))
        self.Zs = z(self.s11(self.raw("fx_short")["s11"]))

    def raw(self, name):
        r = np.load(self.d / f"{name}.npz")
        return r

    def s11(self, m):
        return (m - self.ED) / (self.ER + self.ES * (m - self.ED))

    def measure(self, name):
        """Return f, Z at the adapter tip, |V_tip / V_port2| and corrected S21 for one capture."""
        r = self.raw(name)
        if not np.array_equal(r["f"], self.f):
            raise SystemExit(f"{name}: frequency grid differs from the calibration")
        s11 = self.s11(r["s11"])
        s21 = (r["s21"] - self.EX) / self.ET * (1 - self.ES * s11)
        zm = z(s11)
        Z = (zm - self.Zs) / (1 - (zm - self.Zs) / self.Zo)
        v_tip = (1 + s11) * Z / (Z + self.Zs)  # voltage at the cal plane, referred through the adapter
        return self.f, Z, np.abs(v_tip / s21), s21

    def floor_db(self):
        return -20 * np.log10(np.abs(self.EX / self.ET) + 1e-15)


def z(g):
    return 50 * (1 + g) / (1 - g)


def cispr25_z(f):
    """Nominal 5 uH / 0.1 uF / 50 ohm artificial network impedance."""
    w = 2 * np.pi * f
    zl, zc = 1j * w * 5e-6, 1 / (1j * w * 0.1e-6) + 50
    return np.abs(zl * zc / (zl + zc))
