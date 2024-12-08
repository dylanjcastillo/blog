from pathlib import Path

import instructor
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI

data_dir = Path(__file__).parent.parent.parent / "data" / "live_bench"
reasoning_dir = data_dir / "reasoning"
math_dir = data_dir / "math"
language_dir = data_dir / "language"

np.random.seed(42)

load_dotenv()
langsmith_client = wrap_openai(AsyncOpenAI())
instructor_client = instructor.from_openai(langsmith_client, mode=instructor.Mode.TOOLS)


def process_reasoning_questions():
    df_reasoning = pd.read_json(reasoning_dir / "question.jsonl", lines=True).assign(
        turns_str=lambda x: x.turns.str[0],
        ground_truth=lambda x: x.ground_truth.str.strip(),
    )
    assert df_reasoning.turns.str.len().eq(1).all()

    df_reasoning["updated_question"] = (
        df_reasoning.turns_str.str.replace("in **bold** ", "")
        .str.replace("***", "")
        .str.replace("**", "")
        .str.strip()
    )
    df_reasoning.to_json(
        reasoning_dir / "updated_questions.jsonl", lines=True, orient="records"
    )
    df_reasoning.to_csv(reasoning_dir / "updated_questions.csv", index=False)


def process_language_questions():
    df_language = pd.read_json(language_dir / "question.jsonl", lines=True).assign(
        turns_str=lambda x: x.turns.str[0],
        ground_truth=lambda x: x.ground_truth.str.strip(),
    )

    assert df_language.turns.str.len().eq(1).all()

    df_language["updated_question"] = (
        df_language.turns_str.str.replace(
            " Begin the plot summary with <PLOT_SUMMARY>.", ""
        )
        .str.replace("in **bold** ", "")
        .str.replace("***", "")
        .str.replace("**", "")
        .str.strip()
    )
    df_language.to_json(
        language_dir / "updated_questions.jsonl", lines=True, orient="records"
    )
    df_language.to_csv(language_dir / "updated_questions.csv", index=False)


def process_math_questions():
    df_math = (
        pd.read_json(math_dir / "question.jsonl", lines=True)
        .query("task != 'AMPS_Hard'")
        .assign(
            turns_str=lambda x: x.turns.str[0],
            ground_truth=lambda x: x.ground_truth.str.strip(),
        )
    )
    df_math["updated_question"] = (
        df_math.turns_str.str.strip()
        .str.replace(
            r" Please put your final answer in a $\\boxed{}$.",
            "Please think step by step out loud and provide your answer at the end.",
        )
        .str.replace(
            "If you cannot determine the correct multiple-choice answer, take your best guess.",
            "If you cannot determine the correct answer, take your best guess.",
        )
        .str.replace(
            "Please think step by step, and then display the answer at the very end of your response.",
            "Please think step by step out loud and provide your answer at the end.",
        )
        .str.replace(
            "Once you have your answer, please duplicate that letter five times in a single string. For example, if the answer is F, then write FFFFF.",
            "Please think step by step out loud and provide your answer as a single letter (e.g., F or A). Don't include any other text except a single letter in your answer.",
        )
        .str.replace(
            """Your final answer should be STRICTLY in the format:

<Detailed reasoning>

Answer: <comma separated list of numbers representing expression identifiers>""",
            "Please think step by step out loud and provide your answer as a comma separated list of numbers representing expression identifiers (e.g., 1,2,3). Don't include any other text except a comma separated list of numbers in your answer.",
        )
        .str.replace(
            "Remember to have the three digits as the last part of the response.",
            "Your answer should not include any other text except the three digits.",
        )
        .str.strip()
    )

    assert df_math.turns.str.len().eq(1).all()

    df_math.to_json(math_dir / "updated_questions.jsonl", lines=True, orient="records")
    df_math.to_csv(math_dir / "updated_questions.csv", index=False)


if __name__ == "__main__":
    process_reasoning_questions()
    process_language_questions()
    process_math_questions()
