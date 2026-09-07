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
    "cntry_of_risk": "country",
    "amt_outstanding": "amount_outstanding",
    "convertible": "convertible",
    "srch_asset_class": "asset_class",
}

NUMERIC_FIELDS = {
    SearchField.PRICE,
    SearchField.COUPON,
    SearchField.CONVERSION_PREMIUM,
    SearchField.YIELD_TO_MATURITY,
}
HIGH_YIELD_RATINGS = {
    "BB+", "BB", "BB-", "B+", "B", "B-",
    "CCC+", "CCC", "CCC-", "CC", "C", "D",
}


def require_column(dataframe: pd.DataFrame, column: str) -> None:
    if column not in dataframe.columns:
        raise ValueError(f"CSV is missing required column: {column}")


def _read_bond_data(data_path: Path) -> pd.DataFrame:
    dataframe = pd.read_csv(data_path)
    dataframe.columns = [
        BQL_COLUMN_MAP.get(column.strip().lower().replace(" ", "_"),
                           column.strip().lower().replace(" ", "_"))
        for column in dataframe.columns
    ]
    return dataframe


def load_bond_data(
    query: BondSearchQuery,
    data_path: Path = DEFAULT_DATA_PATH,
) -> pd.DataFrame:
    dataframe = _read_bond_data(data_path)

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
    universe_filter = next(
        (item for item in query.filters
         if item.field == SearchField.BOND_UNIVERSE and item.value),
        None,
    )
    asset_class_filter = next(
        (item for item in query.filters
         if item.field == SearchField.ASSET_CLASSES and item.value),
        None,
    )
    if universe_filter is not None:
        universe = str(universe_filter.value).strip().casefold()
        asset_classes = (
            {str(value).strip().casefold()
             for value in asset_class_filter.value}
            if asset_class_filter is not None
            else {"corporates"}
        )
        require_column(results, "asset_class")
        normalized_assets = (
            results["asset_class"].astype(str).str.strip().str.casefold()
        )
        normalized_ratings = (
            results["rating"].astype("string").str.strip().str.upper()
        )
        high_yield = (
            normalized_ratings.isin(HIGH_YIELD_RATINGS)
            & normalized_assets.isin(asset_classes)
        )
        require_column(results, "convertible")
        convertible = (
            results["convertible"]
            .astype(str)
            .str.strip()
            .str.upper()
            .isin({"Y", "YES", "TRUE", "1"})
            & normalized_assets.eq("corporates")
        )
        if universe == "high_yield":
            results = results[high_yield]
        elif universe == "convertible":
            results = results[convertible]
        else:
            raise ValueError(f"Unsupported bond universe: {universe}")

    for search_filter in query.filters:
        if search_filter.value is None:
            continue
        if search_filter.field in {
            SearchField.BOND_UNIVERSE,
            SearchField.ASSET_CLASSES,
        }:
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
        elif search_filter.field == SearchField.COUNTRY:
            require_column(results, "country")
            countries = (
                search_filter.value
                if isinstance(search_filter.value, list)
                else [search_filter.value]
            )
            normalized_countries = {
                str(country).strip().upper() for country in countries
            }
            results = results[
                results["country"]
                .astype(str)
                .str.strip()
                .str.upper()
                .isin(normalized_countries)
            ]
        elif search_filter.field == SearchField.AMOUNT_OUTSTANDING:
            require_column(results, "amount_outstanding")
            value_range = search_filter.value
            results["amount_outstanding"] = pd.to_numeric(
                results["amount_outstanding"], errors="coerce"
            )
            if value_range.minimum is not None:
                results = results[
                    results["amount_outstanding"]
                    >= value_range.minimum * 1_000_000
                ]
            if value_range.maximum is not None:
                results = results[
                    results["amount_outstanding"]
                    <= value_range.maximum * 1_000_000
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
