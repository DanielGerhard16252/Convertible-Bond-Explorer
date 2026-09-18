import pandas as pd
import pytest

import server.bql_search as module
from shared.models import BondSearchQuery
from server.bql_compiler import get_result_columns


@pytest.mark.parametrize("universe, benchmarks", [
    ("high_yield", False), ("high_yield", True),
    ("convertible", False), ("convertible", True),
])
def test_live_search_contract(monkeypatch, universe, benchmarks):
    query = BondSearchQuery.model_validate({"filters": [
        {"field": "bond_universe", "operator": "equals", "value": universe},
    ]})
    calls = []
    def execute(bql, **kwargs):
        assert bql == module.compile_query(query)
        assert kwargs == {"requested_columns": get_result_columns(query),
                          "field_values_only": True}
        return pd.DataFrame({"ID": ["bond-1"], "PX_LAST": [101.]})
    def enrich(results):
        calls.append(True)
        return results.assign(BENCHMARK_NAME="Call")
    monkeypatch.setattr(module, "execute_bql", execute)
    monkeypatch.setattr(module, "get_benchmark_options", enrich)
    results = module.search_bql(query, benchmarks)
    expected = benchmarks and universe == "convertible"
    assert bool(calls) == expected
    assert results.attrs == {"bond_universe": universe,
                             "include_benchmarks": expected,
                             "data_source": "Bloomberg BQL"}
    assert results.loc[0, "ID"] == "bond-1"


def test_live_failure_is_propagated(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Bloomberg unavailable")
    monkeypatch.setattr(module, "execute_bql", fail)
    with pytest.raises(RuntimeError, match="Bloomberg unavailable"):
        module.search_bql(BondSearchQuery(filters=[]))
