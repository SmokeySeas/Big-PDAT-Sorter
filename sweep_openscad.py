# AI_GENERATED: GPT-5.2 Thinking - Feb 26, 2026
# GITHUB_REPO: reflexia-openscad-pipeline (example)
# FOLDER_PATH: /openscad_automation/
# FILENAME: sweep_openscad.py
# DESCRIPTION: Run parameter sweeps against an OpenSCAD model and export STL + PNG previews with structured logging.
# CREATE_FOLDER: true
# VERSION: 0.1.0
# DEPENDENCIES: python>=3.10, openscad (CLI), json, pathlib, subprocess, hashlib, datetime
# LICENSE: MIT
# AUTHOR_REQUEST: Practical automation scripting starter for OpenSCAD param sweeps.
# Official code starts here...

from __future__ import annotations

import json
import hashlib
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Variant:
    plate_x: int
    plate_y: int
    plate_z: int
    hole_d: float
    hole_edge: int
    rib_on: bool
    rib_h: int
    rib_t: int


def stable_id(v: Variant) -> str:
    """Stable short ID for filenames."""
    payload = json.dumps(asdict(v), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:10]


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )


def export_variant(
    openscad_exe: str,
    model_path: Path,
    out_dir: Path,
    v: Variant,
    render_png: bool = True,
) -> dict:
    vid = stable_id(v)
    ts = datetime.now(timezone.utc).isoformat()

    stl_path = out_dir / f"part_{vid}.stl"
    png_path = out_dir / f"part_{vid}.png"
    meta_path = out_dir / f"part_{vid}.json"

    # OpenSCAD CLI uses -D "var=value" for overrides
    defines = [
        f"plate_x={v.plate_x}",
        f"plate_y={v.plate_y}",
        f"plate_z={v.plate_z}",
        f"hole_d={v.hole_d}",
        f"hole_edge={v.hole_edge}",
        f"rib_on={'true' if v.rib_on else 'false'}",
        f"rib_h={v.rib_h}",
        f"rib_t={v.rib_t}",
    ]

    define_flags: list[str] = []
    for d in defines:
        define_flags += ["-D", d]

    # Export STL
    cmd_stl = [openscad_exe, *define_flags, "-o", str(stl_path), str(model_path)]
    run(cmd_stl)

    # Optional PNG preview (quick visual diff)
    if render_png:
        # --imgsize requires recent OpenSCAD. If your version is older, remove it.
        cmd_png = [
            openscad_exe,
            *define_flags,
            "--imgsize=1200,800",
            "--colorscheme=Tomorrow",
            "-o",
            str(png_path),
            str(model_path),
        ]
        run(cmd_png)

    record = {
        "id": vid,
        "timestamp_utc": ts,
        "variant": asdict(v),
        "outputs": {
            "stl": str(stl_path),
            "png": str(png_path) if render_png else None,
            "meta": str(meta_path),
        },
    }

    meta_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def variant_generator() -> Iterable[Variant]:
    # Start small. You can expand the sweep later.
    # Think: "one knob at a time" then combine.
    base = dict(
        plate_x=80,
        plate_y=50,
        plate_z=5,
        hole_edge=8,
        rib_h=10,
        rib_t=3,
    )

    for hole_d in [4.0, 5.0, 6.0]:
        for rib_on in [False, True]:
            for plate_z in [4, 5, 6]:
                yield Variant(
                    plate_x=base["plate_x"],
                    plate_y=base["plate_y"],
                    plate_z=plate_z,
                    hole_d=hole_d,
                    hole_edge=base["hole_edge"],
                    rib_on=rib_on,
                    rib_h=base["rib_h"],
                    rib_t=base["rib_t"],
                )


def main() -> None:
    openscad_exe = "openscad"
    model_path = Path("test_model.scad").resolve()
    out_dir = Path("out").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "run_log.jsonl"

    records = []
    for v in variant_generator():
        rec = export_variant(openscad_exe, model_path, out_dir, v, render_png=True)
        records.append(rec)
        log_path.open("a", encoding="utf-8").write(json.dumps(rec) + "\n")
        print(f"Exported {rec['id']} -> {rec['outputs']['stl']}")

    print(f"\nDone. Wrote {len(records)} variants to: {out_dir}")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()