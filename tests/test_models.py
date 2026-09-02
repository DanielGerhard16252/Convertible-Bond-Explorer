import pytest
from pydantic import ValidationError

from shared.models import BondSearchQuery, CreditRating


def test_valid_credit_rating_filter():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "in",
                    "value": ["BBB"],
                }
            ]
        }
    )

    assert query.filters[0].value == ["BBB"]


def test_invalid_credit_rating_filter():
    with pytest.raises(ValidationError):
        BondSearchQuery.model_validate(
            {
                "filters": [
                    {
                        "field": "credit_rating",
                        "operator": "in",
                        "value": ["Excellent"],
                    }
                ]
            }
        )

def test_multiple_non_contiguous_ratings():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "in",
                    "value": ["A", "D"],
                }
            ]
        }
    )

    assert query.filters[0].value == [
        CreditRating.A,
        CreditRating.D,
    ]

def test_null_credit_rating():
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

