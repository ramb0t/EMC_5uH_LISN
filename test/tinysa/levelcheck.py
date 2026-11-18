#!/usr/bin/env python3
"""Check the tinySA + LISN chain against the VNA-measured VDF, using the tinySA CAL comb.

usage: levelcheck.py direct    CAL -> cable -> tinySA RF
       levelcheck.py lisn      CAL -> same cable -> adapter -> DUT+, HF+ -> tinySA RF, LISN unpowered
       levelcheck.py analyse   compare the two against data from test/vna

CAL is set to 1 MHz (square wave, harmonics every 1 MHz). For each harmonic from 2 to 30 MHz,
lisn - direct should equal VDF - 20 log|2Z/(Z+50)|: the second term is the LISN not being 50 ohm.
"""
import sys
from pathlib import Path

import numpy as np

import tsa

OUT = tsa.HERE / "data"
H = np.arange(2, 31) * 1e6


def capture(name):
    t = tsa.TinySA(tsa.find_port())
    t.cmd(f"rbw {tsa.RBW_KHZ}")
    t.cmd("attenuate 10")
    t.cmd("spur auto")
    t.cmd("caloutput 1")
    peaks = []
    for h in H:
        a = t.scan(h - 40e3, h + 40e3, 33)
        peaks.append(a[:, 1].max())
    t.cmd("caloutput off")
    OUT.mkdir(exist_ok=True)
    np.savetxt(OUT / f"levelcheck_{name}.csv", np.column_stack([H, peaks]), delimiter=",", fmt="%.6g",
               header="f_Hz,peak_dBm", comments="")
    for h, p in zip(H, peaks):
        print(f"{h / 1e6:5.0f} MHz {p:7.1f} dBm")


def analyse():
    d = np.loadtxt(OUT / "levelcheck_direct.csv", delimiter=",", skiprows=1)
    l = np.loadtxt(OUT / "levelcheck_lisn.csv", delimiter=",", skiprows=1)
    z = np.loadtxt(tsa.VDF_DIR / "dut_plus.csv", delimiter=",", skiprows=1)
    zc = z[:, 1] * np.exp(1j * np.radians(z[:, 2]))
    Z = np.interp(H, z[:, 0], zc.real) + 1j * np.interp(H, z[:, 0], zc.imag)
    vdf = np.interp(H, z[:, 0], z[:, 4])
    expected = vdf - 20 * np.log10(np.abs(2 * Z / (Z + 50)))
    loss = d[:, 1] - l[:, 1]
    floor_ok = l[:, 1] > -100  # harmonic clearly above the tinySA floor
    rows = np.column_stack([H, d[:, 1], l[:, 1], loss, expected, loss - expected])
    np.savetxt(OUT / "levelcheck.csv", rows, delimiter=",", fmt="%.6g",
               header="f_Hz,direct_dBm,lisn_dBm,measured_loss_dB,expected_loss_dB,error_dB", comments="")
    print(" MHz  direct   lisn   loss  expected  error")
    for r, ok in zip(rows, floor_ok):
        print(f"{r[0] / 1e6:4.0f} {r[1]:7.1f} {r[2]:7.1f} {r[3]:6.2f} {r[4]:8.2f} {r[5]:+6.2f}" + ("" if ok else "  (near floor)"))
    e = rows[floor_ok, 5]
    print(f"error over {len(e)} harmonics: mean {e.mean():+.2f} dB, worst {e[np.argmax(abs(e))]:+.2f} dB")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode in ("direct", "lisn"):
        capture(mode)
    elif mode == "analyse":
        analyse()
    else:
        sys.exit(__doc__)
