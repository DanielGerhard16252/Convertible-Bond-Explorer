from pathlib import Path

import pandas as pd

from shared.models import (
    BondSearchQuery,
    SearchField,
)


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "bond_data.csv"
)

BQL_COLUMN_MAP = {
    "security_des": "bond_name",
    "bb_composite": "rating",
    "px_last": "price",
    "cpn": "coupon",
    "long_comp_name": "issuer",
    "maturity": "maturity",
    "crncy": "currency",
    "cnv_prem": "conversion_premium",
    "delta": "delta",
    "yld_ytm_mid": "yield_to_maturity",
}

NUMERIC_FIELDS = {
    SearchField.PRICE,
    SearchField.COUPON,
    SearchField.CONVERSION_PREMIUM,
    SearchField.DELTA,
    SearchField.YIELD_TO_MATURITY,
}
BQL_ONLY_FIELDS = {
    SearchField.COUNTRY,
    SearchField.BOND_UNIVERSE,
    SearchField.AMOUNT_OUTSTANDING,
}


def require_column(dataframe: pd.DataFrame, column: str) -> None:
    if column not in dataframe.columns:
        raise ValueError(f"CSV is missing required column: {column}")


def load_bond_data(
    query: BondSearchQuery,
    data_path: Path = DEFAULT_DATA_PATH,
) -> pd.DataFrame:
    dataframe = pd.read_csv(data_path)

    # Convert headings such as "bond name" to "bond_name".
    normalized_columns = [
        column.strip().lower().replace(" ", "_")
        for column in dataframe.columns
    ]
    dataframe.columns = [
        BQL_COLUMN_MAP.get(column, column)
        for column in normalized_columns
    ]

    required_columns = {
        "bond_name",
        "rating",
        "price",
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(
            f"CSV is missing required columns: {missing}"
        )

    results = dataframe.copy()

    for search_filter in query.filters:
        if search_filter.value is None:
            continue
        if search_filter.field in BQL_ONLY_FIELDS:
            continue

        if search_filter.field == SearchField.CREDIT_RATING:
            require_column(results, "rating")
            ratings = {
                rating.value.upper()
                for rating in search_filter.value
                if rating.value.upper() != "NR"
            }
            include_not_rated = any(
                rating.value.upper() == "NR"
                for rating in search_filter.value
            )
            normalized_ratings = (
                results["rating"].astype("string").str.strip().str.upper()
            )
            rating_matches = normalized_ratings.isin(ratings)
            if include_not_rated:
                rating_matches |= (
                    normalized_ratings.isna()
                    | normalized_ratings.isin({"NR", "N.A", "N/A"})
                )

            results = results[rating_matches]
        elif search_filter.field in NUMERIC_FIELDS:
            column = search_filter.field.value
            require_column(results, column)
            value_range = search_filter.value
            results[column] = pd.to_numeric(
                results[column], errors="coerce"
            )

            if value_range.minimum is not None:
                results = results[results[column] >= value_range.minimum]

            if value_range.maximum is not None:
                results = results[results[column] <= value_range.maximum]
        elif search_filter.field == SearchField.ISSUER:
            require_column(results, "issuer")

            issuer = str(search_filter.value).strip().casefold()
            results = results[
                results["issuer"]
                .astype(str)
                .str.strip()
                .str.casefold()
                == issuer
            ]
        elif search_filter.field == SearchField.CURRENCY:
            require_column(results, "currency")
            currency = str(search_filter.value).strip().upper()
            results = results[
                results["currency"].astype(str).str.strip().str.upper()
                == currency
            ]
        elif search_filter.field == SearchField.MATURITY:
            require_column(results, "maturity")
            date_range = search_filter.value
            results["maturity"] = pd.to_datetime(
                results["maturity"], errors="coerce"
            )

            if date_range.minimum is not None:
                results = results[
                    results["maturity"] >= pd.Timestamp(date_range.minimum)
                ]

            if date_range.maximum is not None:
                results = results[
                    results["maturity"] <= pd.Timestamp(date_range.maximum)
                ]

    return results.reset_index(drop=True)
