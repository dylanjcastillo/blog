"""Shared helpers for VLM calls over rendered PNGs via OpenRouter."""

import asyncio
import base64
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI
from tqdm import tqdm

from config import OPENROUTER_BASE_URL

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def make_client() -> AsyncOpenAI:
    load_dotenv(override=True)
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not set (add it to .env)")
    # max_retries=0: retrying is handled explicitly by callers; the SDK's own
    # silent retries would multiply with ours on hanging requests.
    return wrap_openai(AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=key, max_retries=0))


def image_content(png_path: Path) -> dict:
    b64 = base64.b64encode(png_path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


async def vision_json_call(
    client: AsyncOpenAI,
    model: str,
    instructions: str,
    png_path: Path,
    schema: dict | None = None,
    metadata: dict | None = None,
) -> dict | None:
    """Send instructions + image, parse a single JSON object from the reply.

    With `schema`, requests structured outputs; the last retry drops the
    response_format in case the provider rejects it."""
    try:
        image = image_content(png_path)
    except FileNotFoundError:
        tqdm.write(f"  gone  {png_path.name} (deleted mid-run), skipping")
        return None
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": instructions}, image],
        }
    ]
    for attempt in range(3):
        kwargs = {}
        if metadata:
            kwargs["langsmith_extra"] = {"metadata": metadata}
        if schema and attempt < 2:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": schema},
            }
        try:
            resp = await client.chat.completions.create(
                model=model, messages=messages, temperature=0, timeout=180, **kwargs
            )
            match = JSON_RE.search(resp.choices[0].message.content or "")
            if match:
                return json.loads(match.group())
            last_error = f"no JSON in reply: {(resp.choices[0].message.content or '')[:200]!r}"
        except Exception as e:
            last_error = repr(e)
        await asyncio.sleep(3 * (attempt + 1))
    tqdm.write(f"  error  {model} on {png_path.name}: {last_error}")
    return None
