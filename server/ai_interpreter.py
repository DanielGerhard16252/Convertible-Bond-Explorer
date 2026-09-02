import os

from dotenv import load_dotenv
from openai import OpenAI

from shared.models import BondSearchQuery


load_dotenv()

client = OpenAI()

SYSTEM_PROMPT = """
Translate natural-language convertible-bond search requests into
structured search queries.

The currently supported functionality is:

- Search field: credit_rating
- Operator: equal
- Values: only the credit ratings permitted by the supplied schema

Interpret only what the user explicitly requests.
Do not invent additional filters.
"""


def interpret_request_with_ai(text: str) -> BondSearchQuery:
    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        text_format=BondSearchQuery,
    )

    query = response.output_parsed

    if query is None:
        raise ValueError("The AI response could not be parsed")

    return query