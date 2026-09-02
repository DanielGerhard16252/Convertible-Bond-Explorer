import os

from dotenv import load_dotenv
from openai import OpenAI

from shared.models import BondSearchQuery


load_dotenv()

client = OpenAI()

SYSTEM_PROMPT = """
Translate the user's convertible-bond search request into the supplied schema.

You must always return exactly two filters:

1. credit_rating
2. price

Do not add any other filters.

CREDIT RATING

Required structure:

{
  "field": "credit_rating",
  "operator": "in",
  "value": ["BBB"]
}

The credit-rating scale from strongest to weakest is:

AAA, AA+, AA, AA-, A+, A, A-, BBB+, BBB, BBB-,
BB+, BB, BB-, B+, B, B-, CCC+, CCC, CCC-, CC, C, D

Rules:

- The value must be a JSON list or null.
- For one rating, return a list containing one rating.
- For multiple specified ratings, return exactly those ratings.
- For a rating range, return every rating in the inclusive range.
- Preserve rating order from strongest to weakest.
- If no valid rating is specified, set value to null.
- Never guess a rating or select the closest rating.

Examples:

"BBB bonds"

{
  "field": "credit_rating",
  "operator": "in",
  "value": ["BBB"]
}

"A or D bonds"

{
  "field": "credit_rating",
  "operator": "in",
  "value": ["A", "D"]
}

"Bonds rated between BB and A+"

{
  "field": "credit_rating",
  "operator": "in",
  "value": [
    "A+",
    "A",
    "A-",
    "BBB+",
    "BBB",
    "BBB-",
    "BB+",
    "BB"
  ]
}

PRICE

Required structure:

{
  "field": "price",
  "operator": "between",
  "value": {
    "minimum": 90,
    "maximum": 110
  }
}

Rules:

- The minimum and maximum values must be numbers or null.
- Price boundaries are inclusive.
- "Above", "over", "at least" and "minimum" set minimum.
- "Below", "under", "at most" and "maximum" set maximum.
- "Exactly" sets minimum and maximum to the same value.
- If no price condition is specified, set the entire value to null.
- Do not invent missing price limits.

Examples:

"Price between 90 and 110"

{
  "field": "price",
  "operator": "between",
  "value": {
    "minimum": 90,
    "maximum": 110
  }
}

"Price above 90"

{
  "field": "price",
  "operator": "between",
  "value": {
    "minimum": 90,
    "maximum": null
  }
}

"Price below 110"

{
  "field": "price",
  "operator": "between",
  "value": {
    "minimum": null,
    "maximum": 110
  }
}

"Price exactly 100"

{
  "field": "price",
  "operator": "between",
  "value": {
    "minimum": 100,
    "maximum": 100
  }
}

COMPLETE RESPONSE EXAMPLES

"Show me BBB-rated bonds priced between 90 and 110"

{
  "filters": [
    {
      "field": "credit_rating",
      "operator": "in",
      "value": ["BBB"]
    },
    {
      "field": "price",
      "operator": "between",
      "value": {
        "minimum": 90,
        "maximum": 110
      }
    }
  ]
}

"Show me all convertible bonds"

{
  "filters": [
    {
      "field": "credit_rating",
      "operator": "in",
      "value": null
    },
    {
      "field": "price",
      "operator": "between",
      "value": null
    }
  ]
}
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