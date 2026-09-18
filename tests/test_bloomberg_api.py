import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from server.bloomberg_api import execute_bql
from server.bloomberg_api import assemble_search_results
from server.bql_compiler import CONVERTIBLE_RESULT_COLUMNS


@pytest.mark.parametrize("fail_during_request", [False, True])
def test_bql_failure_includes_query_and_response_diagnostics(monkeypatch, fail_during_request):
    original = ValueError("No dataframes to combine")
    query = "GET(PX_LAST)\nFOR('XS0000000001 Corp')"

    class EmptyResult:
        names = []
        dataframes = []

        def combine(self, **kwargs):
            raise original

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bql(self, submitted):
            assert submitted == query
            if fail_during_request:
                raise original
            return EmptyResult()

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    with pytest.raises(RuntimeError) as caught:
        execute_bql(query, requested_columns=("ID", "PX_LAST"))
    message = str(caught.value)
    assert message.startswith("No results found; check BQL token limit not hit")
    assert f"BQL request:\n{query}" in message
    assert "exception_type=ValueError" in message
    assert "request_invoked=True" in message
    assert "combine_on=ID" in message
    assert "requested_columns=('ID', 'PX_LAST')" in message
    assert caught.value.__cause__ is original
    if fail_during_request:
        assert "stage=execute BQL" in message
        assert "response_received=False" in message
        assert "dataframe_count=" not in message
    else:
        assert "stage=combine response tables" in message
        assert "response_received=True" in message
        assert "dataframe_count=0" in message
        assert "returned_fields=[]" in message


@pytest.mark.parametrize("response", [
    {"responseExceptions": [{"message": "API access denied", "code": "TEST"}]},
    {"unexpectedEnvelope": {"results": {}}},
])
def test_empty_bql_result_exposes_raw_parser_input(monkeypatch, response):
    from polars_bloomberg import BQuery

    class FakeBQuery(BQuery):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def _create_bql_request(self, expression):
            return expression

        def _send_request(self, request):
            return [response]

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    with pytest.raises(RuntimeError) as caught:
        execute_bql("GET(PX_LAST) FOR('IBM US Equity')")
    message = str(caught.value)
    assert "Raw Bloomberg parser input:" in message
    assert next(iter(response)) in message
    if "responseExceptions" in response:
        assert "API access denied" in message
        assert '"code": "TEST"' in message
    assert "polars_bloomberg_version=" in message
    assert "dataframe_count=0" in message


def test_field_assembly_preserves_values_with_different_security_order():
    import polars as pl
    result = SimpleNamespace(names=["px_last()", "CPN"], dataframes=[
        pl.DataFrame({"ID": ["A", "B"], "px_last()": [100., 90.]}),
        pl.DataFrame({"ID": ["B", "A"], "CPN": [2., 5.]}),
    ])
    actual = assemble_search_results(result, ("ID", "PX_LAST", "CPN")).set_index("ID")
    assert actual.loc["A"].to_dict() == {"PX_LAST": 100., "CPN": 5.}
    assert actual.loc["B"].to_dict() == {"PX_LAST": 90., "CPN": 2.}


@pytest.mark.parametrize("item_name,column_name", [
    ("CV CNVS RATIO", "CV CNVS RATIO"),
    ("CV_CNVS_RATIO", "cv cnvs ratio"),
    ("cv cnvs ratio()", "CV_CNVS_RATIO"),
])
def test_field_assembly_accepts_spaces_in_bloomberg_names(item_name, column_name):
    import polars as pl
    result = SimpleNamespace(names=[item_name], dataframes=[
        pl.DataFrame({"ID": ["bond-1"], column_name: [2.75]}),
    ])
    actual = assemble_search_results(result, ("ID", "CV_CNVS_RATIO"))
    assert actual.to_dict("records") == [{"ID": "bond-1", "CV_CNVS_RATIO": 2.75}]


def test_field_assembly_reports_missing_fields_and_upstream_nulls():
    import polars as pl
    result = SimpleNamespace(names=["PX_LAST"], dataframes=[
        pl.DataFrame({"ID": ["A"], "PX_LAST": [None]}),
    ])
    with pytest.raises(ValueError, match="missing requested fields: CPN"):
        assemble_search_results(result, ("ID", "PX_LAST", "CPN"))
    with pytest.raises(ValueError, match="before merging"):
        assemble_search_results(result, ("ID", "PX_LAST"))


