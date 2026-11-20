#!/usr/bin/env python3
"""Split two-channel LISN captures into common and differential mode.

usage: cmdm.py OUT_STEM CAPTURE.npz [CAPTURE.npz ...] [--f0 HZ]

Each capture is a dho.py long record with CH1 on HF+ and CH2 on HF-, both into 50 ohm.
CM = (CH1 + CH2) / 2 and DM = (CH1 - CH2) / 2, sample by sample, then FFT (Hann, dBuV RMS
per bin). Power spectra are averaged over the captures. The LISN's measured VDF is added, so
levels are at the DUT jack. Writes OUT_STEM.csv and OUT_STEM.png.
"""
import argparse
from pathlib import Path

import numpy as np

import dho

VDF_DIR = Path(__file__).resolve().parent.parent / "vna" / "data" / "2026-11-18" / "results"


def vdf(line, f):
    d = np.loadtxt(VDF_DIR / f"dut_{line}.csv", delimiter=",", skiprows=1)
    return np.interp(f, d[:, 0], d[:, 4])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("captures", nargs="+")
    ap.add_argument("--f0", type=float, default=0, help="mark harmonics of this frequency")
    a = ap.parse_args()
    acc = None
    for c in a.captures:
        z = np.load(c)
        t, p, m = z["t0"], z["v0"], z["v1"]
        specs = [dho.spectrum(t, x) for x in (p, m, (p + m) / 2, (p - m) / 2)]
        f, enbw = specs[0][0], specs[0][2]
        pw = np.array([10 ** (s[1] / 10) for s in specs])
        acc = pw if acc is None else acc + pw
    db = 10 * np.log10(acc / len(a.captures))
    k = (f >= 100e3) & (f <= 30e6)
    f, db = f[k], db[:, k]
    vp, vm = vdf("plus", f), vdf("minus", f)
    db = db + np.array([vp, vm, (vp + vm) / 2, (vp + vm) / 2])
    out = Path(a.out)
    np.savetxt(out.with_suffix(".csv"), np.column_stack([f, *db]), delimiter=",", fmt=["%.0f"] + ["%.1f"] * 4,
               header=f"f_Hz,HFplus_dBuV,HFminus_dBuV,CM_dBuV,DM_dBuV  # at DUT jack, {len(a.captures)} records, ENBW {enbw:.0f} Hz",
               comments="")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5.5))
    if a.f0:
        for h in range(1, int(30e6 / a.f0) + 1):
            ax.axvline(h * a.f0 / 1e6, color="#e4e3df", lw=0.6, zorder=0)
    ax.plot(f / 1e6, db[2], color="#2a78d6", lw=0.7, label="Common mode, (HF+ + HF−)/2")
    ax.plot(f / 1e6, db[3], color="#eb6834", lw=0.7, label="Differential mode, (HF+ − HF−)/2")
    ax.set_xscale("log")
    ax.set_xlim(0.1, 30)
    ax.set_xticks([0.1, 0.2, 0.4, 1, 2, 5, 10, 30])
    ax.set_xticklabels(["0.1", "0.2", "0.4", "1", "2", "5", "10", "30"])
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel(f"dBµV RMS per bin at DUT jack (ENBW {enbw / 1e3:.1f} kHz)")
    ax.set_title(f"{out.name}: common and differential mode, {len(a.captures)} records averaged", fontweight="bold")
    ax.legend(loc="upper right", frameon=False)
    dho.style(ax, "")
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), dpi=120)
    print(out.with_suffix(".png"))


if __name__ == "__main__":
    main()
