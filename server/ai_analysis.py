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

PRESENTATION AND FORMATTING

Present the answer as a polished financial research response adapted to the
user's specific question.

- Lead directly with the conclusion or most decision-relevant finding.
- Use a short, descriptive title only when useful.
- Organise longer answers into clear sections with descriptive headings.
- Keep paragraphs short and avoid repeating the same observation.
- Prefer concise tables when comparing multiple securities or reporting
  several metrics.
- Markdown tables must be valid: do not insert blank lines between table rows.
- Put units in column headings where possible and use consistent decimal places.
- Format percentages to two decimal places and dates consistently.
- Use bullet points for risks, assumptions and actions, but avoid excessive
  nested lists.
- Use bold sparingly, primarily for key conclusions, security names and
  important warnings.
- Do not describe every row in prose after presenting the same information
  in a table.
- Separate dataset observations from interpretation or recommendations.
- Clearly label missing data, assumptions and limitations.
- Never manufacture metrics that are not present in the dataset or calculated
  by executed code.
- Include only sections that help answer the question. Do not force every
  response into the same structure.
- For simple questions, give a short direct answer rather than a full report.
- For analytical questions, use this general order where appropriate:
  conclusion, supporting evidence, interpretation, risks or limitations.
- End with a brief actionable conclusion when the question asks for a decision,
  ranking, strategy or recommendation.
When discussing three or more securities, summarise them in a compact comparison
table rather than separate bullet-point paragraphs. After the table, discuss
only the most important distinctions, anomalies or risks.
Default to a concise answer of approximately 300–600 words unless the user asks
for a detailed report. Prioritise decision-relevant findings over generic
financial explanation.
If extra information is needed to answer the user's question for example benchmarks, use the `web_search` tool to find relevant information. Always state any extra information used and cite sources and provide links where possible.

EXTERNAL BENCHMARKS AND CREDIT SPREADS

When the user's question requires a market benchmark that is not contained in
the dataset, use web search to obtain it rather than stopping immediately.

For an approximate credit spread:

- Use the bond's YTM from the supplied dataset.
- Select a government bond yield in the same currency and with the closest
  reasonably available maturity:
  - USD: US Treasury
  - GBP: UK gilt
  - EUR: German Bund
  - JPY: Japanese government bond
  - CAD: Government of Canada bond
  - AUD: Australian government bond
  - CHF: Swiss Confederation bond
- Prefer an official government, central-bank or recognised market-data source.
- Match the benchmark by remaining maturity, not the bond's original tenor.
- Interpolate between two benchmark maturities when useful and when both yields
  are available.
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
