# Matryoshka embeddings vs PCA

Compares two ways of shrinking embedding vectors for retrieval: MRL truncation
(keep the first d dimensions, re-normalize) versus PCA projection. Evaluated
on eight BEIR datasets with exact search, NDCG@10 and recall@10/100, at
512/256/128/64/32 dimensions.

Models:

- `openai/text-embedding-3-small` (1536 dims, MRL): the main model
- `openai/text-embedding-ada-002` (1536 dims, pre-MRL): control for whether
  PCA's performance depends on MRL training
- `qwen/qwen3-embedding-8b` (4096 dims, MRL): replication on a stronger,
  open-weights MRL implementation. Queries use the per-task instructions that
  official MTEB evaluations use (see `TASK_INSTRUCTIONS` in `config.py`)

PCA arms: fit in-domain (on the eval corpus itself) and out-of-domain (fit
once on 100k MS MARCO passages and transferred). A fit-sample-size sweep runs
on FiQA. Full-dimension scores reproduce the official MTEB results within
0.005 NDCG@10 for every model-dataset pair.

## Pipeline

Run from the repo root. Needs `OPENROUTER_API_KEY` in the repo's `.env`.
Select the model with `EMBED_MODEL` (see `API_MODELS` in `config.py`);
`EMBED_PROVIDER=local` runs nomic-embed-text-v1.5 on-device instead.

```bash
# 1. Download BEIR corpora/queries/qrels (msmarco is streamed, 100k sample)
uv run python _extras/matryoshka-vs-pca/download.py

# 2. Embed everything at full dimension (resumable per file)
EMBED_MODEL=openai/text-embedding-3-small uv run python _extras/matryoshka-vs-pca/embed.py

# 3. Evaluate every (dataset, method, dim) cell + the PCA fit-size sweep
EMBED_MODEL=openai/text-embedding-3-small uv run python _extras/matryoshka-vs-pca/evaluate.py
```

Extras:

```bash
# int8/binary quantization grid (asymmetric int8, symmetric + asymmetric binary)
uv run python _extras/matryoshka-vs-pca/quantize_eval.py

# exhaustive-search speed benchmark over Quora with faiss
uv run python _extras/matryoshka-vs-pca/speed_bench.py

# check that local truncation matches the API's `dimensions` parameter
uv run python _extras/matryoshka-vs-pca/verify_truncation.py
```

Outputs land in `data/analysis/<model>/` as CSVs (committed; everything else
under `data/` is gitignored and regenerates for a few dollars). The post's
charts read the CSVs via `figures.py`.
