import os

from dotenv import load_dotenv
from openai import OpenAI

from shared.models import BondSearchQuery


load_dotenv()

client = OpenAI()

SYSTEM_PROMPT = """
Translate the user's convertible-bond search request into the supplied schema.

Currently supported:

- field: credit_rating
- operator: equal
- accepted values are defined by the schema

Always include the credit_rating filter.

If the user provides a recognised credit rating, use it.

If the rating is missing, invalid, ambiguous or unrecognised, set value to null.

Never guess a rating or select the closest available rating.
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