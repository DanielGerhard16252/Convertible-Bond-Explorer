"""Desktop CSV search with the same query and result contract as BQL.

CSV inputs are active-security snapshots. Amounts are in currency units;
AMT_OUTSTANDING_USD is required for ranking non-USD bonds by size.
"""

from pathlib import Path

import pandas as pd

from server.bql_compiler import compile_query, get_result_columns
from server.csv_provider import BQL_COLUMN_MAP, load_bond_data, require_column
from shared.config import configured_data_path
from shared.models import SearchField, SearchFilter

def add_csv_benchmarks(results, options_path):
    options = pd.read_csv(options_path)
    options.columns = [str(column).strip().upper().removesuffix("()") for column in options.columns]
    fields = ["ID", "NAME", "EXPIRE_DT", "STRIKE_PX", "PX_LAST", "IVOL"]
    for column in ["TICKER", "PUT_CALL", *fields]:
        require_column(options, column)
    options["EXPIRE_DT"] = pd.to_datetime(options["EXPIRE_DT"], errors="coerce")
    for column in ["STRIKE_PX", "PX_LAST", "IVOL"]:
        options[column] = pd.to_numeric(options[column], errors="coerce")
    rows = []
    for ticker, price, maturity in results[["CV_COMMON_TICKER_EXCH", "CV_CNVS_PX", "MATURITY"]].itertuples(index=False, name=None):
        if pd.isna(ticker) or pd.isna(price) or pd.isna(maturity):
            rows.append({})
            continue
        candidates = options[
            options["TICKER"].astype("string").str.strip().eq(str(ticker).strip())
            & options["PUT_CALL"].astype("string").str.casefold().eq("call")
            & options["STRIKE_PX"].between(float(price) * .9, float(price) * 1.1)
            & options["EXPIRE_DT"].notna()
        ]
        if candidates.empty:
            rows.append({})
        else:
            distance = (candidates["EXPIRE_DT"] - pd.Timestamp(maturity)).abs()
            rows.append(candidates.loc[distance.idxmin(), fields].to_dict())
    benchmarks = pd.DataFrame(rows, columns=fields, index=results.index).add_prefix("BENCHMARK_")
    return pd.concat([results, benchmarks], axis=1)


def search_csv(query, include_benchmarks=False, data_path=None, options_path=None):
    # Print the equivalent bond retrieval BQL even while using CSV data.
    print(compile_query(query), flush=True)
    filters = list(query.filters)
    if query.find_filter(SearchField.BOND_UNIVERSE) is None:
        filters.append(SearchFilter(field="bond_universe", operator="equals", value=query.universe))
    if query.find_filter(SearchField.AMOUNT_OUTSTANDING) is None:
        filters.append(SearchFilter(field="amount_outstanding", operator="between", value={"minimum": 50}))
    data_path = Path(data_path or configured_data_path("BOND_CSV_PATH", "search_demo.csv"))
    results = load_bond_data(query.model_copy(update={"filters": filters}), data_path)
    if query.max_number is not None:
        ranking_column = "amt_outstanding_usd"
        if ranking_column not in results.columns:
            require_column(results, "currency")
            if not results["currency"].astype("string").str.upper().eq("USD").all():
                raise ValueError("CSV requires AMT_OUTSTANDING_USD to rank non-USD bonds")
            ranking_column = "amount_outstanding"
        amounts = pd.to_numeric(results[ranking_column], errors="coerce")
        if amounts.isna().any():
            raise ValueError(f"CSV contains missing or invalid {ranking_column} ranking values")
        results = results.assign(_ranking_amount=amounts).sort_values(
            "_ranking_amount", ascending=False, kind="stable"
        ).head(query.max_number).drop(columns="_ranking_amount")
    # Restore Bloomberg field names for the shared tables and analysis.
    renames = {}
    for field in get_result_columns(query):
        source = BQL_COLUMN_MAP.get(field.lower(), field.lower())
        require_column(results, source)
        renames[source] = field
    results = results.rename(columns=renames).reset_index(drop=True)
    results["MATURITY"] = pd.to_datetime(results["MATURITY"], errors="coerce")
    if include_benchmarks and query.universe == "convertible":
        options_path = Path(options_path or configured_data_path("OPTION_CSV_PATH", "option_demo.csv"))
        results = add_csv_benchmarks(results, options_path)
    results.attrs.update(bond_universe=query.universe,
                         include_benchmarks=include_benchmarks and query.universe == "convertible",
                         data_source=f"CSV: {data_path}")
    return results
