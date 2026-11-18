#!/usr/bin/env python3
"""Impedance and voltage division factor (VDF) of one LISN line, against CISPR 25.

usage: lisn_line.py DATA_DIR CAPTURE [CAPTURE...]   -> DATA_DIR/../results/CAPTURE.{csv,png}
Capture: port 1 (adapter) on a DUT jack, port 2 on that line's HF SMA, 50 ohm on the other
HF SMA, supply jacks shorted to the case. VDF in dB is what to add to the SMA reading.
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cal import Cal, cispr25_z  # noqa: E402


def main(data, names):
    cal = Cal(data)
    out = Path(data).parent / "results"
    out.mkdir(exist_ok=True)
    for name in names:
        f, Z, ratio, _ = cal.measure(name)
        vdf = 20 * np.log10(ratio)
        zref = cispr25_z(f)
        dev = np.abs(Z) / zref - 1
        np.savetxt(out / f"{name}.csv", np.column_stack([f, np.abs(Z), np.degrees(np.angle(Z)), zref, vdf]),
                   delimiter=",", header="f_Hz,Z_ohm,Z_deg,Zref_ohm,VDF_dB", comments="", fmt="%.6g")
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
        a1.fill_between(f / 1e6, zref * 0.8, zref * 1.2, color="0.85", label="CISPR 25 ±20 %")
        a1.plot(f / 1e6, zref, "k--", lw=1, label="nominal 5 µH / 0.1 µF / 50 Ω")
        a1.plot(f / 1e6, np.abs(Z), lw=1.5, label=name)
        a1.set_ylabel("|Z| at DUT jack (Ω)")
        a1.legend()
        a1.grid(True, which="both", alpha=.3)
        a2.plot(f / 1e6, vdf, lw=1.5)
        a2.set_ylabel("VDF (dB), add to SMA reading")
        a2.set_xlabel("MHz")
        a2.set_xscale("log")
        a2.grid(True, which="both", alpha=.3)
        fig.suptitle(f"{name}: impedance and voltage division factor")
        fig.tight_layout()
        fig.savefig(out / f"{name}.png", dpi=110)
        plt.close(fig)
        k = np.argmax(np.abs(dev))
        print(f"{name}: worst |Z| deviation {100 * dev[k]:+.1f} % at {f[k] / 1e6:.2f} MHz")
        for fq in (0.15, 0.5, 1, 2, 5, 10, 30, 50, 108):
            k = np.argmin(np.abs(f - fq * 1e6))
            print(f"  {f[k] / 1e6:7.2f} MHz |Z| {abs(Z[k]):5.1f} Ω ({100 * dev[k]:+5.1f} %)  VDF {vdf[k]:5.2f} dB")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
