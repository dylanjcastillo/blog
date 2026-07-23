#!/usr/bin/env bash
# Generate social cards for posts that don't have one yet.
# - Locally: uses the project environment (uv run).
# - CI: uses an ephemeral env with only the two deps the script needs,
#   so new posts get cards even if they weren't rendered locally.
if ! command -v uv >/dev/null 2>&1; then
  echo "social cards: uv not found, skipping card generation"
  exit 0
fi
if [ -n "$CI" ]; then
  uv run --no-project --with pillow --with pyyaml python _extras/social_cards/generate_cards.py
else
  uv run python _extras/social_cards/generate_cards.py
fi
