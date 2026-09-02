from pathlib import Path

from server.csv_provider import load_bond_data
from shared.models import BondSearchQuery


DATA_PATH = Path("data/bond_data.csv")


def test_filters_csv_by_credit_rating():
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

    results = load_bond_data(query, DATA_PATH)

    assert all(results["rating"] == "BBB")


def test_null_rating_returns_all_bonds():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "equal",
                    "value": None,
                }
            ]
        }
    )

    results = load_bond_data(query, DATA_PATH)

    assert len(results) > 0