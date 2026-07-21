"""Render every generated SVG to PNG with cairosvg.

Resumable: existing PNGs are skipped. Render failures are recorded in
data/renders/_failures.json so they show up in the analysis as missing cells
rather than silently disappearing.

Usage:
    uv run python _extras/pelicanmaxxing/render.py
"""

import json

import cairosvg

from config import GENERATIONS_DIR, RENDER_WIDTH, RENDERS_DIR


def render_svg(svg: str, out_path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        bytestring=svg.encode(),
        write_to=str(out_path),
        output_width=RENDER_WIDTH,
        background_color="white",
    )


def main() -> None:
    failures = []
    rendered = skipped = 0
    for gen_path in sorted(GENERATIONS_DIR.glob("*/*.json")):
        record = json.loads(gen_path.read_text())
        out_path = RENDERS_DIR / gen_path.parent.name / f"{gen_path.stem}.png"
        if out_path.exists():
            skipped += 1
            continue
        if not record["svg"]:
            failures.append({"file": str(gen_path), "error": "no svg in response"})
            continue
        try:
            render_svg(record["svg"], out_path)
            rendered += 1
        except Exception as e:
            failures.append({"file": str(gen_path), "error": str(e)})

    RENDERS_DIR.mkdir(parents=True, exist_ok=True)
    (RENDERS_DIR / "_failures.json").write_text(json.dumps(failures, indent=2))
    print(f"rendered {rendered}, skipped {skipped} existing, {len(failures)} failures")


if __name__ == "__main__":
    main()
