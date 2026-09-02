import pytest
from pydantic import ValidationError

from shared.models import BondSearchQuery, CreditRating, PriceRange


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


@pytest.mark.parametrize("field", ["price", "coupon"])
@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        (90, None),
        (None, 110),
        (90, 110),
        (100, 100),
    ],
)
def test_valid_numeric_range_filters(field, minimum, maximum):
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": field,
                    "operator": "between",
                    "value": {
                        "minimum": minimum,
                        "maximum": maximum,
                    },
                }
            ]
        }
    )

    value = query.filters[0].value
    assert isinstance(value, PriceRange)
    assert value.minimum == minimum
    assert value.maximum == maximum


@pytest.mark.parametrize("field", ["price", "coupon"])
def test_null_numeric_range_filter(field):
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": field,
                    "operator": "between",
                    "value": None,
                }
            ]
        }
    )

    assert query.filters[0].value is None

