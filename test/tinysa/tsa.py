#!/usr/bin/env python3
"""Conducted-emission sweep through this LISN with a tinySA Ultra, plotted against IEC 61000-6-3.

usage: tsa.py NAME [--line plus|minus|none] [--sweeps N] [--atten DB] [--lna on|off] [--out DIR]
               [--start HZ] [--stop HZ] [--step HZ] [--rbw KHZ] [--no-limits] [--port DEV]

The sweep itself is tinysa-ultra/tsa.py in the lab-tools repository (github.com/ramb0t/lab-tools);
tsa.py --help lists its options. This wrapper supplies what belongs to this LISN: --line plus, the
VDF measured in test/vna, and test/tinysa/data as the output folder. Options given on the command
line win. Set LAB_TOOLS to the lab-tools checkout if it is not beside this repository.
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VDF_DIR = HERE.parent / "vna" / "data" / "2026-11-18" / "results"
_TOOL = Path(os.environ.get("LAB_TOOLS") or HERE.parents[2] / "lab-tools").expanduser() / "tinysa-ultra" / "tsa.py"
if not _TOOL.is_file():
    raise SystemExit(f"{_TOOL} not found: clone github.com/ramb0t/lab-tools beside this repository, or set LAB_TOOLS to it")
_spec = importlib.util.spec_from_file_location("lab_tools_tsa", _TOOL)
_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tool)
TinySA, find_port, RBW_KHZ = _tool.TinySA, _tool.find_port, _tool.RBW_KHZ  # used by levelcheck.py


def main():
    # defaults go first, so anything on the command line overrides them
    sys.argv[1:1] = ["--line", "plus", "--vdf-dir", str(VDF_DIR), "--out", str(HERE / "data")]
    _tool.main()


if __name__ == "__main__":
    main()
