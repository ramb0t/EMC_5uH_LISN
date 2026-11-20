#!/usr/bin/env python3
"""Capture channels on a Rigol DHO800/900 over LAN and plot the waveform and its spectrum.

usage: dho.py NAME [--chan 1 2 ...] [--label L1 L2 ...] [--mode short|long|both] [--host IP] [--out DIR] [--f0 HZ]

short: 2 us/div, 100k points, for ripple and edge ringing.
long:  100 us/div, 1M points (about 1.6 ms), FFT'd here: about 1 kHz ENBW, Hann window, dBuV RMS per bin.
Only the timebase and memory depth are changed; vertical settings stay as the user set them.
Writes NAME_short / NAME_long .npz and .png; all channels in one acquisition.
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pyvisa

TIMEBASE = {"short": (2e-6, "100k"), "long": (100e-6, "1M")}  # record = MDEP points
CHUNK = 250_000  # points per :WAV:DATA? read


class DHO:
    def __init__(self, host):
        self.s = pyvisa.ResourceManager("@py").open_resource(f"TCPIP0::{host}::INSTR", timeout=30000)
        self.s.chunk_size = 4 * 1024 * 1024

    def q(self, c):
        return self.s.query(c).strip()

    def w(self, c):
        self.s.write(c)

    def single(self, timebase, mdep):
        self.w(":RUN")
        self.w(":CHAN1:DISP 1")  # with CH1 off, RAW reads of other channels return junk (fw 00.01.05)
        self.w(f":TIM:SCAL {timebase:g}")
        self.w(f":ACQ:MDEP {mdep}")
        self.w(":SING")
        time.sleep(0.5)
        for _ in range(100):
            if self.q(":TRIG:STAT?") == "STOP":
                return
            time.sleep(0.1)
        raise SystemExit("no trigger in 10 s; check the trigger source and level")

    def read(self, chan):
        self.w(f":WAV:SOUR CHAN{chan}")
        self.w(":WAV:MODE RAW")
        self.w(":WAV:FORM WORD")
        # the preamble's point count follows the last STAR/STOP window, which persists between
        # clients, so set the full window first and take the count from the memory depth
        n = int(float(self.q(":ACQ:MDEP?")))
        self.w(f":WAV:POIN {n}")
        self.w(":WAV:STAR 1")
        self.w(f":WAV:STOP {n}")
        pre = [float(x) for x in self.q(":WAV:PRE?").split(",")]
        xinc, xorig, yinc, yorig, yref = pre[4], pre[5], pre[7], pre[8], pre[9]
        raw = []
        for a in range(1, n + 1, CHUNK):
            self.w(f":WAV:STAR {a}")
            self.w(f":WAV:STOP {min(a + CHUNK - 1, n)}")
            raw.append(np.array(self.s.query_binary_values(":WAV:DATA?", datatype="H", container=np.array)))
        d = np.concatenate(raw).astype(float)
        if len(d) != n:
            raise SystemExit(f"CH{chan}: read {len(d)} of {n} points")
        clip = max(np.mean(d == d.max()), np.mean(d == d.min()))
        if clip > 1e-3:
            print(f"WARNING CH{chan}: {clip:.1%} of samples at the ADC limit -- clipped, change scale or offset")
        v = (d - yref - yorig) * yinc
        t = xorig + np.arange(len(v)) * xinc
        # cross-check against the screen record, which the scope always gets right
        self.w(":WAV:MODE NORM")
        pre = [float(x) for x in self.q(":WAV:PRE?").split(",")]
        s = np.array(self.s.query_binary_values(":WAV:DATA?", datatype="H", container=np.array), float)
        s = (s - pre[9] - pre[8]) * pre[7]
        # the screen record is a min/max envelope at long timebases, so compare peak-to-peak, not RMS
        err = 20 * np.log10(max(np.ptp(v), 1e-9) / max(np.ptp(s), 1e-9))
        if abs(err) > 3:
            raise SystemExit(f"CH{chan}: RAW record pk-pk is {err:+.1f} dB off the screen record; data not trusted")
        return t, v


def spectrum(t, v):
    fs = 1 / (t[1] - t[0])
    w = np.hanning(len(v))
    X = np.fft.rfft((v - v.mean()) * w)
    f = np.fft.rfftfreq(len(v), 1 / fs)
    vrms = np.abs(X) * 2 / w.sum() / np.sqrt(2)
    return f, 20 * np.log10(np.maximum(vrms, 1e-12) / 1e-6), 1.5 * fs / len(v)


COLORS = ["#2a78d6", "#eb6834", "#1a9e77", "#7b5ea7"]


def style(ax, info):
    ax.grid(True, which="both", color="#e4e3df")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.text(0.99, 0.02, info, transform=ax.transAxes, ha="right", fontsize=8, color="#52514e")


def plot_short(path, name, caps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(len(caps), 1, figsize=(10, 2.2 + 2.3 * len(caps)), sharex=True, squeeze=False)
    lines = []
    for ax, (lab, t, v, info), c in zip(axs[:, 0], caps, COLORS):
        ax.plot(t * 1e6, v * 1e3, color=c, lw=0.8)
        ax.set_ylabel("mV")
        ax.set_title(f"{lab}: {np.ptp(v) * 1e3:.1f} mV pk-pk, {v.std() * 1e3:.2f} mV RMS", fontsize=10, loc="left")
        style(ax, info)
        lines.append(f"{lab}: {np.ptp(v) * 1e3:.1f} mV pk-pk, {v.std() * 1e3:.2f} mV RMS")
    axs[-1, 0].set_xlabel("Time (µs)")
    fig.suptitle(name, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    return lines


def plot_long(path, name, caps, f0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5.5))
    if f0:
        for h in range(1, int(30e6 / f0) + 1):
            ax.axvline(h * f0 / 1e6, color="#e4e3df", lw=0.6, zorder=0)
    lines = []
    for (lab, t, v, info), c in zip(caps, COLORS):
        f, db, enbw = spectrum(t, v)
        k = (f >= 50e3) & (f <= 30e6)
        ax.plot(f[k] / 1e6, db[k], color=c, lw=0.7, label=lab)
        peaks = []
        for i in np.argsort(np.where(k, db, -np.inf))[::-1]:
            if all(abs(f[i] - f[j]) > 20e3 for j in peaks):
                peaks.append(i)
            if len(peaks) == 6:
                break
        lines.append(f"{lab} peaks: " + ", ".join(f"{f[i] / 1e6:.3f} MHz {db[i]:.1f}" for i in peaks))
    ax.set_xscale("log")
    ax.set_xlim(0.05, 30)
    ax.set_xticks([0.1, 0.2, 0.4, 1, 2, 5, 10, 30])
    ax.set_xticklabels(["0.1", "0.2", "0.4", "1", "2", "5", "10", "30"])
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel(f"dBµV RMS per bin (ENBW {enbw / 1e3:.1f} kHz)")
    ax.set_title(f"{name}: spectrum, {(t[-1] - t[0]) * 1e3:.1f} ms record", fontweight="bold")
    ax.legend(loc="upper right", frameon=False)
    style(ax, caps[0][3].split(",")[-2] + "," + caps[0][3].split(",")[-1])
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--chan", type=int, nargs="+", default=[1])
    ap.add_argument("--label", nargs="+", help="one per channel")
    ap.add_argument("--mode", choices=("short", "long", "both"), default="both")
    ap.add_argument("--host", default="192.168.7.51")
    ap.add_argument("--out", default=".")
    ap.add_argument("--f0", type=float, default=0, help="mark harmonics of this frequency")
    a = ap.parse_args()
    labels = a.label or [f"CH{c}" for c in a.chan]
    d = DHO(a.host)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for mode in (("short", "long") if a.mode == "both" else (a.mode,)):
        d.single(*TIMEBASE[mode])
        caps = []
        for ch, lab in zip(a.chan, labels):
            t, v = d.read(ch)
            c = f":CHAN{ch}"
            info = (f"CH{ch} {d.q(c + ':COUP?')} {float(d.q(c + ':SCAL?')) * 1e3:g} mV/div, "
                    f"BWL {d.q(c + ':BWL?')}, {1 / (t[1] - t[0]) / 1e6:g} MSa/s, {len(v)} pts")
            caps.append((lab, t, v, info))
        d.w(":RUN")
        stem = f"{a.name}_{mode}"
        np.savez(out / f"{stem}.npz", **{f"t{i}": c[1] for i, c in enumerate(caps)},
                 **{f"v{i}": c[2] for i, c in enumerate(caps)}, labels=labels, info=[c[3] for c in caps])
        res = plot_short(out / f"{stem}.png", stem, caps) if mode == "short" else plot_long(out / f"{stem}.png", stem, caps, a.f0)
        print("\n".join(res))
        print(out / f"{stem}.png")


if __name__ == "__main__":
    main()
