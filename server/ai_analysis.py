import os
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
client = OpenAI()



def build_analysis_instructions(
    dataset: pd.DataFrame,
    bql_query: str,
) -> str:
    records = dataset.replace({float("nan"): None}).to_dict(orient="records")

    return f"""
Current date: {date.today().isoformat()}.

You are a financial analyst specialising in convertible and high-yield bonds.

The upstream generated Bloomberg Query Language (BQL) query is:
```bql
{bql_query}
```

Use the BQL to understand the intended universe, filters, and requested source
fields. The actual pandas DataFrame named `dataset` is authoritative for the
rows and columns available to your code; do not assume unavailable columns.

The dataset is:
{records}

Answer the user's question using only the supplied bond dataset and research any extra context needed.

Rules:
- Do not invent missing values.
- Explain calculations briefly.
"""


def run_post_analysis(
    query: str,
    dataset: pd.DataFrame,
    bql_query: str,
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
        input=query,
        tools=[{"type": "web_search"}],
    )

    return response.output_text
