#!/usr/bin/env python3
"""Summary performance graphs for a characterisation run.

usage: report.py DATA_DIR   -> DATA_DIR/../results/report_*.png
Needs dut_plus, dut_minus, isolation_supply_plus and crosstalk_dut_plus_to_hf_minus captures;
before_fix_dut_plus/minus are overlaid when present.
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cal import Cal, cispr25_z  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
PLUS, MINUS, NOMINAL, BEFORE, FLOOR = "#2a78d6", "#eb6834", "#0b0b0b", "#a9a8a2", "#c3c2b7"
SA_OFFSET = 10.1  # dB, the flat correction used on the tinySA

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "legend.frameon": False, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
})


def nominal_complex(f):
    w = 2 * np.pi * f
    zl, zc = 1j * w * 5e-6, 1 / (1j * w * 0.1e-6) + 50
    return zl * zc / (zl + zc)


def mhz_axis(ax):
    ax.set_xscale("log")
    ax.set_xlim(0.1, 110)
    ax.set_xticks([0.15, 0.3, 1, 3, 10, 30, 108])
    ax.set_xticklabels(["0.15", "0.3", "1", "3", "10", "30", "108"])
    ax.set_xlabel("Frequency (MHz)")


def label_end(ax, x, y, text, color, dy=0):
    ax.annotate(text, (x, y), xytext=(6, dy), textcoords="offset points", va="center",
                color=INK, fontsize=9, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec=color, lw=1.2))


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(out / f"report_{name}.png", dpi=130)
    plt.close(fig)
    print(out / f"report_{name}.png")


def main(data):
    cal = Cal(data)
    out = Path(data).parent / "results"
    out.mkdir(exist_ok=True)
    have = lambda n: (Path(data) / f"{n}.npz").exists()
    m = {n: cal.measure(n) for n in ("dut_plus", "dut_minus", "before_fix_dut_plus", "before_fix_dut_minus",
                                    "isolation_supply_plus", "crosstalk_dut_plus_to_hf_minus") if have(n)}
    f = cal.f
    F = f / 1e6
    zn = nominal_complex(f)
    lines = [("dut_plus", "DUT+", PLUS), ("dut_minus", "DUT−", MINUS)]
    before = [n for n in ("before_fix_dut_plus", "before_fix_dut_minus") if n in m]

    # 1. impedance magnitude against the CISPR 25 band
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.fill_between(F, 0.8 * abs(zn), 1.2 * abs(zn), color="#ecebe7", lw=0, label="CISPR 25 ±20 %")
    ax.plot(F, abs(zn), "--", color=NOMINAL, lw=1, label="Nominal 5 µH / 0.1 µF / 50 Ω")
    for i, n in enumerate(before):
        ax.plot(F, abs(m[n][1]), ":", color=BEFORE, lw=1.5, label="Before L6/L12 fix" if i == 0 else None)
    for n, lab, c in lines:
        ax.plot(F, abs(m[n][1]), color=c, label=lab)
    label_end(ax, F[-1], abs(m["dut_plus"][1][-1]), "DUT+", PLUS, 8)
    label_end(ax, F[-1], abs(m["dut_minus"][1][-1]), "DUT−", MINUS, -8)
    mhz_axis(ax)
    ax.set_ylim(0, 62)
    ax.set_ylabel("|Z| at DUT jack (Ω)")
    ax.set_title("Impedance stays inside the CISPR 25 band on both lines")
    ax.legend(loc="lower right", bbox_to_anchor=(0.92, 0.02))
    save(fig, out, "1_impedance")

    # 2. deviation from nominal
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhspan(-20, 20, color="#ecebe7", lw=0, label="±20 % tolerance")
    ax.axhline(0, color=NOMINAL, lw=1, ls="--")
    for i, n in enumerate(before):
        ax.plot(F, 100 * (abs(m[n][1]) / abs(zn) - 1), ":", color=BEFORE, lw=1.5,
                label="Before L6/L12 fix" if i == 0 else None)
    for n, lab, c in lines:
        ax.plot(F, 100 * (abs(m[n][1]) / abs(zn) - 1), color=c, label=lab)
    mhz_axis(ax)
    ax.set_ylim(-40, 25)
    ax.set_ylabel("|Z| deviation from nominal (%)")
    ax.set_title("Within 4 % to 30 MHz; −15 % at 108 MHz")
    ax.legend(loc="lower left")
    save(fig, out, "2_deviation")

    # 3. impedance phase
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(F, np.degrees(np.angle(zn)), "--", color=NOMINAL, lw=1, label="Nominal")
    for n, lab, c in lines:
        ax.plot(F, np.degrees(np.angle(m[n][1])), color=c, label=lab)
    mhz_axis(ax)
    ax.set_ylabel("Phase of Z (°)")
    ax.set_title("Impedance phase: inductive below 1 MHz, resistive above")
    ax.legend(loc="upper right")
    save(fig, out, "3_phase")

    # 4. Smith chart of the DUT-port reflection
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), color=INK2, lw=1)
    for r in (0.2, 0.5, 1, 2):  # constant-resistance circles
        ax.plot(r / (1 + r) + np.cos(t) / (1 + r), np.sin(t) / (1 + r), color=GRID, lw=0.8)
    for x in (0.2, 0.5, 1, 2):  # constant-reactance arcs
        for s in (1, -1):
            c = 1 + 1j * s / x
            arc = c + np.exp(1j * t) / x
            arc = arc[abs(arc) <= 1.0001]
            ax.plot(arc.real, arc.imag, ".", ms=0.6, color=GRID)
    ax.axhline(0, color=GRID, lw=0.8)
    g = lambda z: (z - 50) / (z + 50)
    ax.plot(g(zn).real, g(zn).imag, "--", color=NOMINAL, lw=1, label="Nominal")
    for n, lab, c in lines:
        gg = g(m[n][1])
        ax.plot(gg.real, gg.imag, color=c, label=lab)
    for fq in (0.15, 1, 10, 108):
        k = np.argmin(abs(f - fq * 1e6))
        gg = g(m["dut_plus"][1][k])
        ax.plot(gg.real, gg.imag, "o", ms=8, color=PLUS, mec=SURFACE, mew=2)
        ax.annotate(f"{fq:g} MHz", (gg.real, gg.imag), xytext=(8, 6), textcoords="offset points", fontsize=9, color=INK2)
    ax.set_aspect("equal")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("DUT-port reflection (Smith chart, 50 Ω)")
    ax.legend(loc="lower left")
    save(fig, out, "4_smith")

    # 5. voltage division factor
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(SA_OFFSET, color=NOMINAL, lw=1, ls="--", label=f"tinySA offset {SA_OFFSET} dB")
    for i, n in enumerate(before):
        ax.plot(F, 20 * np.log10(m[n][2]), ":", color=BEFORE, lw=1.5, label="Before L6/L12 fix" if i == 0 else None)
    for n, lab, c in lines:
        ax.plot(F, 20 * np.log10(m[n][2]), color=c, label=lab)
    mhz_axis(ax)
    ax.set_ylim(9.5, 17.5)
    ax.set_ylabel("VDF (dB)")
    ax.set_title("Voltage division factor: 10.1 dB flat from 0.5 to 108 MHz")
    ax.legend(loc="upper right")
    save(fig, out, "5_vdf")

    # 6. residual error of the flat tinySA offset
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axhspan(-0.5, 0.5, color="#ecebe7", lw=0, label="±0.5 dB")
    ax.axhline(0, color=NOMINAL, lw=1, ls="--")
    for n, lab, c in lines:
        ax.plot(F, 20 * np.log10(m[n][2]) - SA_OFFSET, color=c, label=lab)
    mhz_axis(ax)
    ax.set_ylim(-1, 1)
    ax.set_ylabel("Reading error (dB)")
    ax.set_title(f"Error left after a flat {SA_OFFSET} dB correction (positive: tinySA reads low)")
    ax.legend(loc="upper right")
    save(fig, out, "6_offset_error")

    # 7. isolation and crosstalk
    if "isolation_supply_plus" in m and "crosstalk_dut_plus_to_hf_minus" in m:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(F, cal.floor_db(), color=FLOOR, lw=1, label="VNA floor")
        for n, lab, c in (("isolation_supply_plus", "Isolation: SUPPLY+ → HF+", PLUS),
                          ("crosstalk_dut_plus_to_hf_minus", "Crosstalk: DUT+ → HF−", MINUS)):
            ax.plot(F, -20 * np.log10(abs(m[n][3])), color=c, label=lab)
        ax.plot(F, 20 * np.log10(m["dut_plus"][2]), "--", color=NOMINAL, lw=1, label="Through path DUT+ → HF+ (VDF)")
        mhz_axis(ax)
        ax.set_ylim(130, 0)
        ax.set_ylabel("Loss (dB, lower on chart = more loss)")
        ax.set_title("Supply isolation ≥ 48 dB, crosstalk ≈ 70 dB or better", pad=52)
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
        save(fig, out, "7_isolation_crosstalk")

    # 8. line matching (two measures, two panels)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    a1.plot(F, 100 * (abs(m["dut_plus"][1]) / abs(m["dut_minus"][1]) - 1), color=PLUS)
    a1.axhline(0, color=NOMINAL, lw=1, ls="--")
    a1.set_ylabel("|Z| DUT+ vs DUT− (%)")
    a1.set_title("DUT+ and DUT− match within 4 % and 0.15 dB")
    a2.plot(F, 20 * np.log10(m["dut_plus"][2] / m["dut_minus"][2]), color=PLUS)
    a2.axhline(0, color=NOMINAL, lw=1, ls="--")
    a2.set_ylabel("VDF DUT+ − DUT− (dB)")
    mhz_axis(a2)
    save(fig, out, "8_line_matching")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
