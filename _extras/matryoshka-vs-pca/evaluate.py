"""Brute-force retrieval evaluation for every (dataset, method, dim) cell.

Methods, all starting from the same full-dim embeddings:
  full     untouched full-dim vectors (the ceiling)
  mrl      truncate to d dims, re-normalize (what the dimensions param does)
  pca_in   PCA fit on the eval corpus's own doc embeddings
  pca_ood  PCA fit on the msmarco sample, transferred to the eval corpus

Search is exact (numpy matmul), so no ANN recall contaminates the numbers.
PCA components are nested, so each fit source is fit once at MAX_PCA_DIM and
sliced. Outputs data/analysis/results.csv and fit_size_sweep.csv.

Usage:
    uv run python _extras/matryoshka-vs-pca/evaluate.py
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from config import (
    ANALYSIS_DIR,
    DATASETS,
    DIMS,
    EMBEDDINGS_DIR,
    FIT_SIZE_DATASET,
    FIT_SIZES,
    FULL_DIM,
    K_VALUES,
    MAX_PCA_DIM,
    PCA_FIT_CORPUS,
    RAW_DIR,
    SEED,
)

K_MAX = max(K_VALUES)


def normalize(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def load_dataset(name: str) -> dict:
    docs = np.load(EMBEDDINGS_DIR / f"{name}_docs.npy")
    # ArguAna's queries are themselves corpus documents (same id, same text
    # modulo title), so self-matches must be dropped, as is standard for that
    # dataset. Elsewhere an id shared between a query and a doc is a numeric
    # coincidence (55 cases in FiQA), not the same object.
    drop_self = name == "arguana"
    queries = np.load(EMBEDDINGS_DIR / f"{name}_queries.npy")
    doc_ids = pd.read_parquet(EMBEDDINGS_DIR / f"{name}_docs_ids.parquet")["doc_id"].astype(str)
    query_ids = pd.read_parquet(EMBEDDINGS_DIR / f"{name}_queries_ids.parquet")["query_id"].astype(str)
    qrels = pd.read_parquet(RAW_DIR / name / "qrels.parquet")
    rels = {
        qid: dict(zip(g["doc_id"], g["score"]))
        for qid, g in qrels[qrels["score"] > 0].groupby("query_id")
    }
    return {
        "docs": docs,
        "queries": queries,
        "doc_ids": list(doc_ids),
        "query_ids": list(query_ids),
        "rels": rels,
        "drop_self": drop_self,
    }


def fit_pca(doc_vectors: np.ndarray, n_components: int) -> PCA:
    pca = PCA(n_components=n_components, random_state=SEED)
    pca.fit(normalize(doc_vectors))
    return pca


def pca_project(pca: PCA, vectors: np.ndarray, dim: int) -> np.ndarray:
    reduced = (normalize(vectors) - pca.mean_) @ pca.components_[:dim].T
    return normalize(reduced)


def reduce(method: str, vectors: np.ndarray, dim: int, pca: PCA | None) -> np.ndarray:
    if method == "full":
        return normalize(vectors)
    if method == "mrl":
        return normalize(vectors[:, :dim])
    if method in ("pca_in", "pca_ood"):
        return pca_project(pca, vectors, dim)
    raise ValueError(method)


QUERY_BLOCK = 512  # queries scored per matmul, bounds memory on large corpora


def score_queries(data: dict, doc_matrix: np.ndarray, query_matrix: np.ndarray) -> pd.DataFrame:
    """Exact top-K_MAX search; one row per query with NDCG@10 and recall@k."""
    doc_ids = data["doc_ids"]
    doc_index = {d: i for i, d in enumerate(doc_ids)}
    k = min(K_MAX, len(doc_ids))

    top = np.empty((len(query_matrix), k), dtype=np.int64)
    for start in range(0, len(query_matrix), QUERY_BLOCK):
        scores = query_matrix[start : start + QUERY_BLOCK] @ doc_matrix.T
        if data["drop_self"]:
            for qi, qid in enumerate(data["query_ids"][start : start + QUERY_BLOCK]):
                if qid in doc_index:
                    scores[qi, doc_index[qid]] = -np.inf
        block_top = np.argpartition(-scores, k - 1, axis=1)[:, :k]
        row_order = np.argsort(-np.take_along_axis(scores, block_top, axis=1), axis=1)
        top[start : start + len(scores)] = np.take_along_axis(block_top, row_order, axis=1)

    rows = []
    for qi, qid in enumerate(data["query_ids"]):
        rel = data["rels"].get(qid)
        if not rel:
            continue
        retrieved = [doc_ids[di] for di in top[qi]]
        gains = [rel.get(d, 0) for d in retrieved[:10]]
        dcg = sum(g / np.log2(i + 2) for i, g in enumerate(gains))
        ideal = sorted(rel.values(), reverse=True)[:10]
        idcg = sum(g / np.log2(i + 2) for i, g in enumerate(ideal))
        row = {"query_id": qid, "ndcg@10": dcg / idcg}
        for kv in K_VALUES:
            row[f"recall@{kv}"] = sum(1 for d in retrieved[:kv] if d in rel) / len(rel)
        rows.append(row)
    return pd.DataFrame(rows)


def search_and_score(data: dict, doc_matrix: np.ndarray, query_matrix: np.ndarray) -> dict:
    """Corpus-level means of score_queries."""
    per_query = score_queries(data, doc_matrix, query_matrix)
    result = {"ndcg@10": float(per_query["ndcg@10"].mean()), "n_queries": len(per_query)}
    for kv in K_VALUES:
        result[f"recall@{kv}"] = float(per_query[f"recall@{kv}"].mean())
    return result


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    ood_path = EMBEDDINGS_DIR / f"{PCA_FIT_CORPUS}_docs.npy"
    if ood_path.exists():
        pca_ood = fit_pca(np.load(ood_path), MAX_PCA_DIM)
    else:
        pca_ood = None
        print(f"WARNING: {ood_path.name} missing, skipping pca_ood")

    rows = []
    for name in DATASETS:
        if not (EMBEDDINGS_DIR / f"{name}_docs.npy").exists():
            print(f"WARNING: {name} not embedded yet, skipping")
            continue
        data = load_dataset(name)
        pca_in = fit_pca(data["docs"], min(MAX_PCA_DIM, len(data["docs"]) - 1))
        pcas = {"pca_in": pca_in, "pca_ood": pca_ood}

        cells = [("full", FULL_DIM)]
        cells += [("mrl", d) for d in DIMS if d < FULL_DIM]
        for method in ("pca_in", "pca_ood"):
            if pcas[method] is not None:
                cells += [(method, d) for d in DIMS if d <= pcas[method].n_components_]

        for method, dim in cells:
            pca = pcas.get(method)
            doc_matrix = reduce(method, data["docs"], dim, pca)
            query_matrix = reduce(method, data["queries"], dim, pca)
            metrics = search_and_score(data, doc_matrix, query_matrix)
            rows.append({"dataset": name, "method": method, "dim": dim, **metrics})
            print(f"{name:10s} {method:14s} d={dim:4d}  ndcg@10={metrics['ndcg@10']:.4f}")

    results = pd.DataFrame(rows)
    results.to_csv(ANALYSIS_DIR / "results.csv", index=False)

    # Secondary sweep: how much fitting data does in-domain PCA need?
    if not (EMBEDDINGS_DIR / f"{FIT_SIZE_DATASET}_docs.npy").exists():
        print(f"WARNING: {FIT_SIZE_DATASET} not embedded yet, skipping fit-size sweep")
        return
    data = load_dataset(FIT_SIZE_DATASET)
    rng = np.random.default_rng(SEED)
    sweep_rows = []
    for fit_size in FIT_SIZES:
        if fit_size is None or fit_size >= len(data["docs"]):
            sample, label = data["docs"], len(data["docs"])
        else:
            sample = data["docs"][rng.choice(len(data["docs"]), fit_size, replace=False)]
            label = fit_size
        pca = fit_pca(sample, min(MAX_PCA_DIM, len(sample) - 1))
        for dim in [d for d in DIMS if d <= pca.n_components_]:
            doc_matrix = pca_project(pca, data["docs"], dim)
            query_matrix = pca_project(pca, data["queries"], dim)
            metrics = search_and_score(data, doc_matrix, query_matrix)
            sweep_rows.append({"dataset": FIT_SIZE_DATASET, "fit_size": label, "dim": dim, **metrics})
            print(f"fit_size={label:6d} d={dim:4d}  ndcg@10={metrics['ndcg@10']:.4f}")

    pd.DataFrame(sweep_rows).to_csv(ANALYSIS_DIR / "fit_size_sweep.csv", index=False)

    # Index-growth simulation: fit PCA on a random half of the corpus, index
    # ALL docs (so half the index was never seen by the fit), then split
    # queries by whether their relevant docs were in the fit half. MRL gets
    # the same split as a control: any seen/unseen gap it shows is query
    # difficulty, not a fitting effect, so PCA's gap minus MRL's gap is the
    # true cost of searching docs added after the fit.
    n_docs = len(data["docs"])
    fit_mask = np.zeros(n_docs, dtype=bool)
    fit_mask[rng.choice(n_docs, n_docs // 2, replace=False)] = True
    seen_doc_ids = {d for d, m in zip(data["doc_ids"], fit_mask) if m}

    def query_group(qid: str) -> str | None:
        rel_docs = data["rels"][qid].keys()
        in_fit = [d in seen_doc_ids for d in rel_docs]
        if all(in_fit):
            return "seen"
        if not any(in_fit):
            return "unseen"
        return None  # mixed: ambiguous, excluded

    pca_half = fit_pca(data["docs"][fit_mask], MAX_PCA_DIM)
    growth_rows = []
    for dim in [d for d in DIMS if d <= MAX_PCA_DIM]:
        for method in ("pca_half", "mrl"):
            if method == "pca_half":
                doc_matrix = pca_project(pca_half, data["docs"], dim)
                query_matrix = pca_project(pca_half, data["queries"], dim)
            else:
                doc_matrix = normalize(data["docs"][:, :dim])
                query_matrix = normalize(data["queries"][:, :dim])
            per_query = score_queries(data, doc_matrix, query_matrix)
            per_query["group"] = per_query["query_id"].map(query_group)
            for group, g in per_query.dropna(subset=["group"]).groupby("group"):
                growth_rows.append({
                    "dataset": FIT_SIZE_DATASET, "method": method, "dim": dim,
                    "group": group, "ndcg@10": float(g["ndcg@10"].mean()),
                    "n_queries": len(g),
                })
                print(f"growth {method:9s} d={dim:4d} {group:6s}  "
                      f"ndcg@10={growth_rows[-1]['ndcg@10']:.4f} (n={len(g)})")

    pd.DataFrame(growth_rows).to_csv(ANALYSIS_DIR / "index_growth.csv", index=False)
    print(f"\nWrote {ANALYSIS_DIR / 'results.csv'}, fit_size_sweep.csv, index_growth.csv")


if __name__ == "__main__":
    main()
