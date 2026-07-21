# Are AI labs pelicanmaxxing?

Tests whether models are suspiciously good at Simon Willison's "pelican riding
a bicycle" SVG benchmark — i.e. whether pelicans show up in training more than
other animals. The prompt set is an animals x vehicles grid where the
canonical prompt (ring 0) is one cell and every other cell is a control.

Signals: panel-normalized excess score per animal row, the pelican-bicycle
interaction residual, and cross-lab compositional convergence (facing
direction, sun, ground).

## Pipeline

Requires `OPENROUTER_API_KEY` in the repo's `.env`. Run from the repo root:

```bash
# 0. Verify the model slugs in config.py still exist on OpenRouter
uv run python _extras/pelicanmaxxing/generate.py --check-models

# 1. Generate: models x prompts x samples (resumable, skips existing)
uv run python _extras/pelicanmaxxing/generate.py

# 2. Render SVGs to PNG (failures logged, they count as data)
uv run python _extras/pelicanmaxxing/render.py

# 3. Blind feature inventory (extractor never sees the prompt)
uv run python _extras/pelicanmaxxing/extract.py

# 4. Quality judging (judges see the prompt; two judges from different labs)
uv run python _extras/pelicanmaxxing/judge.py

# 5. Analysis: CSVs + plotly figures in data/analysis/
uv run python _extras/pelicanmaxxing/analysis.py
```

Steps 1-4 are all resumable — re-run after failures or after adding models.

Scale is models x prompts x N_SAMPLES (see config.py); with N_SAMPLES = 1 the
whole run stays cheap, at the cost of noisier single-observation cells and no
within-model diversity probe.

## Reliability check worth running before publishing

Re-run `extract.py` with a second `EXTRACTOR_MODEL` on ~50 images and report
feature agreement — one sentence in the post preempts the "LLM judges are
unreliable" objection for the fingerprint claims.
