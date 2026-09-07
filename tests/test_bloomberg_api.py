import sys
from types import SimpleNamespace

import pandas as pd

from server.bloomberg_api import execute_bql


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
