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


def test_valid_single_issuer_filter():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "issuer",
                    "operator": "equals",
                    "value": "Acme Corporation",
                }
            ]
        }
    )

    assert query.filters[0].value == "Acme Corporation"


def test_rejects_multiple_issuers():
    with pytest.raises(ValidationError):
        BondSearchQuery.model_validate(
            {
                "filters": [
                    {
                        "field": "issuer",
                        "operator": "equals",
                        "value": ["Acme", "Example Inc"],
                    }
                ]
            }
        )


def test_converts_amount_outstanding_text_to_minimum_range():
    query = BondSearchQuery.model_validate({"filters": [{
        "field": "amount_outstanding",
        "operator": "between",
        "value": "50MM",
    }]})

    value = query.filters[0].value
    assert isinstance(value, PriceRange)
    assert value.minimum == 50
    assert value.maximum is None


def test_decodes_json_string_amount_outstanding_range():
    query = BondSearchQuery.model_validate({"filters": [{
        "field": "amount_outstanding",
        "operator": "between",
        "value": '{"minimum": 50, "maximum": null}',
    }]})

    value = query.filters[0].value
    assert isinstance(value, PriceRange)
    assert value.minimum == 50
    assert value.maximum is None


def test_rejects_combined_bond_universe():
    with pytest.raises(ValidationError, match="must be convertible or high_yield"):
        BondSearchQuery.model_validate({"filters": [{
            "field": "bond_universe",
            "operator": "equals",
            "value": "convertible_or_high_yield",
        }]})

