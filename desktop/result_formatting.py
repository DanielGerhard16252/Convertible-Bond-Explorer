"""Result labels, selection and formatting without Qt dependencies."""

import pandas as pd

from shared.columns import column_key

THREE_DECIMAL_COLUMNS = {
    "parity",
    "cv_pct_premium",
    "conversion_premium",
    "price",
    "px_last",
    "conversion_price",
    "cv_cnvs_px",
    "conversion_ratio",
    "cv_cnvs_ratio",
    "strike_px",
    "benchmark_strike_px",
    "benchmark_px_last",
    "benchmark_ivol",
    "benchmark_cpn",
    "benchmark_yield(yield_type=ytm)",
    "yield_to_maturity",
    "yield_to_worst",
    "yield(yield_type=ytw)",
    "yield(yield_type=ytm)",
}


RESULT_COLUMN_LABELS = {
    "id": "ID",
    "long_comp_name": "Issuer",
    "cv_common_ticker_exch": "Equity ticker",
    "security_typ": "Security type",
    "classification_name(bics,2)": "Sector",
    "payment_rank": "Payment rank",
    "cntry_of_risk": "Risk country",
    "crncy": "Currency",
    "amt_outstanding": "Outstanding",
    "bb_composite": "Credit rating",
    "maturity": "Maturity",
    "px_last": "Price",
    "cv_cnvs_px": "Conversion price",
    "cv_cnvs_ratio": "Conversion ratio",
    "parity": "Parity",
    "cv_pct_premium": "Premium (%)",
    "cpn": "Coupon (%)",
    "yield(yield_type=ytm)": "YTM (%)",
    "yield(yield_type=ytw)": "YTW (%)",
    "delta": "Delta",
    "security_des": "Description",
}


HIGH_YIELD_COLUMN_LABELS = {
    "cast_parent_equity_ticker": "Parent equity ticker",
    "id": "ID",
    "long_comp_name": "Issuer",
    "security_typ": "Security type",
    "classification_name(bics,2)": "Sector",
    "payment_rank": "Payment rank",
    "cntry_of_risk": "Risk country",
    "crncy": "Currency",
    "amt_outstanding": "Outstanding",
    "bb_composite": "Credit rating",
    "maturity": "Maturity",
    "px_last": "Price",
    "cpn": "Coupon (%)",
    "yield(yield_type=ytm)": "YTM (%)",
    "yield(yield_type=ytw)": "YTW (%)",
    "security_des": "Description",
}


BENCHMARK_COLUMN_LABELS = {
    "benchmark_name": "Option name",
    "benchmark_expire_dt": "Option expiry",
    "benchmark_strike_px": "Option strike",
    "benchmark_px_last": "Option price",
    "benchmark_ivol": "Option implied vol",
}


def display_column_labels(dataframe: pd.DataFrame) -> dict[str, str]:
    labels = dict(HIGH_YIELD_COLUMN_LABELS
                  if dataframe.attrs.get("bond_universe") == "high_yield"
                  else RESULT_COLUMN_LABELS)
    if dataframe.attrs.get("include_benchmarks"):
        labels.update(BENCHMARK_COLUMN_LABELS)
    return labels


def select_display_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Match Bloomberg mnemonics or friendly headings without guessing fields."""
    labels = display_column_labels(dataframe)

    key = column_key

    available = {}
    for column in dataframe.columns:
        available.setdefault(key(column), []).append(column)
    selected = []
    renamed = {}
    for field, label in labels.items():
        aliases = {key(field), key(label)}
        if field.startswith("benchmark_"):
            aliases.add(key("Benchmark " + label))
        if field == "security_typ":
            aliases.add(key("Security Type"))
        matches = [column for alias in aliases for column in available.get(alias, [])]
        if len(matches) > 1:
            raise ValueError(f"Multiple returned columns match {label}: {matches}")
        if matches:
            selected.append(matches[0])
            renamed[matches[0]] = field.upper()
    if not selected and len(dataframe.columns):
        raise ValueError(f"No recognised result columns. Returned: {list(dataframe.columns)}")
    return dataframe.loc[:, selected].rename(columns=renamed)


def format_table_value(column: str, value) -> str:
    if pd.isna(value):
        return str(value)

    normalized_column = column.casefold().removesuffix("()")
    amount_column = normalized_column.replace("_", "").replace(" ", "")
    if amount_column in {
        "amtoutstanding", "amountoutstanding", "amtout",
        "benchmarkamtoutstanding", "benchmarkamountoutstanding",
    }:
        try:
            return f"{float(value):,.0f}"
        except (TypeError, ValueError, OverflowError):
            return str(value)
    if normalized_column in THREE_DECIMAL_COLUMNS:
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    date_column = normalized_column.replace("_", "").replace(" ", "").removesuffix("()")
    if date_column not in {"maturity", "benchmarkexpiredt"}:
        return str(value)

    try:
        maturity = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError):
        return str(value)
    return (
        str(value)
        if pd.isna(maturity)
        else maturity.strftime("%m-%d-%Y")
    )
