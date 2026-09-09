import os
from server.prompts import SYSTEM_PROMPT, build_system_prompt

from dotenv import load_dotenv
from openai import OpenAI

from shared.models import BondSearchQuery


load_dotenv()

client = OpenAI()

def parse_ai_query(value) -> BondSearchQuery:
    if isinstance(value, BondSearchQuery):
        return value
    if isinstance(value, str):
        return BondSearchQuery.model_validate_json(value)
    return BondSearchQuery.model_validate(value)


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
        tools=[{"type": "web_search"}],
    )

    if response.output_parsed is None:
        raise ValueError("The AI response could not be parsed")

    return parse_ai_query(response.output_parsed)
