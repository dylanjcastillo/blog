"""Blind feature-inventory pass: a cheap VLM describes each rendered PNG.

The extractor never sees the original prompt, so `animal` / `activity` double
as a blind identifiability measure. Resumable: existing outputs are skipped.

Usage:
    uv run python _extras/pelicanmaxxing/extract.py
"""

import asyncio
import json

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from config import EXTRACTOR_MODEL, FEATURES_DIR, MAX_CONCURRENCY, RENDERS_DIR
from vision import make_client, vision_json_call

INSTRUCTIONS = """\
Look at this image and answer with a single JSON object, no markdown fences, \
with exactly these keys:

- "animal": the main animal depicted, one or two words, lowercase (null if \
no animal)
- "vehicle": the vehicle or conveyance depicted, one or two words, lowercase \
(null if none)
- "facing": which way the main subject faces: "left", "right", or "ambiguous"
- "elements": every other distinct element visible in the scene, as a list of \
short lowercase singular nouns (e.g. ["sun", "cloud", "road", "tree", \
"grass", "mountain"]). Do not include the animal or the vehicle. Use [] if \
there is nothing else.

Answer only with the JSON object."""


async def extract_one(client, sem: asyncio.Semaphore, png_path) -> None:
    out_path = FEATURES_DIR / png_path.parent.name / f"{png_path.stem}.json"
    if out_path.exists():
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        features = await vision_json_call(
            client,
            EXTRACTOR_MODEL,
            INSTRUCTIONS,
            png_path,
            metadata={"stage": "extract", "image": f"{png_path.parent.name}/{png_path.stem}"},
        )
    if features is None:
        tqdm.write(f"FAILED  {png_path.parent.name}/{png_path.stem}")
        return
    out_path.write_text(json.dumps(features, indent=2))


async def main() -> None:
    client = make_client()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    pngs = sorted(RENDERS_DIR.glob("*/*.png"))
    print(f"{len(pngs)} images to extract with {EXTRACTOR_MODEL}")
    await tqdm_asyncio.gather(*(extract_one(client, sem, p) for p in pngs), desc="extract")


if __name__ == "__main__":
    asyncio.run(main())
