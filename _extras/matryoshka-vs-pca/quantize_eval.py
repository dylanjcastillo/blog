"""Quantization experiments on the cached embeddings.

Applies int8 and binary quantization to documents at several dimension
reductions (none, MRL truncation, in-domain PCA) and measures retrieval
quality. int8 uses asymmetric scoring: documents are quantized and queries
stay float32. Binary is evaluated both asymmetrically and with both sides
binarized, the pure-Hamming setup reported in the article. int8 uses
per-dimension min/max calibration on the corpus; binary keeps the sign bit
per dimension.

Storage per vector: float32 = 4d bytes, int8 = d bytes, binary = d/8 bytes.

Usage:
    uv run python _extras/matryoshka-vs-pca/quantize_eval.py [--only scifact]
"""

import argparse

import numpy as np
import pandas as pd

from config import ANALYSIS_DIR, DATASETS, EMBEDDINGS_DIR, FULL_DIM
from evaluate import fit_pca, load_dataset, normalize, pca_project, search_and_score

# (base reduction, dim, quantization). float32 rows are in results.csv
# already. "binary" keeps queries float32 (asymmetric); "binary_sym"
# binarizes queries too, the pure-Hamming setup most literature reports.
_BINARY_CELLS = [
    ("full", FULL_DIM),
    ("mrl", 512), ("mrl", 256), ("mrl", 128),
    ("pca_in", 512), ("pca_in", 256), ("pca_in", 128),
]
CONFIGS = [
    ("full", FULL_DIM, "int8"),
    ("mrl", 512, "int8"),
    ("mrl", 128, "int8"),
    ("pca_in", 512, "int8"),
    ("pca_in", 128, "int8"),
]
CONFIGS += [(m, d, q) for m, d in _BINARY_CELLS for q in ("binary", "binary_sym")]


def reduce_float(method: str, vectors: np.ndarray, dim: int, pca) -> np.ndarray:
    if method == "full":
        return normalize(vectors)
    if method == "mrl":
        return normalize(vectors[:, :dim])
    return pca_project(pca, vectors, dim)


def quantize_docs(docs: np.ndarray, quant: str) -> np.ndarray:
    """Quantize then dequantize, so the matmul scorer sees what an int8/binary
    index would effectively score against."""
    if quant == "int8":
        lo, hi = docs.min(axis=0), docs.max(axis=0)
        scale = hi - lo
        scale[scale == 0] = 1.0
        q = np.clip(np.round((docs - lo) / scale * 255), 0, 255)
        deq = (q / 255 * scale + lo).astype(np.float32)
        return normalize(deq)
    if quant in ("binary", "binary_sym"):
        return normalize(np.where(docs > 0, 1.0, -1.0).astype(np.float32))
    raise ValueError(quant)


def bytes_per_vector(dim: int, quant: str) -> float:
    return {"float32": 4 * dim, "int8": dim, "binary": dim / 8, "binary_sym": dim / 8}[quant]


def summarize(quantization: pd.DataFrame) -> pd.DataFrame:
    """Aggregate each configuration using the post's mean-of-ratios rule."""
    results = pd.read_csv(ANALYSIS_DIR / "results.csv")
    baseline = (
        results[(results["method"] == "full") & (results["dim"] == FULL_DIM)]
        [["dataset", "ndcg@10"]]
        .rename(columns={"ndcg@10": "baseline_ndcg@10"})
    )
    merged = quantization.merge(baseline, on="dataset", validate="many_to_one")
    merged["quality_retained"] = merged["ndcg@10"] / merged["baseline_ndcg@10"]
    summary = (
        merged.groupby(["method", "dim", "quant"], as_index=False)
        .agg(
            bytes=("bytes", "first"),
            quality_retained=("quality_retained", "mean"),
            mean_ndcg_at_10=("ndcg@10", "mean"),
            datasets=("dataset", "nunique"),
        )
    )
    summary["size_vs_full_float32"] = summary["bytes"] / (4 * FULL_DIM)
    return summary[
        [
            "method", "dim", "quant", "bytes", "size_vs_full_float32",
            "quality_retained", "mean_ndcg_at_10", "datasets",
        ]
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="subset of dataset names")
    args = parser.parse_args()

    rows = []
    for name in args.only or DATASETS:
        if not (EMBEDDINGS_DIR / f"{name}_docs.npy").exists():
            print(f"WARNING: {name} not embedded, skipping")
            continue
        data = load_dataset(name)
        pca = fit_pca(data["docs"], min(512, len(data["docs"]) - 1))
        for method, dim, quant in CONFIGS:
            if method == "pca_in" and dim > pca.n_components_:
                continue
            doc_matrix = quantize_docs(reduce_float(method, data["docs"], dim, pca), quant)
            query_matrix = reduce_float(method, data["queries"], dim, pca)
            if quant == "binary_sym":
                query_matrix = quantize_docs(query_matrix, "binary")
            metrics = search_and_score(data, doc_matrix, query_matrix)
            rows.append({
                "dataset": name, "method": method, "dim": dim, "quant": quant,
                "bytes": bytes_per_vector(dim, quant), **metrics,
            })
            print(f"{name:16s} {method:7s} d={dim:4d} {quant:6s} "
                  f"({bytes_per_vector(dim, quant):6.0f} B)  ndcg@10={metrics['ndcg@10']:.4f}")

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    quantization = pd.DataFrame(rows)
    quantization.to_csv(ANALYSIS_DIR / "quantization.csv", index=False)
    summarize(quantization).to_csv(ANALYSIS_DIR / "quantization_summary.csv", index=False)
    print(
        f"\nWrote {ANALYSIS_DIR / 'quantization.csv'} and "
        f"{ANALYSIS_DIR / 'quantization_summary.csv'}"
    )


if __name__ == "__main__":
    main()
