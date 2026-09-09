import pandas as pd
import pytest

from data.data_generation import BQL_FIELD_MAP, generate_bond_data
from server.csv_provider import load_bond_data
from shared.models import BondSearchQuery


def test_generated_data_is_reproducible_and_usable_by_csv_provider(tmp_path):
    data = generate_bond_data(100, seed=42)
    pd.testing.assert_frame_equal(data, generate_bond_data(100, seed=42))
    assert data.columns.tolist() == BQL_FIELD_MAP
    assert data["AMT_OUTSTANDING"].between(50_000_000, 500_000_000).all()
    path = tmp_path / "bonds.csv"
    data.to_csv(path, index=False)
    query = BondSearchQuery.model_validate({"filters": [
        {"field": "bond_universe", "operator": "equals", "value": "convertible"},
        {"field": "amount_outstanding", "operator": "between", "value": {"minimum": 50}},
    ]})
    results = load_bond_data(query, path)
    assert len(results) == data["CONVERTIBLE"].eq("Y").sum()
    assert not results.empty


def test_empty_and_invalid_sample_sizes():
    assert generate_bond_data(0).columns.tolist() == BQL_FIELD_MAP
    assert generate_bond_data(0).empty
    with pytest.raises(ValueError, match="negative"):
        generate_bond_data(-1)
