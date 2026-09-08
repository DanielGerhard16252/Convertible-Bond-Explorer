import sys
from types import SimpleNamespace

import pandas as pd

from server.bloomberg_api import execute_bql
from server.bql_compiler import BQL_RESULT_COLUMNS


def test_execute_bql_submits_query_and_converts_combined_result(monkeypatch):
    submitted = []

    class CombinedResult:
        def to_dicts(self):
            return [{"ID": "XS0000000001 Corp", "PX_LAST": 101.25}]

    class BqlResult:
        def combine(self):
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


def test_execute_bql_keeps_only_requested_columns(monkeypatch):
    class CombinedResult:
        def to_dicts(self):
            return [{
                "ID": "XS0000000001 Corp",
                "PX_LAST": 101.25,
                "CRNCY": "USD",
                "AMT_OUTSTANDING": 250000000,
                "PARITY": 95.125,
                "CV_PCT_PREMIUM": 6.438,
                "CURRENCY": None,
                "DATE": "2026-09-07",
            }]

    class BqlResult:
        def combine(self):
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
        "GET(PX_LAST, CRNCY, AMT_OUTSTANDING, PARITY, CV_PCT_PREMIUM) FOR(BONDS)",
        requested_columns=BQL_RESULT_COLUMNS,
    )

    assert result.columns.tolist() == [
        "ID", "CRNCY", "AMT_OUTSTANDING", "PX_LAST", "PARITY", "CV_PCT_PREMIUM",
    ]
    assert result.iloc[0]["AMT_OUTSTANDING"] == 250000000
    assert result.iloc[0]["PARITY"] == 95.125
    assert result.iloc[0]["CV_PCT_PREMIUM"] == 6.438
