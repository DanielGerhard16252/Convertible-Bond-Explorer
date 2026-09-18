import pandas as pd
import pytest

from data.search_demo_generation import generate_search_demo
from server.csv_search import search_csv, add_csv_benchmarks
from server.bql_compiler import get_result_columns
from shared.models import BondSearchQuery
from shared.ratings import HIGH_YIELD_RATINGS


@pytest.fixture
def demo(tmp_path):
    bonds, options = generate_search_demo(150, seed=42)
    bond_path, option_path = tmp_path / "bonds.csv", tmp_path / "options.csv"
    bonds.to_csv(bond_path, index=False)
    options.to_csv(option_path, index=False)
    return bonds, bond_path, option_path


def query(filters=(), limit=None):
    return BondSearchQuery.model_validate({"filters": list(filters), "max_number": limit})


def test_default_high_yield_and_limit_rank_after_filtering(demo):
    bonds, path, _ = demo
    result = search_csv(query(limit=7), data_path=path)
    eligible = bonds[bonds.BB_COMPOSITE.isin(HIGH_YIELD_RATINGS)
                     & bonds.SRCH_ASSET_CLASS.eq("Corporates")
                     & bonds.AMT_OUTSTANDING.ge(50_000_000)]
    expected = eligible.sort_values("AMT_OUTSTANDING_USD", ascending=False).head(7)
    assert result.ID.tolist() == expected.ID.tolist()
    assert set(get_result_columns(query())) <= set(result.columns)
    assert result.attrs["bond_universe"] == "high_yield"


def test_all_filters_together_and_benchmark_return_columns(demo):
    bonds, path, options = demo
    bond = bonds[bonds.CONVERTIBLE.eq("Y")].iloc[0]
    filters = [{"field": "bond_universe", "operator": "equals", "value": "convertible"}]
    for field, value in [("isin", bond.ID_ISIN), ("issuer", bond.LONG_COMP_NAME)]:
        filters.append({"field": field, "operator": "equals", "value": value})
    for field, value in [("credit_rating", bond.BB_COMPOSITE), ("currency", bond.CRNCY),
                         ("country", bond.CNTRY_OF_RISK), ("fi_bics_level_2", bond["CLASSIFICATION_NAME(BICS,2)"]),
                         ("payment_rank", bond.PAYMENT_RANK)]:
        filters.append({"field": field, "operator": "in", "value": [value]})
    for field, value in [("price", bond.PX_LAST), ("coupon", bond.CPN),
                         ("conversion_premium", bond.CV_PCT_PREMIUM),
                         ("yield_to_maturity", bond["YIELD(YIELD_TYPE=YTM)"]),
                         ("yield_to_worst", bond["YIELD(YIELD_TYPE=YTW)"]),
                         ("amount_outstanding", bond.AMT_OUTSTANDING / 1_000_000)]:
        filters.append({"field": field, "operator": "between", "value": {"minimum": value-.00001, "maximum": value+.00001}})
    filters.append({"field": "maturity", "operator": "between", "value": {"minimum": bond.MATURITY, "maximum": bond.MATURITY}})
    result = search_csv(query(filters, limit=10), True, path, options)
    assert result.ID.tolist() == [bond.ID]
    assert result.BENCHMARK_IVOL.notna().all()
    assert result.BENCHMARK_EXPIRE_DT.iloc[0] == pd.Timestamp(bond.MATURITY) + pd.Timedelta(days=30)
    assert "SYNTHETIC" in result.data_source.iloc[0]


def test_government_asset_class_and_no_results(demo):
    _, path, _ = demo
    result = search_csv(query([{"field": "asset_classes", "operator": "in", "value": ["Governments"]}]), data_path=path)
    assert not result.empty
    assert result.asset_class.eq("Governments").all()
    empty = search_csv(query([{"field": "issuer", "operator": "equals", "value": "not present"}]), data_path=path)
    assert empty.empty
    assert "PAYMENT_RANK" in empty.columns


def test_missing_return_fields_raise_instead_of_silently_disappearing(demo):
    bonds, path, _ = demo
    bonds.drop(columns="PAYMENT_RANK").to_csv(path, index=False)
    with pytest.raises(ValueError, match="payment_rank"):
        search_csv(query(), data_path=path)


def test_benchmarks_ignore_puts_wrong_tickers_and_outside_strikes(tmp_path):
    path = tmp_path / "options.csv"
    pd.DataFrame({
        "ID": ["put", "wrong ticker", "wrong strike", "match"],
        "NAME": ["put", "wrong ticker", "wrong strike", "match"],
        "TICKER": ["AAA", "BBB", "AAA", "AAA"], "PUT_CALL": ["Put", "Call", "Call", "Call"],
        "EXPIRE_DT": ["2030-01-01"] * 3 + ["2030-02-01"],
        "STRIKE_PX": [100, 100, 200, 100], "PX_LAST": [1] * 4, "IVOL": [30] * 4,
    }).to_csv(path, index=False)
    bonds = pd.DataFrame({"CV_COMMON_TICKER_EXCH": ["AAA", "NONE"],
                          "CV_CNVS_PX": [100, 100], "MATURITY": ["2030-01-01"] * 2})
    result = add_csv_benchmarks(bonds, path)
    assert result.BENCHMARK_ID.iloc[0] == "match"
    assert pd.isna(result.BENCHMARK_ID.iloc[1])
