#!/usr/bin/env python3
"""Generate JLCPCB assembly files from the KiCad project (KiCad 7 or 8+ format).

Reads 5uH_LISN.kicad_sch, 5uH_LISN.kicad_pcb and jlcpcb/parts.csv and writes
jlcpcb/out/:
  jlc_bom.csv     parts assembled by JLCPCB (assembly = jlc)
  jlc_cpl.csv     placement of those parts
  hand_bom.csv    parts soldered by hand (assembly = hand)
  order_bom.csv   the same parts for a distributor BOM import, for 1 and 10 LISNs
  gerbers.zip     the Gerber/drill files from Gerber_V1R1/, zipped for upload

Every reference in the schematic and on the PCB must appear exactly once in
parts.csv, otherwise nothing is written. Output is deterministic.

  python3 jlcpcb/generate.py          write the files
  python3 jlcpcb/generate.py --check  fail if the files in out/ are stale

Only the Python standard library is used.
"""

import csv
import io
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCH = ROOT / "5uH_LISN.kicad_sch"
PCB = ROOT / "5uH_LISN.kicad_pcb"
GERBER_DIR = ROOT / "Gerber_V1R1"  # plotted by jlcpcb/plot_gerbers.sh
PARTS = Path(__file__).resolve().parent / "parts.csv"
OUT = Path(__file__).resolve().parent / "out"

ASSEMBLY = ("jlc", "hand", "dnp")
GERBER_EXT = (".gtl", ".gbl", ".gto", ".gbo", ".gts", ".gbs", ".gtp", ".gbp", ".gm1", ".drl")


def search(pattern, text, what):
    m = re.search(pattern, text)
    if m is None:
        sys.exit(f"cannot parse {what}")
    return m


def natural_key(ref):
    m = search(r"([A-Za-z_]+)(\d*)", ref, f"reference '{ref}'")
    return (m.group(1), int(m.group(2) or 0), ref)


def read_schematic(path):
    """Return {ref: (value, footprint)} from the placed symbols.

    Handles KiCad 7 (two-space indent) and KiCad 8+ (tab indent, no
    symbol_instances section). Library symbols are nested deeper and carry a
    quoted name instead of lib_id, so they are not matched.
    """
    text = path.read_text(encoding="utf-8")
    refs = {}
    for block in re.split(r"\n(?:\t| {2})\(symbol\s+\((?:lib_name|lib_id) ", text)[1:]:
        ref = search(r'\(property "Reference" "([^"]+)"', block, "symbol reference").group(1)
        if ref.startswith("#"):
            continue
        value = search(r'\(property "Value" "([^"]*)"', block, f"{ref} value").group(1)
        value = value or "~"  # KiCad 8+ writes an empty value as "", KiCad 7 as "~"
        footprint = search(r'\(property "Footprint" "([^"]*)"', block, f"{ref} footprint").group(1)
        refs[ref] = (value, footprint)
    if not refs:
        sys.exit(f"{path.name}: no placed symbols found")
    return refs


def read_pcb(path):
    """Return {ref: dict(layer, x, y, rot, attrs, footprint)}."""
    text = path.read_text(encoding="utf-8")
    fps = {}
    # KiCad 7: two-space indent, fp_text reference; KiCad 8+: tab indent, property "Reference"
    for block in re.split(r"\n(?:\t| {2})\(footprint ", text)[1:]:
        ref = search(r'\((?:fp_text reference|property "Reference") "([^"]+)"', block,
                     "footprint reference").group(1)
        at = search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", block, f"{ref} position")
        attr = re.search(r"\(attr ([^)]*)\)", block)
        fps[ref] = {
            "footprint": block.split('"')[1],
            "layer": search(r'\(layer "([^"]+)"\)', block, f"{ref} layer").group(1),
            "x": float(at.group(1)),
            "y": float(at.group(2)),
            "rot": float(at.group(3) or 0),
            "attrs": attr.group(1).split() if attr else [],
        }
    return fps


def read_parts(path):
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["refs"] = row["refs"].split()
    return rows


def validate(sch, pcb, parts):
    errors = []
    seen = {}
    for i, row in enumerate(parts, start=2):
        if row["assembly"] not in ASSEMBLY:
            errors.append(f"parts.csv:{i}: assembly '{row['assembly']}' not in {ASSEMBLY}")
        if row["assembly"] == "jlc" and not re.fullmatch(r"C\d+", row["lcsc"]):
            errors.append(f"parts.csv:{i}: jlc part needs an LCSC number")
        if row["assembly"] != "jlc" and row["lcsc"]:
            errors.append(f"parts.csv:{i}: LCSC number only for assembly = jlc")
        for ref in row["refs"]:
            if ref in seen:
                errors.append(f"parts.csv:{i}: {ref} already listed in line {seen[ref]}")
            seen[ref] = i
            if ref not in sch:
                errors.append(f"parts.csv:{i}: {ref} not in schematic")
            elif sch[ref][0] != row["value"]:
                errors.append(f"parts.csv:{i}: {ref} value '{row['value']}' != schematic '{sch[ref][0]}'")
            if row["assembly"] == "jlc":
                fp = pcb.get(ref)
                if fp is None:
                    errors.append(f"parts.csv:{i}: {ref} is a jlc part but not on the PCB")
                elif "exclude_from_pos_files" in fp["attrs"]:
                    errors.append(f"parts.csv:{i}: {ref} is a jlc part but excluded from position files")
    for ref in sorted(set(sch) | set(pcb), key=natural_key):
        if ref not in seen:
            errors.append(f"{ref} (schematic/PCB) missing in parts.csv")
    for ref in sorted(set(pcb) - set(sch), key=natural_key):
        errors.append(f"{ref} on PCB but not in schematic")
    return errors


