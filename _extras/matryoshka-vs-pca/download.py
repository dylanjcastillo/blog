"""Download BEIR corpora, queries, and qrels from Hugging Face.

Writes per-dataset parquet files under data/raw/. Queries are filtered to
those with test-split qrels. The msmarco corpus is streamed and cut off at
PCA_FIT_SAMPLE passages, so the full 8.8M-row corpus is never downloaded.
Resumable: existing outputs are skipped.

Usage:
    uv run python _extras/matryoshka-vs-pca/download.py [--only scifact]
"""

import argparse

import pandas as pd
from datasets import load_dataset

from config import DATASETS, PCA_FIT_CORPUS, PCA_FIT_SAMPLE, RAW_DIR


def download_eval_dataset(name: str) -> None:
    out_dir = RAW_DIR / name
    if (out_dir / "qrels.parquet").exists():
        print(f"{name}: already downloaded, skipping")
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    corpus = load_dataset(f"BeIR/{name}", "corpus", split="corpus")
    corpus_df = pd.DataFrame(
        {
            "doc_id": corpus["_id"],
            "text": [f"{t} {x}".strip() for t, x in zip(corpus["title"], corpus["text"])],
        }
    )
    corpus_df.to_parquet(out_dir / "corpus.parquet")

    qrels = load_dataset(f"BeIR/{name}-qrels", split="test")
    qrels_df = pd.DataFrame(
        {
            "query_id": [str(q) for q in qrels["query-id"]],
            "doc_id": [str(d) for d in qrels["corpus-id"]],
            "score": qrels["score"],
        }
    )

    queries = load_dataset(f"BeIR/{name}", "queries", split="queries")
    queries_df = pd.DataFrame({"query_id": queries["_id"], "text": queries["text"]})
    queries_df = queries_df[queries_df["query_id"].isin(set(qrels_df["query_id"]))]
    queries_df.to_parquet(out_dir / "queries.parquet")
    qrels_df.to_parquet(out_dir / "qrels.parquet")

    print(f"{name}: {len(corpus_df)} docs, {len(queries_df)} queries, {len(qrels_df)} qrels")


def download_pca_fit_corpus() -> None:
    out_path = RAW_DIR / PCA_FIT_CORPUS / "corpus.parquet"
    if out_path.exists():
        print(f"{PCA_FIT_CORPUS}: already downloaded, skipping")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stream = load_dataset(f"BeIR/{PCA_FIT_CORPUS}", "corpus", split="corpus", streaming=True)
    rows = []
    for row in stream:
        rows.append({"doc_id": row["_id"], "text": f"{row['title']} {row['text']}".strip()})
        if len(rows) >= PCA_FIT_SAMPLE:
            break
    pd.DataFrame(rows).to_parquet(out_path)
    print(f"{PCA_FIT_CORPUS}: {len(rows)} passages (PCA fit corpus)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="subset of dataset names, e.g. --only scifact")
    args = parser.parse_args()

    names = args.only or DATASETS + [PCA_FIT_CORPUS]
    for name in names:
        if name == PCA_FIT_CORPUS:
            download_pca_fit_corpus()
        else:
            download_eval_dataset(name)


if __name__ == "__main__":
    main()
