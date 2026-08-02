"""Encode every corpus and query set at full dimension.

All reduction happens later in evaluate.py, so embeddings are computed once.
Vectors are stored unnormalized as float32 .npy files with doc/query ids in a
sidecar parquet, under a per-model subdirectory. Resumable at file
granularity: existing .npy files are skipped.

The provider is set in config.py: "openrouter" or "openai" (async, needs the
matching API key in the repo's .env) or "local" (sentence-transformers on MPS).

Usage:
    uv run python _extras/matryoshka-vs-pca/embed.py [--only scifact] [--limit 100]
"""

import argparse
import asyncio

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from config import (
    BATCH_SIZE,
    DATASETS,
    DOC_PREFIX,
    EMBEDDINGS_DIR,
    MAX_CHARS,
    MODEL_NAME,
    OPENAI_BATCH,
    OPENAI_BATCH_CHARS,
    OPENAI_CONCURRENCY,
    OPENROUTER_BASE_URL,
    PCA_FIT_CORPUS,
    PROVIDER,
    QUERY_PREFIX,
    RAW_DIR,
    TASK_INSTRUCTIONS,
)


def encode_local(texts: list[str], model) -> np.ndarray:
    return model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=False,
    ).astype(np.float32)


async def _openai_batch(client, sem: asyncio.Semaphore, batch: list[str]) -> np.ndarray:
    async with sem:
        for attempt in range(5):
            try:
                resp = await client.embeddings.create(model=MODEL_NAME, input=batch)
                return np.array([e.embedding for e in resp.data], dtype=np.float32)
            except Exception as exc:
                if attempt == 4:
                    if len(batch) == 1:
                        raise RuntimeError(f"unembeddable text ({len(batch[0])} chars): {exc}")
                    break
                tqdm.write(f"retry {attempt + 1}: {exc}")
                await asyncio.sleep(2**attempt)
    # A batch that fails all retries usually has one bad input; bisect to
    # isolate it instead of killing a multi-hour run.
    tqdm.write(f"batch of {len(batch)} failed, bisecting")
    mid = len(batch) // 2
    left = await _openai_batch(client, sem, batch[:mid])
    right = await _openai_batch(client, sem, batch[mid:])
    return np.concatenate([left, right])


def _make_batches(texts: list[str]) -> list[list[str]]:
    """Pack texts into requests capped by both count and total characters,
    since the API limits total tokens per request as well as per input."""
    batches, cur, cur_chars = [], [], 0
    for t in texts:
        if cur and (len(cur) >= OPENAI_BATCH or cur_chars + len(t) > OPENAI_BATCH_CHARS):
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(t)
        cur_chars += len(t)
    if cur:
        batches.append(cur)
    return batches


def _truncate_tokens(texts: list[str]) -> list[str]:
    """The API rejects empty inputs and inputs over 8191 tokens; chars are a
    bad proxy for tokens on messy web text, so truncate token-accurately.
    The char pre-cut just keeps tokenization fast on huge documents."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    out = []
    for t in texts:
        t = t[:MAX_CHARS] or " "
        tokens = enc.encode(t, disallowed_special=())
        if len(tokens) > 8000:
            t = enc.decode(tokens[:8000])
        out.append(t)
    return out


async def encode_openai(texts: list[str], client) -> np.ndarray:
    texts = _truncate_tokens(texts)
    sem = asyncio.Semaphore(OPENAI_CONCURRENCY)
    batches = _make_batches(texts)
    tasks = [asyncio.create_task(_openai_batch(client, sem, b)) for b in batches]
    for fut in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="embed"):
        await fut
    return np.concatenate([t.result() for t in tasks])  # tasks keep batch order


def encode(name: str, kind: str, prefix: str, limit: int | None, backend) -> None:
    """kind is 'docs' or 'queries'; reads the matching raw parquet."""
    out_path = EMBEDDINGS_DIR / f"{name}_{kind}.npy"
    if out_path.exists():
        print(f"{name} {kind}: already embedded, skipping")
        return

    raw_file = "corpus.parquet" if kind == "docs" else "queries.parquet"
    df = pd.read_parquet(RAW_DIR / name / raw_file)
    if limit:
        df = df.head(limit)

    texts = [prefix + t for t in df["text"]]
    if PROVIDER != "local":
        vectors = asyncio.run(encode_openai(texts, backend))
    else:
        vectors = encode_local(texts, backend)

    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    np.save(out_path, vectors)
    id_col = "doc_id" if kind == "docs" else "query_id"
    df[[id_col]].to_parquet(EMBEDDINGS_DIR / f"{name}_{kind}_ids.parquet")
    print(f"{name} {kind}: {vectors.shape}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="subset of dataset names")
    parser.add_argument("--limit", type=int, help="encode only the first N texts (smoke test)")
    args = parser.parse_args()

    if PROVIDER == "local":
        from sentence_transformers import SentenceTransformer

        backend = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
    else:
        import os

        from openai import AsyncOpenAI

        load_dotenv()
        if PROVIDER == "openrouter":
            backend = AsyncOpenAI(
                base_url=OPENROUTER_BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"]
            )
        else:
            backend = AsyncOpenAI()

    names = args.only or DATASETS + [PCA_FIT_CORPUS]
    for name in names:
        encode(name, "docs", DOC_PREFIX, args.limit, backend)
        if name != PCA_FIT_CORPUS:
            query_prefix = QUERY_PREFIX
            if MODEL_NAME.startswith("qwen/") and name in TASK_INSTRUCTIONS:
                query_prefix = f"Instruct: {TASK_INSTRUCTIONS[name]}\nQuery: "
            encode(name, "queries", query_prefix, args.limit, backend)


if __name__ == "__main__":
    main()
