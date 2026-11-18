#!/usr/bin/env python3
"""Take one raw (uncalibrated) S11/S21 sweep from a LiteVNA / NanoVNA V2 and save it as .npz.

usage: lvna.py OUT.npz [--avg N] [--port /dev/ttyACMx]
Speaks the NanoVNA V2 binary protocol over USB serial. Sweeps 100 kHz-110 MHz in three
linear segments (10 kHz, 100 kHz and 1 MHz steps). The file holds f, s11, s21 (raw ratios
to the forward wave) and fwd. Calibrate with cal.py; never connect the VNA to a powered LISN.
"""
import argparse
import struct
import time
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports

SEGMENTS = [(100e3, 10e3, 91), (1e6, 100e3, 91), (10e6, 1e6, 101)]  # start Hz, step Hz, points


def find_port():
    for p in serial.tools.list_ports.comports():
        if "LiteVNA" in (p.product or "") or "NanoVNA" in (p.product or ""):
            return p.device
    raise SystemExit("no LiteVNA/NanoVNA found; pass --port")


class VNA:
    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=3)
        self.s.write(bytes(8))  # NOPs resync the protocol
        time.sleep(0.1)
        self.s.reset_input_buffer()
        self.s.write(b"\x0d")  # INDICATE
        if self.s.read(1) != b"2":
            raise SystemExit(f"{port}: not a NanoVNA V2 protocol device")

    def _w(self, fmt, op, addr, val):
        self.s.write(struct.pack(fmt, op, addr, int(val)))

    def segment(self, start, step, n, avg):
        self._w("<BBQ", 0x23, 0x00, start)  # sweepStartHz
        self._w("<BBQ", 0x23, 0x10, step)   # sweepStepHz
        self._w("<BBH", 0x21, 0x20, n)      # sweepPoints
        self._w("<BBH", 0x21, 0x22, avg)    # valuesPerFrequency
        self._w("<BBB", 0x20, 0x30, 0)      # clear FIFO
        total, got = n * avg, b""
        while len(got) < total * 32:
            k = min(255, total - len(got) // 32)
            self.s.write(bytes([0x18, 0x30, k]))  # READFIFO
            chunk = self.s.read(k * 32)
            if len(chunk) != k * 32:
                raise SystemExit(f"short FIFO read {len(chunk)}/{k * 32}")
            got += chunk
        acc, cnt = np.zeros((n, 3), complex), np.zeros(n)
        for i in range(total):
            fr, fi, r0r, r0i, r1r, r1i, idx = struct.unpack_from("<6iH", got, 32 * i)
            acc[idx] += (complex(fr, fi), complex(r0r, r0i), complex(r1r, r1i))
            cnt[idx] += 1
        acc /= cnt[:, None]
        return acc[:, 1] / acc[:, 0], acc[:, 2] / acc[:, 0], np.abs(acc[:, 0])

    def sweep(self, avg):
        parts = [self.segment(s, st, n, avg) for s, st, n in SEGMENTS]
        f = np.concatenate([s + st * np.arange(n) for s, st, n in SEGMENTS])
        return (f, *(np.concatenate(x) for x in zip(*parts)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--avg", type=int, default=16)
    ap.add_argument("--port")
    a = ap.parse_args()
    v = VNA(a.port or find_port())
    v.sweep(1)  # settle
    f, s11, s21, fwd = v.sweep(a.avg)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(a.out, f=f, s11=s11, s21=s21, fwd=fwd)
    print(f"{a.out}: {len(f)} points, {f[0] / 1e6:g}-{f[-1] / 1e6:g} MHz")


if __name__ == "__main__":
    main()