def test_search_joins_fields_by_id_despite_different_or_null_metadata(monkeypatch):
    import polars as pl
    from polars_bloomberg import BqlResult

    raw = BqlResult([
        pl.DataFrame({"ID": ["bond-1"], "LONG_COMP_NAME": ["Example"],
                      "DATE": ["2026-09-07"], "CURRENCY": [None]},
                     schema_overrides={"CURRENCY": pl.String}),
        pl.DataFrame({"ID": ["bond-1"], "PX_LAST": [101.25],
                      "DATE": ["2026-09-08"], "CURRENCY": ["USD"]}),
        pl.DataFrame({"ID": ["bond-1"], "CPN": [3.5],
                      "DATE": [None], "CURRENCY": [None]},
                     schema_overrides={"DATE": pl.String, "CURRENCY": pl.String}),
    ], ["LONG_COMP_NAME", "PX_LAST", "CPN"])
    assert raw.combine().height == 3

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bql(self, query):
            return raw

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    result = execute_bql("GET(LONG_COMP_NAME, PX_LAST, CPN) FOR(BONDS)",
                         requested_columns=("ID", "LONG_COMP_NAME", "PX_LAST", "CPN"))
    assert "DATE" in result.columns
    assert "CURRENCY" in result.columns
    assert result[["ID", "LONG_COMP_NAME", "PX_LAST", "CPN"]].to_dict("records") == [
        {"ID": "bond-1", "LONG_COMP_NAME": "Example", "PX_LAST": 101.25, "CPN": 3.5},
    ]


def test_execute_bql_submits_query_and_converts_combined_result(monkeypatch):
    submitted = []

    class CombinedResult:
        def to_dicts(self):
            return [{"ID": "XS0000000001 Corp", "PX_LAST": 101.25}]

    class BqlResult:
        def combine(self, **kwargs):
            return CombinedResult()

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def bql(self, query):
            submitted.append(query)
            return BqlResult()

    monkeypatch.setitem(
        sys.modules,
        "polars_bloomberg",
        SimpleNamespace(BQuery=FakeBQuery),
    )

    result = execute_bql("GET(PX_LAST) FOR('XS0000000001 Corp')")

    assert submitted == ["GET(PX_LAST) FOR('XS0000000001 Corp')"]
    assert isinstance(result, pd.DataFrame)
    assert result.to_dict("records") == [
        {"ID": "XS0000000001 Corp", "PX_LAST": 101.25}
    ]


def test_execute_bql_retains_metadata_columns(monkeypatch):
    class CombinedResult:
        def to_dicts(self):
            return [{
                "ID": "XS0000000001 Corp",
                "PX_LAST": 101.25,
                "CRNCY": "USD",
                "SECURITY_TYP": "CORP",
                "CNTRY_OF_RISK": "US",
                "AMT_OUTSTANDING": 250000000,
                "PARITY": 95.125,
                "CV_PCT_PREMIUM": 6.438,
                "CURRENCY": None,
                "DATE": "2026-09-07",
            }]

    class BqlResult:
        def combine(self, on=None):
            assert on == "ID"
            return CombinedResult()

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def bql(self, _query):
            return BqlResult()

    monkeypatch.setitem(
        sys.modules,
        "polars_bloomberg",
        SimpleNamespace(BQuery=FakeBQuery),
    )

    result = execute_bql(
        "GET(SECURITY_TYP, CNTRY_OF_RISK, PX_LAST, CRNCY, AMT_OUTSTANDING, PARITY, CV_PCT_PREMIUM) FOR(BONDS)",
        requested_columns=("ID", "SECURITY_TYP", "CNTRY_OF_RISK", "CRNCY",
                           "AMT_OUTSTANDING", "PX_LAST", "PARITY", "CV_PCT_PREMIUM"),
    )

    assert result.to_dict("records") == CombinedResult().to_dicts()
    assert result.iloc[0]["SECURITY_TYP"] == "CORP"
    assert result.iloc[0]["CNTRY_OF_RISK"] == "US"
    assert result.iloc[0]["AMT_OUTSTANDING"] == 250000000
    assert result.iloc[0]["PARITY"] == 95.125
    assert result.iloc[0]["CV_PCT_PREMIUM"] == 6.438


@pytest.mark.parametrize("field_values_only", [False, True])
@pytest.mark.parametrize("empty_tables", [False, True])
def test_empty_bql_returns_requested_error(monkeypatch, field_values_only, empty_tables):
    import polars as pl
    from polars_bloomberg import BqlResult

    result = BqlResult([], []) if empty_tables else BqlResult(
        [pl.DataFrame(schema={"ID": pl.String, "PX_LAST": pl.Float64})],
        ["PX_LAST"],
    )

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bql(self, query):
            return result

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    with pytest.raises(RuntimeError) as caught:
        execute_bql("GET(PX_LAST) FOR(BONDS)", ("ID", "PX_LAST"),
                    field_values_only=field_values_only)
    assert str(caught.value).splitlines()[0] == "No results found; check BQL token limit not hit"
