#!/usr/bin/env bash
# Generate social cards for new posts. Skips silently in environments
# without uv (e.g. CI, where the committed cards are used as-is).
if ! command -v uv >/dev/null 2>&1; then
  echo "social cards: uv not found, skipping card generation"
  exit 0
fi
uv run python _extras/social_cards/generate_cards.py
