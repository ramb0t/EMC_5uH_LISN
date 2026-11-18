#!/usr/bin/env python3
"""Conducted-emission sweep through the LISN with a tinySA Ultra, plotted against IEC 61000-6-3.

usage: tsa.py NAME [--line plus|minus|none] [--sweeps N] [--atten DB] [--port DEV] [--out DIR]

Sweeps 150 kHz-30 MHz at 10 kHz RBW in 5 kHz steps, keeps the max hold of N sweeps, and adds
the LISN's measured VDF for that line (test/vna results), so the result is dBuV at the DUT jack.
--line none gives the raw tinySA reading in dBuV (for the instrument floor).
Writes NAME.csv and NAME.png. Sets RBW and attenuation on the tinySA; nothing is saved to it.
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

HERE = Path(__file__).resolve().parent
VDF_DIR = HERE.parent / "vna" / "data" / "2026-11-18" / "results"
START, STOP, STEP, RBW_KHZ, CHUNK = 150e3, 30e6, 5e3, 10, 450  # tinySA scan maximum
# IEC 61000-6-3:2021 Table 5, clause 5.1 (V-AN), dBuV: (f_lo MHz, f_hi MHz, QP, AV)
LIMITS = [(0.15, 0.5, 79, 66), (0.5, 30, 73, 60)]
VALID_FROM = 2e6  # below this the 5 uH LISN reads low against the 50 uH V-AN the limits assume


def find_port():
    for p in serial.tools.list_ports.comports():
        if (p.product or "").startswith("tinySA"):
            return p.device
    raise SystemExit("no tinySA found; pass --port")


class TinySA:
    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=120)
        self.cmd("")

    def cmd(self, c):
        self.s.reset_input_buffer()
        self.s.write((c + "\r").encode())
        return self.s.read_until(b"ch> ").decode(errors="replace")

    def scan(self, f0, f1, n):
        out = self.cmd(f"scan {int(f0)} {int(f1)} {n} 3")
        rows = [ln.split() for ln in out.splitlines()[1:] if ln[:1].isdigit()]
        if len(rows) != n:
            raise SystemExit(f"scan {f0:g}-{f1:g}: got {len(rows)} of {n} points")
        # firmware prints a mantissa that rounds up to 10 as ':' (e.g. -100 dBm -> "-:.000000e+01")
        return np.array([[float(r[0]), float(r[1].replace(":", "10"))] for r in rows])

    def sweep(self):
        f = np.arange(START, STOP + 1, STEP)
        parts = [self.scan(c[0], c[-1], len(c)) for c in np.array_split(f, int(np.ceil(len(f) / CHUNK)))]
        a = np.vstack(parts)
        return a[:, 0], a[:, 1]


def vdf(line, f):
    if line == "none":
        return np.zeros_like(f)
    d = np.loadtxt(VDF_DIR / f"dut_{line}.csv", delimiter=",", skiprows=1)
    return np.interp(f, d[:, 0], d[:, 4])


def limit(f, col):
    out = np.full_like(f, np.nan)
    for lo, hi, qp, av in LIMITS:
        out[(f >= lo * 1e6) & (f <= hi * 1e6)] = qp if col == "qp" else av
    return out


def plot(path, name, f, dbuv, info):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    F = f / 1e6
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axvspan(F[0], VALID_FROM / 1e6, color="#ecebe7", lw=0, label="Below 2 MHz: 5 µH LISN reads low vs V-AN")
    ax.step(F, limit(f, "qp"), where="post", color="#0b0b0b", lw=1.2, label="61000-6-3 QP limit")
    ax.step(F, limit(f, "av"), where="post", color="#0b0b0b", lw=1.2, ls="--", label="61000-6-3 AV limit")
    ax.plot(F, dbuv, color="#2a78d6", lw=1, label=f"{name} (peak, max hold)")
    ok = f >= VALID_FROM
    k = np.argmax(np.where(ok, dbuv - limit(f, "av"), -np.inf))
    margin = limit(f, "av")[k] - dbuv[k]
    ax.plot(F[k], dbuv[k], "o", ms=8, color="#2a78d6", mec="#fcfcfb", mew=2)
    ax.annotate(f"{dbuv[k]:.1f} dBµV at {F[k]:.3f} MHz\n{margin:+.1f} dB to AV limit", (F[k], dbuv[k]),
                xytext=(10, 10), textcoords="offset points", fontsize=9)
    ax.set_xscale("log")
    ax.set_xlim(0.15, 30)
    ax.set_xticks([0.15, 0.3, 0.5, 1, 2, 5, 10, 30])
    ax.set_xticklabels(["0.15", "0.3", "0.5", "1", "2", "5", "10", "30"])
    ax.set_ylim(min(0, np.nanmin(dbuv) - 5), 90)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("dBµV at DUT jack" if info["line"] != "none" else "dBµV at tinySA input")
    ax.grid(True, which="both", color="#e4e3df")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(f"{name}: conducted emission, {info['line']} line", fontweight="bold")
    ax.text(0.99, 0.02, f"RBW {RBW_KHZ} kHz, atten {info['atten']} dB, {info['sweeps']} sweeps, {info['time']}",
            transform=ax.transAxes, ha="right", fontsize=8, color="#52514e")
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    return margin, F[k]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--line", choices=("plus", "minus", "none"), default="plus")
    ap.add_argument("--sweeps", type=int, default=3)
    ap.add_argument("--atten", default="10")
    ap.add_argument("--port")
    ap.add_argument("--out", default=str(HERE / "data"))
    a = ap.parse_args()
    t = TinySA(a.port or find_port())
    t.cmd(f"rbw {RBW_KHZ}")
    t.cmd(f"attenuate {a.atten}")
    t.cmd("spur auto")
    hold = None
    t0 = time.time()
    for _ in range(a.sweeps):
        f, dbm = t.sweep()
        hold = dbm if hold is None else np.maximum(hold, dbm)
    dbuv = hold + 107.0 + vdf(a.line, f)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    info = dict(line=a.line, atten=a.atten, sweeps=a.sweeps, time=datetime.now().strftime("%Y-%m-%d %H:%M"))
    np.savetxt(out / f"{a.name}.csv", np.column_stack([f, hold, dbuv]), delimiter=",", fmt="%.6g",
               header=f"f_Hz,tinysa_dBm,dBuV_at_DUT  # {info}", comments="")
    margin, fk = plot(out / f"{a.name}.png", a.name, f, dbuv, info)
    print(f"{a.name}: {len(f)} points x {a.sweeps} sweeps in {time.time() - t0:.0f} s; "
          f"max {np.max(dbuv):.1f} dBuV; worst above 2 MHz {margin:+.1f} dB to AV limit at {fk:.3f} MHz")
    print(out / f"{a.name}.png")


if __name__ == "__main__":
    main()
