import pandas as pd
import sys
from types import SimpleNamespace

import server.benchmarks as benchmarks_module
from server.benchmarks import build_benchmark_query, get_benchmark_options


def test_benchmark_fields_merge_by_id_before_selecting_first_row(monkeypatch):
    import polars as pl
    from polars_bloomberg import BqlResult
    from desktop.results import select_display_columns

    raw = BqlResult([
        pl.DataFrame({"ID": ["option-1"], "name()": ["Example call"],
                      "DATE": [None]}, schema_overrides={"DATE": pl.String}),
        pl.DataFrame({"ID": ["option-1"], "px_last()": [12.5],
                      "DATE": ["2026-09-10"]}),
        pl.DataFrame({"ID": ["option-1"], "strike_px()": [100.],
                      "DATE": ["2026-09-09"]}),
    ], ["name()", "px_last()", "strike_px()"])
    assert raw.combine().height > 1
    # Include all requested fields, including valid null optional values.
    for name in benchmarks_module.BENCHMARK_RESULT_COLUMNS:
        if name not in {"ID", "NAME", "PX_LAST", "STRIKE_PX"}:
            raw.names.append(name)
            raw.dataframes.append(pl.DataFrame({"ID": ["option-1"], name: [None]}))

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bql(self, query):
            return raw

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    bonds = pd.DataFrame([{"CV_COMMON_TICKER_EXCH": "AAA US Equity",
                           "CV_CNVS_PX": 100., "MATURITY": "2030-01-01"}])
    enriched = get_benchmark_options(bonds)
    enriched.attrs.update(bond_universe="convertible", include_benchmarks=True)
    displayed = select_display_columns(enriched)
    assert displayed.loc[0, "BENCHMARK_NAME"] == "Example call"
    assert displayed.loc[0, "BENCHMARK_PX_LAST"] == 12.5
    assert displayed.loc[0, "BENCHMARK_STRIKE_PX"] == 100.


def test_builds_option_query_for_conversion_price_and_maturity():
    query = build_benchmark_query(
        "AAA US Equity",
        100.0,
        "2030-01-01",
    )

    assert "options('AAA US Equity')" in query
    assert "strike_px() >= 90" in query
    assert "strike_px() <= 110" in query
    get_fields = query.split("get(", 1)[1].split("\n)", 1)[0]
    assert [field.strip() for field in get_fields.split(",")] == [
        "name()", "expire_dt()", "strike_px()", "px_last()",
    ]
    assert "expire_dt() - 2030-01-01" in query


def test_null_benchmark_fields_are_preserved_without_filtering(monkeypatch):
    import polars as pl
    from polars_bloomberg import BqlResult
    fields = list(benchmarks_module.BENCHMARK_RESULT_COLUMNS[1:])
    raw = BqlResult([
        pl.DataFrame({"ID": ["option-1"], name: [None]}) for name in fields
    ], fields)

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bql(self, query):
            return raw

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    bonds = pd.DataFrame([{"CV_COMMON_TICKER_EXCH": "AAA US Equity",
                           "CV_CNVS_PX": 100., "MATURITY": "2030-01-01"}])
    enriched = get_benchmark_options(bonds)
    assert enriched.loc[0, "BENCHMARK_ID"] == "option-1"
    for field in fields:
        assert pd.isna(enriched.loc[0, f"BENCHMARK_{field}"])


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

    def fake_execute_bql(query, requested_columns=None, **kwargs):
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
        lambda _query, requested_columns=None, **kwargs: pd.DataFrame([{"NAME": "AAA call"}]),
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
        lambda _query, requested_columns=None, **kwargs: pd.DataFrame(columns=["NAME"]),
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

    def fail_lookup(_query, requested_columns=None, **kwargs):
        raise RuntimeError("Bloomberg unavailable")

    monkeypatch.setattr(benchmarks_module, "execute_bql", fail_lookup)

    enriched = get_benchmark_options(results)

    assert enriched.loc[0, "BENCHMARK_ERROR"] == "Bloomberg unavailable"
