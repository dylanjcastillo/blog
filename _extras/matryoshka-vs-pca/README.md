# Matryoshka embeddings vs PCA

Compares two ways of shrinking embedding vectors for retrieval: truncating an
MRL-trained model (nomic-embed-text-v1.5) versus projecting its full vectors
with PCA. Same model, same corpora, so the comparison isolates the reduction
method.

The interesting axis is distribution shift: matryoshka truncation has no
fitting step, while PCA quality depends on what it was fit on. `pca_in` fits
on the eval corpus itself; `pca_ood` fits on a 100k MS MARCO sample and
transfers, standing in for "you fit PCA once, then your domain drifted".

Evaluated on four small BEIR datasets (scifact, nfcorpus, arguana, fiqa) with
exact search, NDCG@10 and recall@10/100, at 512/256/128/64/32 dims.

## Pipeline

Run from the repo root. Embedding runs locally (MPS), no API keys needed.

```bash
# 1. Download BEIR corpora/queries/qrels (msmarco is streamed, 100k sample)
uv run python _extras/matryoshka-vs-pca/download.py

# 2. Embed everything at full 768 dims (~175k texts, resumable per file)
uv run python _extras/matryoshka-vs-pca/embed.py

# 3. Evaluate every (dataset, method, dim) cell + the PCA fit-size sweep
uv run python _extras/matryoshka-vs-pca/evaluate.py
```

Steps 1-2 are resumable: existing files are skipped. To smoke-test the
pipeline end to end on one small dataset first:

```bash
uv run python _extras/matryoshka-vs-pca/download.py --only scifact
uv run python _extras/matryoshka-vs-pca/embed.py --only scifact
```

Outputs land in `data/analysis/`: `results.csv` (main grid),
`fit_size_sweep.csv` (PCA fit-sample-size sweep), and `index_growth.csv`
(PCA fit on half the corpus, queries split by whether their relevant docs
were seen by the fit — simulates docs added to the index after fitting, with
MRL on the same query split as the difficulty control). The post's charts
read those via `figures.py`.

## Details that matter

- Truncated vectors are re-normalized before scoring, which matches what the
  OpenAI `dimensions` parameter does (verified: cosine 1.0 against the API).
- PCA is fit once per fit-corpus at 512 components and sliced, since the top-k
  eigenvectors are nested (PCA is matryoshka-shaped too, in that one sense).
- ArguAna queries are themselves corpus documents; self-matches are removed
  before scoring, as is standard for that dataset.
