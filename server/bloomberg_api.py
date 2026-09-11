import json
from importlib.metadata import PackageNotFoundError, version

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
    *,
    field_values_only: bool = False,
) -> pd.DataFrame:
    if not query or not query.strip():
        raise ValueError("BQL query cannot be empty")

    stage = "import polars_bloomberg"
    request_invoked = False
    response_received = False
    raw_responses = None
    result = None
    try:
        from polars_bloomberg import BQuery

        class DiagnosticBQuery(BQuery):
            def _parse_bql_responses(self, responses):
                # Capture the actual input before the library drops errors or
                # unrecognized envelopes. Keep this scoped to this request.
                nonlocal raw_responses
                raw_responses = responses
                return super()._parse_bql_responses(responses)

        stage = "open Bloomberg session"
        with DiagnosticBQuery() as bq:
            stage = "execute BQL"
            request_invoked = True
            result = bq.bql(query)
            response_received = True
            if field_values_only:
                stage = "extract field values"
                if requested_columns is None:
                    raise ValueError("Field extraction requires requested columns")
                dataframe = assemble_search_results(result, requested_columns)
                stage = "close Bloomberg session"
                return dataframe
            stage = "combine response tables"
            # Temporarily retain every returned column for diagnosis, including
            # DATE/CURRENCY metadata. Keep the security-ID join for searches.
            combined = (
                result.combine(on="ID")
                if requested_columns is not None
                else result.combine()
            )
            stage = "convert response to pandas"
            dataframe = pd.DataFrame(combined.to_dicts())
            stage = "close Bloomberg session"
            return dataframe

    except Exception as exc:
        diagnostics = [
            f"exception_type={type(exc).__name__}",
            f"stage={stage}",
            f"request_invoked={request_invoked}",
            f"response_received={response_received}",
            f"combine_on={'ID' if requested_columns is not None else 'automatic'}",
            f"requested_columns={requested_columns!r}",
        ]
        try:
            diagnostics.append(f"polars_bloomberg_version={version('polars-bloomberg')}")
        except PackageNotFoundError:
            diagnostics.append("polars_bloomberg_version=unknown")
        if raw_responses is not None:
            try:
                raw_text = json.dumps(raw_responses, default=str, ensure_ascii=False)
                limit = 12000
                diagnostics.append(
                    "Raw Bloomberg parser input:\n" + raw_text[:limit]
                    + ("\n[response truncated after 12000 characters]" if len(raw_text) > limit else "")
                )
            except Exception as diagnostic_error:
                diagnostics.append(f"raw_response_diagnostics_unavailable={diagnostic_error}")
        if response_received:
            try:
                frames = getattr(result, "dataframes", None)
                diagnostics.extend([
                    f"returned_fields={getattr(result, 'names', None)!r}",
                    f"dataframe_count={len(frames) if frames is not None else 'unknown'}",
                ])
                if frames is not None:
                    for index, frame in enumerate(frames):
                        diagnostics.append(
                            f"table[{index}]: shape={frame.shape}, columns={frame.columns!r}"
                        )
            except Exception as diagnostic_error:
                diagnostics.append(f"response_diagnostics_unavailable={diagnostic_error}")
        raise RuntimeError(
            f"Bloomberg BQL request failed: {exc}\n\n"
            + "Diagnostics:\n" + "\n".join(diagnostics)
            + f"\n\nBQL request:\n{query}"
        ) from exc
