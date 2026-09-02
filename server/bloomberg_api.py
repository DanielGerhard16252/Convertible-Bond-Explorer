from polars_bloomberg import BQuery
import polars as pl


def execute_bql(query: str) -> pl.DataFrame:
    if not query or not query.strip():
        raise ValueError("BQL query cannot be empty")

    try:
        with BQuery() as bq:
            result = bq.bql(query)
            return result.combine()

    except Exception as exc:
        raise RuntimeError(f"Bloomberg BQL request failed: {exc}") from exc