import os
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


load_dotenv()
client = OpenAI()


class AnalysisCode(BaseModel):
    code: str


def build_analysis_instructions(
    dataset: pd.DataFrame,
    bql_query: str,
) -> str:
    columns = "\n".join(
        f"- {column}: {dtype}"
        for column, dtype in dataset.dtypes.items()
    )
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

The dataset schema is:
{columns}

Write Python code that performs the user's requested analysis.

Rules:
- Add meaningful headers to any new columns you create.
- Use only pandas operations on `dataset`.
- Do not import anything.
- Do not modify `dataset` in place.
- Store the final answer in a variable named `result`.
- Do not print anything.
- Never fabricate missing data.
- If the analysis is impossible using the available columns, use:
  result = {{"error": "explanation"}}
"""


def generate_analysis_code(
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

    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        instructions=instructions,
        input=query,
        text_format=AnalysisCode,
    )

    if response.output_parsed is None:
        raise ValueError("The AI response could not be parsed")

    return response.output_parsed.code


safe_builtins = {
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "sorted": sorted,
    "enumerate": enumerate,
    "range": range,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
    "ValueError": ValueError,
}


def execute_analysis_code(code: str, dataset: pd.DataFrame):
    local_scope = {
        "dataset": dataset.copy(),
        "pd": pd,
    }
    exec(
        code,
        {"__builtins__": safe_builtins},
        local_scope,
    )
    if "result" not in local_scope:
        raise ValueError("Generated code did not create a `result` variable")
    return local_scope["result"]


def analysis_result_to_dataframe(result) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        return result.reset_index(drop=True)
    if isinstance(result, pd.Series):
        return result.rename("value").reset_index()
    if isinstance(result, dict):
        try:
            return pd.DataFrame(result)
        except ValueError:
            return pd.DataFrame([result])
    if isinstance(result, (list, tuple)):
        return pd.DataFrame(result)
    return pd.DataFrame({"result": [result]})


def run_post_analysis(
    query: str,
    dataset: pd.DataFrame,
    bql_query: str,
) -> pd.DataFrame:
    code = generate_analysis_code(query, dataset, bql_query)
    result = execute_analysis_code(code, dataset)
    return analysis_result_to_dataframe(result)
