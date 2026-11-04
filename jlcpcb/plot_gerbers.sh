#!/bin/sh
# Plot the JLCPCB Gerber and drill files from the KiCad board into Gerber_V1R1/.
# Same layer set, origin (absolute) and file naming as the upstream Gerber_IPC356_BOM_camset,
# so the placement file from generate.py stays in the same coordinate system.
set -e
cd "$(dirname "$0")/.."
OUT=Gerber_V1R1
rm -rf "$OUT" && mkdir -p "$OUT"
kicad-cli pcb export gerbers -o "$OUT" --check-zones \
  -l F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
  5uH_LISN.kicad_pcb
kicad-cli pcb export drill -o "$OUT/" --format excellon --drill-origin absolute \
  --excellon-units mm --excellon-separate-th 5uH_LISN.kicad_pcb
