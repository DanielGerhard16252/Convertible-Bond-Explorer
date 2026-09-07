import pandas as pd

import server.benchmarks as benchmarks_module
from server.benchmarks import build_benchmark_query, get_benchmark_options


def test_builds_option_query_for_conversion_price_and_maturity():
    query = build_benchmark_query(
        "AAA US Equity",
        100.0,
        "2030-01-01",
    )

    assert "options('AAA US Equity')" in query
    assert "strike_px() >= 95" in query
    assert "strike_px() <= 105" in query
    assert "expire_dt() - 2030-01-01" in query


def test_adds_benchmark_columns_to_the_corresponding_bonds(monkeypatch):
    results = pd.DataFrame(
        [
            {
                "CV_COMMON_TICKER_EXCH": "AAA US Equity",
                "CV_CNVS_PX": 100.0,
                "MATURITY": "2030-01-01",
            },
            {
                "CV_COMMON_TICKER_EXCH": "BBB US Equity",
                "CV_CNVS_PX": 50.0,
                "MATURITY": "2032-06-30",
            },
        ],
        index=[8, 3],
    )

    def fake_execute_bql(query):
        name = "AAA call" if "AAA US Equity" in query else "BBB call"
        return pd.DataFrame([{"NAME": name, "STRIKE_PX": 99.0}])

    monkeypatch.setattr(benchmarks_module, "execute_bql", fake_execute_bql)

    enriched = get_benchmark_options(results)

    assert enriched.index.tolist() == [8, 3]
    assert enriched["BENCHMARK_NAME"].tolist() == ["AAA call", "BBB call"]
    assert enriched["BENCHMARK_STRIKE_PX"].tolist() == [99.0, 99.0]


def test_supports_normalized_csv_column_names(monkeypatch):
    results = pd.DataFrame([{
        "cv_common_ticker_exch": "AAA US Equity",
        "cv_cnvs_px": 100.0,
        "maturity": "2030-01-01",
    }])
    monkeypatch.setattr(
        benchmarks_module,
        "execute_bql",
        lambda _query: pd.DataFrame([{"NAME": "AAA call"}]),
    )

    enriched = get_benchmark_options(results)

    assert enriched.loc[0, "BENCHMARK_NAME"] == "AAA call"


def test_keeps_row_when_no_benchmark_is_found(monkeypatch):
    results = pd.DataFrame([{
        "CV_COMMON_TICKER_EXCH": "AAA US Equity",
        "CV_CNVS_PX": 100.0,
        "MATURITY": "2030-01-01",
    }])
    monkeypatch.setattr(
        benchmarks_module,
        "execute_bql",
        lambda _query: pd.DataFrame(columns=["NAME"]),
    )

    enriched = get_benchmark_options(results)

    assert len(enriched) == 1
    assert pd.isna(enriched.loc[0, "BENCHMARK_NAME"])


def test_adds_error_to_the_corresponding_row_when_lookup_fails(monkeypatch):
    results = pd.DataFrame([{
        "CV_COMMON_TICKER_EXCH": "AAA US Equity",
        "CV_CNVS_PX": 100.0,
        "MATURITY": "2030-01-01",
    }])

    def fail_lookup(_query):
        raise RuntimeError("Bloomberg unavailable")

    monkeypatch.setattr(benchmarks_module, "execute_bql", fail_lookup)

    enriched = get_benchmark_options(results)

    assert enriched.loc[0, "BENCHMARK_ERROR"] == "Bloomberg unavailable"
