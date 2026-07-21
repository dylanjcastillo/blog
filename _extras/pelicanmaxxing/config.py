"""Shared configuration for the pelicanmaxxing experiment."""

from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
GENERATIONS_DIR = DATA_DIR / "generations"
RENDERS_DIR = DATA_DIR / "renders"
FEATURES_DIR = DATA_DIR / "features"
SCORES_DIR = DATA_DIR / "scores"
CORPUS_DIR = DATA_DIR / "corpus"
ANALYSIS_DIR = DATA_DIR / "analysis"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# All LLM calls are traced to this LangSmith project (overrides LANGCHAIN_PROJECT
# from .env so experiment traces don't mix with other work).
LANGSMITH_PROJECT = "pelicanmaxxing"

# Verify slugs against https://openrouter.ai/models before a full run:
#   uv run python _extras/pelicanmaxxing/generate.py --check-models
MODELS = [
    "openai/gpt-5.6-terra",
    "x-ai/grok-4.5",
    "z-ai/glm-5.2",
    "qwen/qwen3.7-max",
    "google/gemini-3.5-flash",
    "anthropic/claude-sonnet-5",
    "deepseek/deepseek-v4-pro"
]
EXTRACTOR_MODEL = "google/gemini-3.1-flash-lite"
JUDGE_MODELS = [
    "openai/gpt-5.6-luna"
]

# Unified reasoning setting sent to every contestant via OpenRouter's
# `reasoning` parameter. OpenAI models use the effort directly; other providers
# get it translated to a thinking budget; models without configurable
# reasoning ignore it. Requested effort is equalized — actual thinking tokens
# still vary by model.
REASONING = {"effort": "medium"}

N_SAMPLES = 3
TEMPERATURE = 1.0
MAX_CONCURRENCY = 8  # vision calls (extract/judge)
MODEL_CONCURRENCY = 10  # concurrent generation requests per contestant model
RENDER_WIDTH = 800

# Simon Willison's canonical wording, with only the subject substituted.
PROMPT_TEMPLATE = "Generate an SVG of {subject}"

ANIMALS = ["pelican", "flamingo", "heron", "otter", "raccoon", "antelope", "whale", "cat"]
VEHICLES = ["bicycle", "unicycle", "skateboard", "scooter", "plane", "boat"]

# Phrase per vehicle: "riding a" for rideables (matches Simon's canonical
# wording for the bicycle), "on a" where riding reads oddly.
VEHICLE_PHRASES = {
    "bicycle": "riding a",
    "unicycle": "riding a",
    "skateboard": "riding a",
    "scooter": "riding a",
    "plane": "on a",
    "boat": "on a",
}


def _article(word: str) -> str:
    return "an" if word[0].lower() in "aeiou" else "a"


def build_prompts() -> list[dict]:
    """The animal x vehicle grid. Ring 0 is the pelican-bicycle cell itself."""
    prompts = []
    for animal in ANIMALS:
        for vehicle in VEHICLES:
            ring = 0 if (animal == "pelican" and vehicle == "bicycle") else 1
            subject = f"{_article(animal)} {animal} {VEHICLE_PHRASES[vehicle]} {vehicle}"
            prompts.append(
                {
                    "id": f"{animal}-{vehicle}".replace(" ", "-"),
                    "ring": ring,
                    "subject": subject,
                    "animal": animal,
                    "vehicle": vehicle,
                }
            )
    return prompts


def model_slug(model: str) -> str:
    """Filesystem-safe short name for a model id."""
    return model.replace("/", "__")
