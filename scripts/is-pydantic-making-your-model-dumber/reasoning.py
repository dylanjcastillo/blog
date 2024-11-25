import asyncio
from asyncio import Semaphore
from enum import Enum

import instructor
import numpy as np
from dotenv import load_dotenv
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

np.random.seed(42)

load_dotenv()
langsmith_client = wrap_openai(AsyncOpenAI())
instructor_client = instructor.from_openai(langsmith_client, mode=instructor.Mode.TOOLS)


class FormatType(Enum):
    T1 = "Bold formatting for a single phrase. Example: Think step by step, and then put your answer in **bold** as a single phrase (for example, **sphere**)."
    T2 = "Bold formatting for a list of three words. Example: Think step by step, and then put your answer in **bold** as a list of three words, yes or no (for example, **yes, no, yes**)."
    T3 = "Bold formatting for a single integer. Example: Think step by step, and then put your answer in **bold** as a single integer (for example, **0**)."
    T4 = "Return a single digit number. Example: Return a single digit number, in the following format: **N**, where N is the position."
    T5 = "Return your answer as a single word. Example: Return your answer as a single word, in the following format: **X**, where X is the answer."
    OTHER = "Other formatting requirements. Example: Other formatting requirements (if none of the above apply)"


format_mapping = {
    FormatType.T1.name: "Put your answer as a single phrase (for example, sphere).",
    FormatType.T2.name: "Put your answer as a list of three words, yes or no (for example, yes, no, yes).",
    FormatType.T3.name: "Put your answer as a single integer (for example, 0).",
    FormatType.T4.name: "Return a single digit number, in the following format: N, where N is the position.",
    FormatType.T5.name: "Return your answer as a single word, in the following format: X, where X is the answer.",
}


class FormatClassification(BaseModel):
    classification: FormatType = Field(
        description=f"The formatting requirements of the output of the provided question. Only allowed types: {[t.value for t in FormatType]}, should be used",
    )


system_prompt_classification_reasoning = "You're a helpful assistant. I will provide you with a question and you will classify the formatting requirements of the output of the provided question into the most appropriate category."


class UpdatedQuestion(BaseModel):
    updated_question: str


system_prompt_replace_reasoning_format = (
    "You're a helpful assistant. I will provide you with a question and the old formatting requirements. Your task is to replace the old formatting requirements with the new ones."
    "Please return the full text of the question with the new formatting requirements. Don't include any other text. Don't include 'Question:' or 'Old formatting:' or 'New formatting:'"
)


@traceable
async def run_model_with_instructor(
    system_message: str,
    user_message: str,
    response_model: BaseModel,
    semaphore: Semaphore,
) -> dict:
    async with semaphore:
        return await instructor_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            response_model=response_model,
        )


@traceable
async def classify_reasoning_questions(df, concurrency: int = 30):
    semaphore = Semaphore(concurrency)
    tasks = [
        run_model_with_instructor(
            system_message=system_prompt_classification_reasoning,
            user_message=f"Question:\n{row.turns_str}",
            response_model=FormatClassification,
            semaphore=semaphore,
        )
        for _, row in df.iterrows()
    ]
    responses = await asyncio.gather(*tasks)
    return [r.classification for r in responses]


@traceable
async def replace_reasoning_questions_format(df, concurrency: int = 30):
    semaphore = Semaphore(concurrency)
    tasks = [
        run_model_with_instructor(
            system_message=system_prompt_replace_reasoning_format,
            user_message=f"Question:\n{row.turns_str}\nOld formatting:\n{row.classification.value}\nNew formatting:{format_mapping[row.classification.name]}\n",
            response_model=UpdatedQuestion,
            semaphore=semaphore,
        )
        for _, row in df.iterrows()
    ]
    responses = await asyncio.gather(*tasks)
    return [r.updated_question for r in responses]
