import pandas as pd


def execute_bql(
    query: str,
    requested_columns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    if not query or not query.strip():
        raise ValueError("BQL query cannot be empty")

    try:
        from polars_bloomberg import BQuery

        with BQuery() as bq:
            result = bq.bql(query)
            combined = result.combine()
            dataframe = pd.DataFrame(combined.to_dicts())
            if requested_columns is None:
                return dataframe

            available_columns = {
                str(column).casefold(): column
                for column in dataframe.columns
            }
            selected_columns = [
                available_columns[column.casefold()]
                for column in requested_columns
                if column.casefold() in available_columns
            ]
            return dataframe.loc[:, selected_columns]

    except Exception as exc:
        raise RuntimeError(f"Bloomberg BQL request failed: {exc}") from exc
