#!/usr/bin/env python3
"""Transfer loss (isolation or crosstalk) from port 1 to port 2, with the VNA floor.

usage: transfer.py DATA_DIR CAPTURE [CAPTURE...]   -> DATA_DIR/../results/CAPTURE.{csv,png}
Loss is -20 log10 |S21| from a 50 ohm source at the adapter tip into the 50 ohm port 2.
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cal import Cal  # noqa: E402


def main(data, names):
    cal = Cal(data)
    out = Path(data).parent / "results"
    out.mkdir(exist_ok=True)
    floor = cal.floor_db()
    for name in names:
        f, Z, _, s21 = cal.measure(name)
        loss = -20 * np.log10(np.abs(s21))
        np.savetxt(out / f"{name}.csv", np.column_stack([f, loss, floor, np.abs(Z)]), delimiter=",",
                   header="f_Hz,loss_dB,vna_floor_dB,Z_port1_ohm", comments="", fmt="%.6g")
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(f / 1e6, loss, lw=1.5, label=name)
        ax.plot(f / 1e6, floor, color="0.6", lw=1, label="VNA floor")
        ax.set_xscale("log")
        ax.invert_yaxis()
        ax.set_xlabel("MHz")
        ax.set_ylabel("loss (dB)")
        ax.legend()
        ax.grid(True, which="both", alpha=.3)
        fig.suptitle(f"{name}: transfer loss")
        fig.tight_layout()
        fig.savefig(out / f"{name}.png", dpi=110)
        plt.close(fig)
        print(f"{name}: minimum loss {loss.min():.1f} dB at {f[np.argmin(loss)] / 1e6:.2f} MHz")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
