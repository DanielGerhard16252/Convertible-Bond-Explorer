import pytest
from pydantic import ValidationError

from shared.models import BondSearchQuery


def test_valid_credit_rating_filter():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "equal",
                    "value": "BBB",
                }
            ]
        }
    )

    assert query.filters[0].value == "BBB"


def test_invalid_credit_rating_filter():
    with pytest.raises(ValidationError):
        BondSearchQuery.model_validate(
            {
                "filters": [
                    {
                        "field": "credit_rating",
                        "operator": "equal",
                        "value": "Excellent",
                    }
                ]
            }
        )