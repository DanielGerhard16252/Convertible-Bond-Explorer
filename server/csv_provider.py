from pathlib import Path

import pandas as pd

from shared.models import (
    BondSearchQuery,
    PriceRange,
    CouponRange,
    SearchField,
)
from shared.ratings import HIGH_YIELD_RATINGS


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
    "id_isin": "isin",
    "maturity": "maturity",
    "crncy": "currency",
    "cnv_prem": "conversion_premium",
    "cv_pct_premium": "conversion_premium",
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


def _filter_universe(results: pd.DataFrame, query: BondSearchQuery) -> pd.DataFrame:
    universe_filter = query.find_filter(SearchField.BOND_UNIVERSE)
    asset_class_filter = query.find_filter(SearchField.ASSET_CLASSES)
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

    return results


def _filter_numeric_range(
    results: pd.DataFrame,
    column: str,
    value_range: PriceRange | CouponRange,
    scale: float = 1,
) -> pd.DataFrame:
    require_column(results, column)
    results = results.copy()
    results[column] = pd.to_numeric(results[column], errors="coerce")
    if value_range.minimum is not None:
        results = results[results[column] >= value_range.minimum * scale]
    if value_range.maximum is not None:
        results = results[results[column] <= value_range.maximum * scale]
    return results


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

    results = _filter_universe(dataframe.copy(), query)

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
        elif search_filter.field in NUMERIC_FIELDS | {SearchField.AMOUNT_OUTSTANDING}:
            scale = 1_000_000 if search_filter.field == SearchField.AMOUNT_OUTSTANDING else 1
            results = _filter_numeric_range(
                results, search_filter.field.value, search_filter.value, scale
            )
        elif search_filter.field == SearchField.ISIN:
            require_column(results, "isin")
            results = results[results["isin"].astype("string").str.strip().str.upper() == search_filter.value]
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
            currencies = search_filter.value
            results = results[
                results["currency"].astype(str).str.strip().str.upper()
                .isin(currencies)
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