def csv_text(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def build_bom(parts, pcb):
    rows = []
    for row in parts:
        if row["assembly"] != "jlc":
            continue
        refs = sorted(row["refs"], key=natural_key)
        footprint = pcb[refs[0]]["footprint"].split(":")[-1]
        rows.append([row["comment"], ",".join(refs), footprint, row["lcsc"]])
    return csv_text(["Comment", "Designator", "Footprint", "LCSC Part #"], rows)


def build_cpl(parts, pcb):
    rows = []
    for row in parts:
        if row["assembly"] != "jlc":
            continue
        for ref in row["refs"]:
            fp = pcb[ref]
            layer = "Bottom" if fp["layer"] == "B.Cu" else "Top"
            rot = (fp["rot"] + float(row["rot_offset"] or 0)) % 360
            # Gerber coordinates: same origin as the PCB file, Y axis pointing up.
            rows.append([ref, f"{fp['x']:.4f}mm", f"{-fp['y']:.4f}mm", layer, f"{rot:g}"])
    rows.sort(key=lambda r: natural_key(r[0]))
    return csv_text(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"], rows)


def build_hand_bom(parts, pcb):
    rows = []
    for row in parts:
        if row["assembly"] != "hand":
            continue
        refs = sorted(row["refs"], key=natural_key)
        sides = {pcb[r]["layer"] for r in refs if r in pcb}
        side = {"B.Cu": "bottom", "F.Cu": "top"}.get(sides.pop(), "?") if len(sides) == 1 else "-"
        rows.append([len(refs), " ".join(refs), row["comment"], row["mfr"], row["mpn"], side, row["note"]])
    return csv_text(["Qty", "Designator", "Description", "Manufacturer", "MPN", "Side", "Note"], rows)


def ref_ranges(refs):
    """['L1', 'L2', 'L3', 'L7'] -> 'L1-L3,L7'"""
    out, run = [], []
    for ref in sorted(refs, key=natural_key):
        prefix, num, _ = natural_key(ref)
        if run and (prefix, num) == (run[-1][0], run[-1][1] + 1):
            run.append((prefix, num, ref))
            continue
        if run:
            out.append(run[0][2] if len(run) == 1 else f"{run[0][2]}-{run[-1][2]}")
        run = [(prefix, num, ref)]
    if run:
        out.append(run[0][2] if len(run) == 1 else f"{run[0][2]}-{run[-1][2]}")
    return ",".join(out)


def build_order_bom(parts, batch):
    """Hand parts in the column names of Mouser's BOM import: Quantity 1 = one LISN, Quantity 2 = a batch."""
    rows = []
    for row in parts:
        if row["assembly"] != "hand":
            continue
        qty = len(row["refs"])
        rows.append([row["mpn"], row["mfr"], qty, qty * batch, f"LISN {ref_ranges(row['refs'])}", row["comment"]])
    header = ["Manufacturer Part Number", "Manufacturer Name", "Quantity 1", "Quantity 2",
              "Customer Part Number", "Description"]
    return csv_text(header, rows)


def build_gerber_zip():
    files = sorted(p for p in GERBER_DIR.iterdir() if p.suffix.lower() in GERBER_EXT)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info = zipfile.ZipInfo(p.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, p.read_bytes())
    return buf.getvalue()


def zip_members(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: z.read(i) for i in z.infolist()}


def same(name, old, new):
    """Compare zips by member contents: zlib output differs between builds."""
    if name.endswith(".zip"):
        return zip_members(old) == zip_members(new)
    return old == new


def main(argv):
    check = "--check" in argv
    sch, pcb, parts = read_schematic(SCH), read_pcb(PCB), read_parts(PARTS)
    errors = validate(sch, pcb, parts)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2

    outputs = {
        "jlc_bom.csv": build_bom(parts, pcb).encode(),
        "jlc_cpl.csv": build_cpl(parts, pcb).encode(),
        "hand_bom.csv": build_hand_bom(parts, pcb).encode(),
        "order_bom.csv": build_order_bom(parts, 10).encode(),
        "gerbers.zip": build_gerber_zip(),
    }
    if check:
        stale = [n for n, data in outputs.items() if not (OUT / n).exists() or not same(n, (OUT / n).read_bytes(), data)]
        if stale:
            print("stale: " + ", ".join(stale) + " (run jlcpcb/generate.py)", file=sys.stderr)
            return 1
        print("jlcpcb/out is up to date")
        return 0

    OUT.mkdir(exist_ok=True)
    for name, data in outputs.items():
        (OUT / name).write_bytes(data)
    counts = {a: sum(len(r["refs"]) for r in parts if r["assembly"] == a) for a in ASSEMBLY}
    print(f"jlc {counts['jlc']} parts / {sum(r['assembly'] == 'jlc' for r in parts)} LCSC numbers, "
          f"hand {counts['hand']}, dnp {counts['dnp']} -> {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
