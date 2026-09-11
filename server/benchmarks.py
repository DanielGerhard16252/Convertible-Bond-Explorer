import pandas as pd

from server.bloomberg_api import execute_bql

BENCHMARK_RESULT_COLUMNS = (
    "ID", "NAME", "EXPIRE_DT", "STRIKE_PX", "PX_LAST",
)

INPUT_COLUMN_ALIASES = {
    "ticker": (
        "CV_COMMON_TICKER_EXCH",
        "cv_common_ticker_exch",
        "common_ticker",
    ),
    "price": ("CV_CNVS_PX", "cv_cnvs_px", "conversion_price"),
    "maturity": ("MATURITY", "maturity"),
}


def _find_input_columns(results: pd.DataFrame) -> dict[str, str]:
    columns = {}
    for value_name, aliases in INPUT_COLUMN_ALIASES.items():
        column = next(
            (alias for alias in aliases if alias in results.columns),
            None,
        )
        if column is None:
            accepted_names = " or ".join(aliases)
            raise ValueError(
                f"Benchmark lookup requires {accepted_names}"
            )
        columns[value_name] = column
    return columns


def build_benchmark_query(ticker: str, price: float, maturity) -> str:
    escaped_ticker = str(ticker).replace("'", "''")
    maturity_date = pd.Timestamp(maturity).date().isoformat()
    return f"""
let(
    #expiry_delta = abs(expire_dt() - {maturity_date});
)
get(
    name(),
    expire_dt(),
    strike_px(),
    px_last()
)
for(
    top(
        filter(
            options('{escaped_ticker}'),
            put_call() == 'Call'
            and strike_px() >= {price * 0.9:g}
            and strike_px() <= {price * 1.1:g}
        ),
        1,
        -#expiry_delta
    )
)
"""


def get_benchmark_options(results: pd.DataFrame) -> pd.DataFrame:
    columns = _find_input_columns(results)
    benchmark_rows = []
    benchmark_columns = set()

    for ticker, price, maturity in results[
        [columns["ticker"], columns["price"], columns["maturity"]]
    ].itertuples(index=False, name=None):
        if pd.isna(ticker) or pd.isna(price) or pd.isna(maturity):
            benchmark_rows.append({})
            continue
        try:
            benchmark = execute_bql(
                build_benchmark_query(ticker, float(price), maturity),
                requested_columns=BENCHMARK_RESULT_COLUMNS,
            )
        except Exception as exc:
            benchmark_columns.add("ERROR")
            benchmark_rows.append({"ERROR": str(exc)})
            continue
        benchmark_columns.update(benchmark.columns)
        benchmark_rows.append(
            benchmark.iloc[0].to_dict() if not benchmark.empty else {}
        )

    benchmark_results = pd.DataFrame(
        benchmark_rows,
        index=results.index,
        columns=sorted(benchmark_columns),
    )
    benchmark_results = benchmark_results.add_prefix("BENCHMARK_")
    return pd.concat([results.copy(), benchmark_results], axis=1)
