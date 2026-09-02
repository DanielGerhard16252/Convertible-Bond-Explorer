from pathlib import Path

import pandas as pd

from shared.models import (
    BondSearchQuery,
    SearchField,
    PriceRange,
)


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "bond_data.csv"
)


def load_bond_data(
    query: BondSearchQuery,
    data_path: Path = DEFAULT_DATA_PATH,
) -> pd.DataFrame:
    dataframe = pd.read_csv(data_path)

    # Convert headings such as "bond name" to "bond_name".
    dataframe.columns = [
        column.strip().lower().replace(" ", "_")
        for column in dataframe.columns
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

        if search_filter.field == SearchField.CREDIT_RATING:
            ratings = [
                rating.value.upper()
                for rating in search_filter.value
            ]

            results = results[
                results["rating"]
                .astype(str)
                .str.strip()
                .str.upper()
                .isin(ratings)
            ]
        elif search_filter.field == SearchField.PRICE:
            price_range: PriceRange = search_filter.value

            results["price"] = pd.to_numeric(
                results["price"], errors="coerce")
            
            if price_range.minimum is not None:
                results = results[
                    results["price"] >= price_range.minimum
                ]
                
            if price_range.maximum is not None:
                results = results[
                    results["price"] <= price_range.maximum
                ]
            

    return results.reset_index(drop=True)