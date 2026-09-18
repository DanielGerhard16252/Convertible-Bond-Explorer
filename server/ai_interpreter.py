from server.prompts import SYSTEM_PROMPT, build_system_prompt

from server.ai_client import create_client, model_name

from shared.models import BondSearchQuery


def parse_ai_query(value) -> BondSearchQuery:
    if isinstance(value, BondSearchQuery):
        return value
    if isinstance(value, str):
        return BondSearchQuery.model_validate_json(value)
    return BondSearchQuery.model_validate(value)


def interpret_request_with_ai(text: str) -> BondSearchQuery:
    if not text or not text.strip():
        raise ValueError("Search request cannot be empty")
    with create_client() as client:
        response = client.responses.parse(
            model=model_name(),
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
