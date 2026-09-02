from pathlib import Path

import pandas as pd
import pytest

from server.csv_provider import load_bond_data
from shared.models import BondSearchQuery


DATA_PATH = Path("data/bond_data.csv")


def test_filters_csv_by_credit_rating():
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

    results = load_bond_data(query, DATA_PATH)

    assert all(results["rating"] == "BBB")


def test_null_rating_returns_all_bonds():
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

    results = load_bond_data(query, DATA_PATH)

    assert len(results) > 0


@pytest.fixture
def range_data_path(tmp_path):
    path = tmp_path / "bonds.csv"
    pd.DataFrame(
        [
            {"Bond_Name": "Low", "Rating": "BBB", "Price": 90, "Coupon": 1.5},
            {"Bond_Name": "Middle", "Rating": "A", "Price": 100, "Coupon": 2.5},
            {"Bond_Name": "High", "Rating": "BBB", "Price": 110, "Coupon": 4.5},
        ]
    ).to_csv(path, index=False)
    return path


def range_filter(field, minimum=None, maximum=None):
    return {
        "field": field,
        "operator": "between",
        "value": (
            {"minimum": minimum, "maximum": maximum}
            if minimum is not None or maximum is not None
            else None
        ),
    }


@pytest.mark.parametrize(
    ("field", "minimum", "maximum", "expected"),
    [
        ("price", 100, None, ["Middle", "High"]),
        ("price", None, 100, ["Low", "Middle"]),
        ("price", 95, 105, ["Middle"]),
        ("price", 100, 100, ["Middle"]),
        ("coupon", 2.5, None, ["Middle", "High"]),
        ("coupon", None, 2.5, ["Low", "Middle"]),
        ("coupon", 2, 3, ["Middle"]),
        ("coupon", 2.5, 2.5, ["Middle"]),
    ],
)
def test_filters_numeric_ranges(
    range_data_path, field, minimum, maximum, expected
):
    query = BondSearchQuery.model_validate(
        {"filters": [range_filter(field, minimum, maximum)]}
    )

    results = load_bond_data(query, range_data_path)

    assert results["bond_name"].tolist() == expected


def test_combines_price_and_coupon_filters(range_data_path):
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                range_filter("price", 95, 110),
                range_filter("coupon", None, 3),
            ]
        }
    )

    results = load_bond_data(query, range_data_path)

    assert results["bond_name"].tolist() == ["Middle"]


@pytest.mark.parametrize("field", ["price", "coupon"])
def test_null_numeric_range_returns_all_bonds(range_data_path, field):
    query = BondSearchQuery.model_validate(
        {"filters": [range_filter(field)]}
    )

    results = load_bond_data(query, range_data_path)

    assert len(results) == 3
