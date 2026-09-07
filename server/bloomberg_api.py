import pandas as pd


def execute_bql(query: str) -> pd.DataFrame:
    if not query or not query.strip():
        raise ValueError("BQL query cannot be empty")

    try:
        from polars_bloomberg import BQuery

        with BQuery() as bq:
            result = bq.bql(query)
            combined = result.combine()
            return pd.DataFrame(combined.to_dicts())

    except Exception as exc:
        raise RuntimeError(f"Bloomberg BQL request failed: {exc}") from exc
