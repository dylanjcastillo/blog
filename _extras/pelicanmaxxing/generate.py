"""Generate SVGs for every model x prompt x sample via OpenRouter.

Resumable: existing output files are skipped, so it's safe to re-run after
failures or after adding models/prompts to config.py.

Usage:
    uv run python _extras/pelicanmaxxing/generate.py
    uv run python _extras/pelicanmaxxing/generate.py --check-models
"""

import argparse
import asyncio
import json
import os
import re
import sys

import cairosvg
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

# Generations are retried until they produce a renderable SVG, up to this cap.
MAX_GEN_ATTEMPTS = 6

from config import (
    GENERATIONS_DIR,
    MODEL_CONCURRENCY,
    MODELS,
    N_SAMPLES,
    OPENROUTER_BASE_URL,
    PROMPT_TEMPLATE,
    REASONING,
    TEMPERATURE,
    build_prompts,
    model_slug,
)
from vision import make_client

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.DOTALL | re.IGNORECASE)


def extract_svg(text: str) -> str | None:
    """Take the longest <svg>...</svg> block (models sometimes emit fragments first)."""
    matches = SVG_RE.findall(text or "")
    return max(matches, key=len) if matches else None


def svg_renders(svg: str) -> bool:
    try:
        cairosvg.svg2png(bytestring=svg.encode(), output_width=100)
        return True
    except Exception:
        return False


def api_key() -> str:
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not set (add it to .env)")
    return key


def check_models() -> None:
    """Verify every configured slug exists on OpenRouter."""
    resp = httpx.get(f"{OPENROUTER_BASE_URL}/models", timeout=30)
    resp.raise_for_status()
    available = {m["id"] for m in resp.json()["data"]}
    from config import EXTRACTOR_MODEL, JUDGE_MODELS

    for model in [*MODELS, EXTRACTOR_MODEL, *JUDGE_MODELS]:
        status = "ok" if model in available else "NOT FOUND"
        print(f"{status:>10}  {model}")


async def generate_one(
    client: AsyncOpenAI, sem: asyncio.Semaphore, model: str, prompt: dict, sample: int
) -> None:
    out_path = GENERATIONS_DIR / model_slug(model) / f"{prompt['id']}__s{sample}.json"
    if out_path.exists():
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prompt_text = PROMPT_TEMPLATE.format(subject=prompt["subject"])
    async with sem:
        attempts = 0
        retry_reasons: list[str] = []
        svg = None
        text = ""
        usage = None
        while svg is None and attempts < MAX_GEN_ATTEMPTS:
            attempts += 1
            for net_try in range(3):
                try:
                    # Streamed: slow reasoning models (minutes per SVG) would
                    # hit idle gateway timeouts on non-streaming requests; here
                    # the timeout applies between chunks, not the whole request.
                    stream = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt_text}],
                        temperature=TEMPERATURE,
                        timeout=600,
                        stream=True,
                        stream_options={"include_usage": True},
                        extra_body={"reasoning": REASONING},
                        langsmith_extra={
                            "metadata": {
                                "stage": "generate",
                                "prompt_id": prompt["id"],
                                "ring": prompt["ring"],
                                "sample": sample,
                                "attempt": attempts,
                            }
                        },
                    )
                    parts: list[str] = []
                    async for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            parts.append(chunk.choices[0].delta.content)
                        if getattr(chunk, "usage", None):
                            usage = chunk.usage.model_dump()
                    text = "".join(parts)
                    break
                except Exception as e:
                    if net_try == 2:
                        tqdm.write(f"FAILED {model} {prompt['id']} s{sample}: {e}")
                        return
                    tqdm.write(f"net retry  {model} {prompt['id']} s{sample}: {type(e).__name__}")
                    await asyncio.sleep(5 * (net_try + 1))

            candidate = extract_svg(text)
            if candidate is None:
                retry_reasons.append("no svg in response")
            elif not svg_renders(candidate):
                retry_reasons.append("svg failed to render")
            else:
                svg = candidate
            if svg is None and attempts < MAX_GEN_ATTEMPTS:
                tqdm.write(f"regen {attempts}  {model} {prompt['id']} s{sample}: {retry_reasons[-1]}")

    record = {
        "model": model,
        "prompt_id": prompt["id"],
        "ring": prompt["ring"],
        "animal": prompt["animal"],
        "vehicle": prompt["vehicle"],
        "sample": sample,
        "prompt": prompt_text,
        "reasoning": REASONING,
        "response": text,
        "svg": svg,
        "attempts": attempts,
        "retry_reasons": retry_reasons,
        "usage": usage,
    }
    out_path.write_text(json.dumps(record, indent=2))
    if svg is None:
        tqdm.write(f"NO VALID SVG after {attempts} attempts  {model} {prompt['id']} s{sample}")


async def main() -> None:
    client = make_client()
    # One semaphore per model: a slow provider only queues behind itself,
    # never behind the other contestants.
    sems = {model: asyncio.Semaphore(MODEL_CONCURRENCY) for model in MODELS}
    prompts = build_prompts()
    tasks = [
        generate_one(client, sems[model], model, prompt, sample)
        for model in MODELS
        for prompt in prompts
        for sample in range(N_SAMPLES)
    ]
    print(f"{len(tasks)} generations ({len(MODELS)} models x {len(prompts)} prompts x {N_SAMPLES} samples)")
    await tqdm_asyncio.gather(*tasks, desc="generate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-models", action="store_true")
    args = parser.parse_args()
    if args.check_models:
        api_key()
        check_models()
    else:
        asyncio.run(main())
