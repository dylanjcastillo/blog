import asyncio
from pathlib import Path

import instructor
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI
from reasoning import classify_reasoning_questions, replace_reasoning_questions_format

data_dir = Path(__file__).parent.parent.parent / "data" / "live_bench"
reasoning_dir = data_dir / "reasoning"
math_dir = data_dir / "math"
language_dir = data_dir / "language"

np.random.seed(42)

load_dotenv()
langsmith_client = wrap_openai(AsyncOpenAI())
instructor_client = instructor.from_openai(langsmith_client, mode=instructor.Mode.TOOLS)


def process_reasoning_questions():
    df_reasoning = (
        pd.read_json(reasoning_dir / "question.jsonl", lines=True)
        .assign(
            turns_str=lambda x: x.turns.str[0],
            ground_truth=lambda x: x.ground_truth.str.strip(),
        )
        .reset_index()
        .rename(columns={"index": "data_point_id"})
    )
    assert df_reasoning.turns.str.len().eq(1).all()

    df_reasoning["updated_question"] = (
        df_reasoning.turns_str.str.replace("in **bold**", "")
        .str.replace("**", "")
        .str.strip()
    )
    df_reasoning.to_json(
        reasoning_dir / "updated_questions.jsonl", lines=True, orient="records"
    )
    df_reasoning.to_csv(reasoning_dir / "updated_questions.csv", index=False)


def process_language_questions():
    df_language = (
        pd.read_json(language_dir / "question.jsonl", lines=True)
        .assign(
            turns_str=lambda x: x.turns.str[0],
            ground_truth=lambda x: x.ground_truth.str.strip(),
        )
        .reset_index()
        .rename(columns={"index": "data_point_id"})
    )

    assert df_language.turns.str.len().eq(1).all()

    df_language["replaced_question"] = (
        df_language.turns_str.str.replace(
            "Begin the plot summary with <PLOT_SUMMARY>", ""
        )
        .str.replace("in **bold**", "")
        .str.replace("**", "")
        .str.strip()
    )
    df_language.to_json(
        language_dir / "updated_questions.jsonl", lines=True, orient="records"
    )
    df_language.to_csv(language_dir / "updated_questions.csv", index=False)


if __name__ == "__main__":
    process_reasoning_questions()
    process_language_questions()
