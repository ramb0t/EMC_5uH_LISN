# Conducted emissions with a tinySA Ultra

These scripts sweep the LISN's HF ports with a tinySA Ultra over USB and plot the result in dBµV at the DUT jack against the IEC 61000-6-3 DC power port limits (Table 5, clause 5.1). As of 2026-11-18 the measurement chain is verified, but no representative BSI measurement exists yet.

## What is verified (2026-11-18)

| Check | Result | File |
|---|---|---|
| tinySA floor, input terminated | −10 to −20 dBµV from 1 to 30 MHz | `floor_tinysa_terminated` |
| Level check: CAL comb through the LISN vs the VNA VDF | mean +0.3 dB, worst +1.3 dB over 14 harmonics, 3–29 MHz | `levelcheck.csv` |
| Setup floor with the 48 V bench supply | about 56 dB below the AV limit above 2 MHz, on both lines | `floor_supply_48V_hf_*` |

The `v8.0.0-nonrep_*` files are a modified v8.0.0 BSI on a non-ideal setup. They are a dry run of the method, not a result.

Below 2 MHz the 5 µH LISN reads low against the 50 µH V-AN the limits assume, by up to about 17 dB at 150 kHz. The plots shade that region.

## Running a sweep

`python3 tsa.py NAME --line plus|minus` sweeps 150 kHz–30 MHz at 10 kHz RBW in 5 kHz steps, takes a max hold of 3 sweeps (`--sweeps`), adds that line's VDF from `../vna`, and writes `data/NAME.csv` and `.png`. `--line none` gives the raw reading, for the instrument floor. The script sets RBW, 10 dB attenuation (`--atten`) and spur removal, but saves nothing to the tinySA.

`python3 levelcheck.py direct`, then `lisn`, then `analyse` repeats the level check. The CAL output is switched to 1 MHz for the captures. Wire `direct` as CAL → cable → RF. Wire `lisn` as CAL → the same cable → adapter → DUT+, and HF+ → RF, with the LISN unpowered and the supply jacks shorted.

## Safety

The DUT jacks carry the supply voltage relative to the case. Never fit plain 50 Ω terminators to both DUT jacks while powered: at 48 V that puts about 11 W into each. Leave DUT− open, or use a DC block. One terminator on DUT+ is only safe while the supply floats relative to the case, and the tinySA's USB connection grounds the case to the PC.

Power the BSI up and down with both HF ports terminated, then connect the tinySA. Repeating a sweep with `--atten 20` is the overload check: real emissions don't move, mixer products do.
