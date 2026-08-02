"""Shared configuration for the matryoshka-vs-pca experiment."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

# Both models are MRL-trained: the first d dimensions of the output are
# trained to work as a standalone embedding. "openrouter"/"openai" hit the
# API (OPENROUTER_API_KEY / OPENAI_API_KEY in the repo's .env); "local" runs
# nomic on MPS via sentence-transformers. Nomic requires task prefixes,
# which embed.py prepends manually; text-embedding-3 does not use them.
PROVIDER = os.environ.get("EMBED_PROVIDER", "openrouter")

# API models routable through OpenRouter, with their output dims. ada-002 is
# the pre-MRL control: same provider and dims as 3-small, but from before
# truncation was a training objective, so its "mrl" arm is plain truncation.
API_MODELS = {
    "openai/text-embedding-3-small": 1536,
    "openai/text-embedding-ada-002": 1536,
    "qwen/qwen3-embedding-8b": 4096,
}

if PROVIDER == "local":
    MODEL_NAME, FULL_DIM = "nomic-ai/nomic-embed-text-v1.5", 768
    QUERY_PREFIX, DOC_PREFIX = "search_query: ", "search_document: "
else:
    MODEL_NAME = os.environ.get("EMBED_MODEL", "openai/text-embedding-3-small")
    FULL_DIM = API_MODELS[MODEL_NAME]
    # Qwen3-Embedding expects an instruction prefix on queries only.
    if MODEL_NAME.startswith("qwen/"):
        QUERY_PREFIX = ("Instruct: Given a web search query, retrieve relevant "
                        "passages that answer the query\nQuery: ")
        DOC_PREFIX = ""
    else:
        QUERY_PREFIX = DOC_PREFIX = ""

# Per-task query instructions, matching what official MTEB evaluations use
# for instruction-tuned embedding models (the E5/Qwen instruction set).
# Applied for qwen instead of the generic QUERY_PREFIX above.
TASK_INSTRUCTIONS = {
    "scifact": "Given a scientific claim, retrieve documents that support or refute the claim",
    "nfcorpus": "Given a question, retrieve relevant documents that best answer the question",
    "arguana": "Given a claim, find documents that refute the claim",
    "fiqa": "Given a financial question, retrieve user replies that best answer the question",
    "scidocs": "Given a scientific paper title, retrieve paper abstracts that are cited by the given paper",
    "quora": "Given a question, retrieve questions that are semantically equivalent to the given question",
    "trec-covid": "Given a query on COVID-19, retrieve documents that answer the query",
    "webis-touche2020": "Given a question, retrieve detailed and persuasive arguments that answer the question",
}

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODEL_SLUG = MODEL_NAME.replace("/", "__")
EMBEDDINGS_DIR = DATA_DIR / "embeddings" / MODEL_SLUG
ANALYSIS_DIR = DATA_DIR / "analysis" / MODEL_SLUG

BATCH_SIZE = 64  # local encode batch
OPENAI_BATCH = 256  # max texts per embeddings request
# Cap on total characters per request: the API also limits total tokens per
# request, which 256 long documents would exceed. ~600k chars ≈ 150k tokens.
OPENAI_BATCH_CHARS = 600_000
OPENAI_CONCURRENCY = 8
# text-embedding-3 caps inputs at 8191 tokens; a char-level truncation keeps
# requests safely under it without pulling in a tokenizer.
MAX_CHARS = 20_000
SEED = 42

# BEIR eval datasets, chosen to span domains (science, medical, finance,
# argument mining, web, duplicate questions) and text lengths. All are
# evaluated with exact search; the scorer chunks queries so even the
# half-million-doc corpora stay in memory.
DATASETS = [
    "scifact",
    "nfcorpus",
    "arguana",
    "fiqa",
    "scidocs",
    "trec-covid",
    "webis-touche2020",
    "quora",
]

# Where the transferred ("OOD") PCA is fit: a generic web-passage corpus,
# standing in for "you fit PCA on the data you had, then your domain drifted".
PCA_FIT_CORPUS = "msmarco"
PCA_FIT_SAMPLE = 100_000

# Full dim is the untouched baseline; every method below it must earn its keep.
DIMS = sorted({FULL_DIM, 512, 256, 128, 64, 32}, reverse=True)

# PCA components are nested (top-k eigenvectors), so one fit at MAX_PCA_DIM
# serves every smaller dim by slicing.
MAX_PCA_DIM = 512

# Secondary question: how much data does PCA need before it stops being noisy?
# Swept on one dataset only (the largest corpus).
FIT_SIZE_DATASET = "fiqa"
FIT_SIZES = [1_000, 5_000, 20_000, None]  # None = all docs

K_VALUES = [10, 100]  # recall cutoffs; NDCG is always @10

# Datasets evaluated but excluded from the post's charts and aggregates.
# Empty: all eight are reported (trec-covid and webis-touche2020 with a
# ~50-query noise caveat in the prose).
REPORT_EXCLUDE = []
