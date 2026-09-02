import pytest
from datetime import date

from server.bql_compiler import compile_query
from shared.models import BondSearchQuery


def test_null_rating_is_valid():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "in",
                    "value": None,
                }
            ]
        }
    )

    assert query.filters[0].value is None


def test_null_rating_is_ignored_by_compiler():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "in",
                    "value": None,
                }
            ]
        }
    )

    bql = compile_query(query)
    assert bql.startswith("GET(")
    assert "FOR(filter(bondsuniv('active'" in bql

from server.ai_interpreter import build_system_prompt, interpret_request_with_ai


def test_system_prompt_includes_current_date():
    prompt = build_system_prompt(date(2026, 9, 2))

    assert prompt.startswith("Current date: 2026-09-02.")
    assert "Resolve relative dates" in prompt


def test_live_openai_interpretation():
    query = interpret_request_with_ai(
        "Show me BBB-rated convertible bonds"
    )

    assert query.filters[0].value == ["BBB"]

def test_live_openai_interpretation():
    query = interpret_request_with_ai(
        "AAA Bonds"
    )

    assert query.filters[0].value == ["AAA"]

def test_live_openai_interpretation():
    query = interpret_request_with_ai(
        "Bonds with credit C"
    )

    assert query.filters[0].value == ["C"]

def test_live_openai_interpretation_returns_null_for_invalid_rating():
    query = interpret_request_with_ai(
        "Bonds with oiajds credit rating"
    )

    assert query.filters[0].value is None
