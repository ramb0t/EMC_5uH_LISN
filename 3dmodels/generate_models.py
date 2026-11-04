"""Simplified 3D models for LISN parts with no KiCad library model, from datasheet dimensions.

Run: python3 3dmodels/generate_models.py   (writes the .step files next to this script)
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from mkstep import write, box, ngon
out = sys.argv[1] if len(sys.argv) > 1 else __file__.rsplit("/", 1)[0]
FERRITE, TIN, CERAMIC = (0.20, 0.20, 0.22), (0.82, 0.82, 0.80), (0.92, 0.90, 0.85)

# Coilcraft 1008PS (Doc 219): A 3.81 (terminal axis, model Y) x B 3.78 x C 2.74 mm max; terminals at the A ends
write(f"{out}/L_Coilcraft_1008PS.step", "L_Coilcraft_1008PS", [
    (box(-1.89, 1.89, -1.905, 1.905), 0.10, 2.74, FERRITE),
    (box(-1.05, 1.05, 1.395, 1.93), 0.0, 0.60, TIN),
    (box(-1.05, 1.05, -1.93, -1.395), 0.0, 0.60, TIN),
])
# TDK S30-A75X / S30-A400X SMD GDT: 4.5 x 3.2 x 2.7 mm, 0.5 mm tin end caps on the short ends (model X)
write(f"{out}/GDT_TDK_S30-A_1812.step", "GDT_TDK_S30-A_1812", [
    (box(-1.75, 1.75, -1.45, 1.45), 0.15, 2.55, CERAMIC),
    (box(1.75, 2.25, -1.6, 1.6), 0.0, 2.7, TIN),
    (box(-2.25, -1.75, -1.6, 1.6), 0.0, 2.7, TIN),
])

import math
def tube(ro, ri, z0, z1, rgb, n=32):
    """Annulus as n convex sectors (mkstep only does convex prisms)."""
    out = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p = [(ri * math.cos(a0), ri * math.sin(a0)), (ro * math.cos(a0), ro * math.sin(a0)),
             (ro * math.cos(a1), ro * math.sin(a1)), (ri * math.cos(a1), ri * math.sin(a1))]
        out.append((p, z0, z1, rgb))
    return out
NICKEL = (0.75, 0.75, 0.72)
# Keystone 575-8 swage-mount banana jack (catalog p.119): flange 7.9 dia x 2.36 on the board top,
# shank 5.2 OD x 8.9 below the flange (through a 1.6 mm board), bore 4.2 through
write(f"{out}/Banana_Keystone_575-8.step", "Banana_Keystone_575-8",
      tube(7.9 / 2, 4.2 / 2, 0.0, 2.36, NICKEL) + tube(5.2 / 2, 4.2 / 2, -8.9, 0.0, NICKEL))

GOLD, PTFE = (0.86, 0.72, 0.33), (0.95, 0.95, 0.95)
# TE 5-1814832-2 vertical SMA jack (drawing C-1814832 rev C): body sq 6.40, 13.50 overall incl. 4.00 tail,
# 7.80 mating face to body, centre pin dia 1.27, 4 ground legs sq 0.95 at 5.08 pitch. Barrel 1/4-36 thread.
sma = [(box(-3.2, 3.2, -3.2, 3.2), 0.0, 1.7, GOLD)]
sma += tube(6.35 / 2, 4.6 / 2, 1.7, 9.5, GOLD)
sma += tube(4.1 / 2, 1.27 / 2, 1.7, 9.0, PTFE)
sma += [(ngon(0, 0, 1.27 / 2, 16), -4.0, 8.0, GOLD)]
for x in (-2.54, 2.54):
    for y in (-2.54, 2.54):
        sma.append((box(x - 0.475, x + 0.475, y - 0.475, y + 0.475), -4.0, 0.0, GOLD))
write(f"{out}/SMA_TE_5-1814832-2_Vertical.step", "SMA_TE_5-1814832-2_Vertical", sma)
