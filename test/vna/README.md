# LISN characterisation with a LiteVNA

These scripts measure the LISN's impedance, voltage division factor (VDF), supply isolation and line-to-line crosstalk with a LiteVNA 64 (any NanoVNA V2-protocol VNA should work). The 2026-11-18 run on the V1 R1 board passes CISPR 25 on both lines: the VDF is 10.1 dB flat, so the spectrum analyser needs only a −10.1 dB external-gain setting.

## Results, 2026-11-18 (V1 R1, after replacing L6/L12)

| Test | Result |
|---|---|
| Impedance, DUT+ and DUT− | Within ±4 % of nominal to 30 MHz, −15 % at 108 MHz (limit ±20 %) |
| VDF | 10.1 ± 0.1 dB from 0.5 to 108 MHz, 10.5 dB at 150 kHz |
| Isolation, SUPPLY+ → HF+ | 48 dB at 100 kHz, 51 dB at 150 kHz, 68–81 dB above 1 MHz |
| Crosstalk, DUT+ → HF− | 70 dB worst (450 kHz), at the VNA floor from 1 to 10 MHz |
| DUT+ vs DUT− | Within 4 % and 0.15 dB |

The graphs are in `data/2026-11-18/results/`; start with `report_1_impedance.png`.

The first sweep read 20–35 % low at 1–5 MHz, with the VDF 3–4 dB high. In circuit, L6 and L12 measured 36 µH at 1 kHz instead of 1 mH: they had been heat-damaged when hand-soldered (a fresh part measured 1 mH). The `before_fix_*` captures record this. Preheat the board before soldering them, because their GND pad sinks heat into the plane.

Every capture shows a 0.3 dB step at about 420 kHz. Since it is identical across all captures, it is probably the LiteVNA switching ranges, not the LISN.

## Using it with the tinySA Ultra

Set LEVEL → EXT GAIN to −10.1 dB and the unit to dBµV. The remaining error is under 0.6 dB (`report_6_offset_error.png`). Use a 10 kHz resolution bandwidth below 30 MHz and 100 kHz above. The tinySA only has a peak detector, which reads at or above quasi-peak, so the error is on the safe side.

## Re-running

Never connect the VNA to a powered LISN. Keep the cables in the same place from calibration to the last capture. Each capture is `python3 lvna.py DIR/NAME.npz` (it finds the VNA by USB name; `--port` overrides).

1. **Calibrate at the cable ends.** Capture `short`, `open` and `load` on the port-1 cable, with a 50 Ω terminator on the port-2 cable, then `thru` with the two cables joined.
2. **Compensate the SMA-to-banana adapter.** On port 1, capture `fx_open` with the adapter in air and `fx_short` with its tip shorted to its ground right at the tip.
3. **Measure each line.** Short SUPPLY+ and SUPPLY− to the case. Port 1 goes to a DUT jack, port 2 to that line's HF SMA, and 50 Ω on the other HF SMA. Capture `dut_plus` and `dut_minus`.
4. **Isolation.** Remove the supply short. Port 1 on SUPPLY+, port 2 on HF+, DUT+ open. Capture `isolation_supply_plus`.
5. **Crosstalk.** Refit the supply short. Port 1 on DUT+, port 2 on HF−, 50 Ω on HF+. Capture `crosstalk_dut_plus_to_hf_minus`.
6. **Analyse.** `python3 lisn_line.py DIR dut_plus dut_minus`, `python3 transfer.py DIR isolation_supply_plus crosstalk_dut_plus_to_hf_minus`, then `python3 report.py DIR`. Results go to `DIR/../results/`.

`cal.py` holds the calibration: short-open-load at port 1 with ideal standards, one-path enhanced-response transmission with isolation from the load capture, and open/short compensation for the adapter. The adapter here measured about 6 nH.
