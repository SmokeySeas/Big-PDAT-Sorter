# AI_GENERATED: GPT-5.2 Thinking - Feb 26, 2026
# GITHUB_REPO: openscad-jig-pipeline (example)
# FOLDER_PATH: /OpenSCAD_Folder/
# FILENAME: make_jig.py
# DESCRIPTION: Generate a jig_data.scad file (studs + underside pads + plate) and export an STL via OpenSCAD CLI.
# CREATE_FOLDER: false
# VERSION: 0.1.0
# DEPENDENCIES: python>=3.10, csv, pathlib, subprocess
# LICENSE: MIT
# AUTHOR_REQUEST: Minimal deterministic jig generator for OpenSCAD automation.
# Official code starts here...

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

OPENS = "openscad"


def load_studs(csv_path: Path):
    studs = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            studs.append((
                float(row["x_mm"]),
                float(row["y_mm"]),
                float(row["diameter_mm"]),
            ))
    return studs


def fmt3(arr):
    return "[" + ",".join(f"[{x:.3f},{y:.3f},{d:.3f}]" for x, y, d in arr) + "]"


def fmt4(arr):
    return "[" + ",".join(f"[{x:.3f},{y:.3f},{d:.3f},{h:.3f}]" for x, y, d, h in arr) + "]"


def write_jig_data_scad(out_path: Path, plate, studs, pads):
    text = (
        f"plate = [{plate[0]:.3f},{plate[1]:.3f},{plate[2]:.3f}];\n"
        f"studs = {fmt3(studs)};\n"
        f"pads  = {fmt4(pads)};\n"
    )
    out_path.write_text(text, encoding="utf-8")


def export_stl(base_scad: Path, stl_out: Path):
    cmd = [OPENS, "-o", str(stl_out), str(base_scad)]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    root = Path(__file__).parent
    input_csv = root / "input" / "studs.csv"
    gen_dir = root / "generated"
    out_dir = root / "out"
    gen_dir.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)

    studs = load_studs(input_csv)

    # --- Plate sizing (simple): bounding box + margin ---
    margin = 15.0
    xs = [s[0] for s in studs]
    ys = [s[1] for s in studs]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    plate_x = (max_x - min_x) + 2 * margin
    plate_y = (max_y - min_y) + 2 * margin
    plate_z = 6.0

    # shift studs so plate starts at (0,0)
    studs_shifted = [(x - min_x + margin, y - min_y + margin, d) for x, y, d in studs]

    # --- 3-point underside pads (triangle) ---
    # Put pads near corners of the bounding area for stability
    pad_d = 16.0
    pad_h = 6.0
    pads = [
        (margin, margin, pad_d, pad_h),
        (plate_x - margin, margin, pad_d, pad_h),
        (plate_x / 2.0, plate_y - margin, pad_d, pad_h),
    ]

    plate = (plate_x, plate_y, plate_z)

    data_path = gen_dir / "jig_data.scad"
    write_jig_data_scad(data_path, plate, studs_shifted, pads)

    base_scad = root / "base_jig_pads.scad"
    stl_out = out_dir / "jig_001.stl"
    export_stl(base_scad, stl_out)

    print(f"Wrote: {stl_out}")
