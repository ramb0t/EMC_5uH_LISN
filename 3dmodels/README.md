# 3D models

Simplified STEP models for the parts with no KiCad library model: the right envelope and terminal positions for fit checks, not vendor detail. They are generated here, so they fall under the repository's MIT licence. The vendor models (Würth, TE, Keystone, Coilcraft, TDK) can't be redistributed in this repository.

Regenerate them with `python3 3dmodels/generate_models.py` (Python standard library only; `mkstep.py` writes the STEP files). The footprints reference them as `${KIPRJMOD}/3dmodels/…`.

| File | Part | Dimensions from |
|---|---|---|
| `L_Coilcraft_1008PS.step` | Coilcraft 1008PS (L6, L12) | Coilcraft Doc 219, 3.81 × 3.78 × 2.74 mm max |
| `GDT_TDK_S30-A_1812.step` | TDK S30-A75X / S30-A400X (GD1, GD2) | TDK datasheet, 4.5 × 3.2 × 2.7 mm, 0.5 mm end caps |
| `Banana_Keystone_575-8.step` | Keystone 575-8 (J3–J8) | Keystone catalog p.119, 7.9 mm flange, 5.2 mm shank, L 8.9 mm |
| `SMA_TE_5-1814832-2_Vertical.step` | TE 5-1814832-2 (J1, J2) | TE drawing C-1814832 rev C, 6.40 mm body, 13.50 mm overall |
