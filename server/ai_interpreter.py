import os
from datetime import date

from dotenv import load_dotenv
from openai import OpenAI

from shared.models import BondSearchQuery


load_dotenv()

client = OpenAI()

SYSTEM_PROMPT = """
Translate the user's convertible-bond search request into the supplied schema.

You must always return exactly nine filters:

1. credit_rating
2. price
3. coupon
4. issuer
5. maturity
6. currency
7. conversion_premium
8. delta
9. yield_to_maturity

Do not add any other filters.

For maturity use operator "between" and an object with ISO-8601 minimum and
maximum dates. For currency use operator "equals" and a three-letter ISO code.
For conversion_premium, delta, and yield_to_maturity use operator "between"
and an object with numeric minimum and maximum values. Use null when a filter
was not requested. Conversion premium and yield values are percentages; delta
uses the numeric units stated by the user.

CREDIT RATING

Required structure:

{
  "field": "credit_rating",
  "operator": "in",
  "value": ["BBB"]
}

The credit-rating scale from strongest to weakest is:

AAA, AA+, AA, AA-, A+, A, A-, BBB+, BBB, BBB-,
BB+, BB, BB-, B+, B, B-, CCC+, CCC, CCC-, CC, C, D, NR

Rules:

- The value must be a JSON list or null.
- For one rating, return a list containing one rating.
- For multiple specified ratings, return exactly those ratings.
- For a rating range, return every rating in the inclusive range.
- Preserve rating order from strongest to weakest.
- Use NR when the user asks for missing, unrated, not-rated, or N.A bonds.
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

COUPON

Required structure:

{
  "field": "coupon",
  "operator": "between",
  "value": {
    "minimum": 0.1,
    "maximum": 2.7
  }
}

Rules:

- The minimum and maximum values must be numbers or null.
- Coupon boundaries are inclusive.
- "Above", "over", "at least" and "minimum" set minimum.
- "Below", "under", "at most" and "maximum" set maximum.
- "Exactly" sets minimum and maximum to the same value.
- If no coupon condition is specified, set the entire value to null.
- Do not invent missing coupon limits.

Examples:

"Coupon between 0.1 and 2.7"

{
  "field": "coupon",
  "operator": "between",
  "value": {
    "minimum": 0.1,
    "maximum": 2.7
  }
}

"Coupon above 0.1"

{
  "field": "coupon",
  "operator": "between",
  "value": {
    "minimum": 0.1,
    "maximum": null
  }
}

"Coupon below 2.7"

{
  "field": "coupon",
  "operator": "between",
  "value": {
    "minimum": null,
    "maximum": 2.7
  }
}

"Coupon exactly 1.4"

{
  "field": "coupon",
  "operator": "between",
  "value": {
    "minimum": 1.4,
    "maximum": 1.4
  }
}


ISSUER

Required structure:

{
  "field": "issuer",
  "operator": "equals",
  "value": "Acme Corporation"
}

Rules:

- The value must be one issuer name as a string or null.
- Preserve the issuer name supplied by the user.
- Never return a list or infer additional issuers.
- If no issuer is specified, set value to null.

Example:

"Bonds issued by Acme Corporation"

{
  "field": "issuer",
  "operator": "equals",
  "value": "Acme Corporation"
}

COMPLETE RESPONSE EXAMPLES

"Show me BBB-rated bonds priced between 90 and 110 with coupon between 0.1 and 2.7"

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
    },
    {
    
      "field": "coupon",
      "operator": "between",
      "value": {
        "minimum": 0.1,
        "maximum": 2.7
      }
    },
    {
      "field": "issuer",
      "operator": "equals",
      "value": null
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
    },
    {
      "field": "coupon",
      "operator": "between",
      "value": null
    },
    {
      "field": "issuer",
      "operator": "equals",
      "value": null
    }
  ]
}
"""


def build_system_prompt(current_date: date | None = None) -> str:
    current_date = current_date or date.today()
    return (
        f"Current date: {current_date.isoformat()}.\n"
        "Resolve relative dates such as 'within two years' using this date.\n\n"
        f"{SYSTEM_PROMPT}"
    )

def interpret_request_with_ai(text: str) -> BondSearchQuery:
    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        input=[
            {
                "role": "system",
                "content": build_system_prompt(),
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
