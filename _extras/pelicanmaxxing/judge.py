"""Quality-judging pass: each judge model scores each render against its prompt.

Kept separate from extract.py so the inventory task can stay blind and the
quality task can see the prompt. Resumable per judge.

Usage:
    uv run python _extras/pelicanmaxxing/judge.py
"""

import asyncio
import json

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from config import GENERATIONS_DIR, JUDGE_MODELS, MAX_CONCURRENCY, RENDERS_DIR, SCORES_DIR, model_slug
from vision import make_client, vision_json_call

INSTRUCTIONS = """\
This image was generated (as SVG, then rendered) from the prompt:

  "{prompt}"

Evaluate it. First reason about what is depicted versus what was requested, \
then give two ratings on a 1-5 scale:

- "reasoning": 2-3 sentences analyzing the depiction against the prompt
- "animal_rating": 1-5 — how recognizable and well-drawn the requested animal is
- "vehicle_rating": 1-5 — how recognizable and well-drawn the requested \
vehicle is (essential parts present and connected)
- "action_rating": 1-5 — how convincingly the requested action is depicted \
(posture, contact points, interaction between the animal and objects)

Judge only what is visible. A beautiful image of the wrong animal scores low.
"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "animal_rating": {"type": "integer", "minimum": 1, "maximum": 5},
        "vehicle_rating": {"type": "integer", "minimum": 1, "maximum": 5},
        "action_rating": {"type": "integer", "minimum": 1, "maximum": 5},
    },
    "required": ["reasoning", "animal_rating", "vehicle_rating", "action_rating"],
    "additionalProperties": False,
}

async def judge_one(client, sem: asyncio.Semaphore, judge: str, png_path) -> None:
    out_path = SCORES_DIR / model_slug(judge) / png_path.parent.name / f"{png_path.stem}.json"
    if out_path.exists():
        return
    gen_path = GENERATIONS_DIR / png_path.parent.name / f"{png_path.stem}.json"
    rec = json.loads(gen_path.read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        scores = await vision_json_call(
            client,
            judge,
            INSTRUCTIONS.format(prompt=rec["prompt"]),
            png_path,
            schema=JUDGE_SCHEMA,
            metadata={
                "stage": "judge",
                "judge": judge,
                "ring": rec["ring"],
                "image": f"{png_path.parent.name}/{png_path.stem}",
            },
        )
    if scores is None:
        tqdm.write(f"FAILED  {model_slug(judge)} {png_path.parent.name}/{png_path.stem}")
        return
    out_path.write_text(json.dumps(scores, indent=2))


async def main() -> None:
    client = make_client()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    pngs = sorted(RENDERS_DIR.glob("*/*.png"))
    tasks = [judge_one(client, sem, judge, p) for judge in JUDGE_MODELS for p in pngs]
    print(f"{len(pngs)} images x {len(JUDGE_MODELS)} judges = {len(tasks)} scoring calls")
    await tqdm_asyncio.gather(*tasks, desc="judge")


if __name__ == "__main__":
    asyncio.run(main())
