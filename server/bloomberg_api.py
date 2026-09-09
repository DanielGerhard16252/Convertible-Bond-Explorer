import pandas as pd


def _column_key(name: str) -> str:
    return "".join(str(name).split()).replace("_", "").casefold().removesuffix("()")


def assemble_search_results(result, requested_columns: tuple[str, ...]) -> pd.DataFrame:
    """Extract each item's value column before joining, excluding its metadata."""
    frames = []
    returned = {_column_key(name): (name, frame)
                for name, frame in zip(result.names, result.dataframes)}
    missing = []
    for requested in requested_columns:
        if _column_key(requested) == "id":
            continue
        item = returned.get(_column_key(requested))
        if item is None:
            missing.append(requested)
            continue
        name, frame = item
        columns = {_column_key(column): column for column in frame.columns}
        id_column = columns.get("id")
        value_column = columns.get(_column_key(name))
        if id_column is None or value_column is None:
            raise ValueError(f"Bloomberg field {name} lacks its ID or value column: {frame.columns}")
        values = pd.DataFrame(frame.select([id_column, value_column]).to_dicts(),
                              columns=[id_column, value_column])
        values.columns = ["ID", requested]
        if values["ID"].isna().any() or values["ID"].duplicated().any():
            raise ValueError(f"Bloomberg field {name} contains missing or duplicate security IDs")
        frames.append(values.set_index("ID"))
    if missing:
        returned_tables = "; ".join(
            f"{name}: {list(frame.columns)}"
            for name, frame in zip(result.names, result.dataframes)
        ) or "(no field tables returned)"
        raise ValueError(
            f"Bloomberg response is missing requested fields: {', '.join(missing)}. "
            f"Returned fields and table columns: {returned_tables}"
        )
    if not frames:
        raise ValueError("Bloomberg returned no requested field tables")
    dataframe = pd.concat(frames, axis=1, join="outer").reset_index()
    if not dataframe.empty and dataframe.drop(columns="ID").isna().all().all():
        raise ValueError(
            "Bloomberg field tables contain IDs but all requested values are null "
            "before merging. Inspect the raw API response and library parser."
        )
    return dataframe.loc[:, list(requested_columns)]


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
            # Temporarily retain every returned column for diagnosis, including
            # DATE/CURRENCY metadata. Keep the security-ID join for searches.
            combined = (
                result.combine(on="ID")
                if requested_columns is not None
                else result.combine()
            )
            dataframe = pd.DataFrame(combined.to_dicts())
            return dataframe

    except Exception as exc:
        raise RuntimeError(f"Bloomberg BQL request failed: {exc}") from exc
