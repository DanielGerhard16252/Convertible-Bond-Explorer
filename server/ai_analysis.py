import os
from server.prompts import build_analysis_instructions

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
client = OpenAI()



def run_post_analysis(
    query: str,
    dataset: pd.DataFrame,
    bql_query: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    if not query or not query.strip():
        raise ValueError("Post-analysis instructions cannot be empty")
    if dataset.empty:
        raise ValueError("There are no filtered results to analyse")
    if not bql_query or not bql_query.strip():
        raise ValueError("Generated BQL context cannot be empty")

    instructions = build_analysis_instructions(dataset, bql_query)

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        instructions=instructions,
        input=(
            [dict(message) for message in history]
            + [{"role": "user", "content": query}]
            if history else query
        ),
        tools=[{"type": "web_search"}],
    )

    return response.output_text
