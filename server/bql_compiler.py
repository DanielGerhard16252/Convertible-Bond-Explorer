from shared.models import (
    BondSearchQuery,
    SearchField,
    SearchOperator,
    PriceRange,
    CouponRange,
    CreditRating,
    DateRange,
)


BQL_FIELD_MAP = {
    SearchField.CREDIT_RATING: "BB_COMPOSITE",
    SearchField.PRICE: "PX_LAST",
    SearchField.COUPON: "CPN",
    SearchField.ISSUER: "LONG_COMP_NAME",
    SearchField.MATURITY: "MATURITY",
    SearchField.CURRENCY: "CRNCY",
    SearchField.DELTA: "DELTA",
    SearchField.YIELD_TO_MATURITY: "YIELD(YIELD_TYPE=YTM)",
    SearchField.COUNTRY: "CNTRY_OF_RISK",
    SearchField.AMOUNT_OUTSTANDING: "AMT_OUTSTANDING",
}

BQL_GET_FIELDS = (
    "SECURITY_DES, BB_COMPOSITE, PX_LAST, CPN, MATURITY, CRNCY, "
    "DELTA, YIELD(YIELD_TYPE=YTM), LONG_COMP_NAME"
)
BQL_BASE_CONDITIONS = [
    "SRCH_ASSET_CLASS == 'Corporates'",
]
HIGH_YIELD_RATINGS = [
    "BB+", "BB", "BB-", "B+", "B", "B-",
    "CCC+", "CCC", "CCC-", "CC", "C", "D",
]


def format_bql_value(value: str) -> str:
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def compile_filter(search_filter) -> str | None:
    if not search_filter.value:
        return None

    # Conversion premium remains available in the temporary CSV data source,
    # but CNV_PREM is not a valid BQL item. Omit it until a supported Bloomberg
    # expression is selected for the target convertible universe.
    if search_filter.field == SearchField.CONVERSION_PREMIUM:
        return None

    if search_filter.field == SearchField.BOND_UNIVERSE:
        return None

    bql_field = BQL_FIELD_MAP[search_filter.field]

    if search_filter.field == SearchField.CREDIT_RATING:
        if search_filter.operator != SearchOperator.IN:
            raise ValueError(
                f"Invalid operator for credit_rating: {search_filter.operator}"
            )
    
        rating_values = []
        include_missing = False
        for rating in search_filter.value:
            if rating == CreditRating.NOT_RATED:
                rating_values.extend(["NR", "N.A"])
                include_missing = True
            else:
                rating_values.append(rating.value)

        formatted_ratings = ", ".join(
            format_bql_value(rating) for rating in rating_values
        )

        rating_condition = f"{bql_field} IN [{formatted_ratings}]"
        if include_missing:
            rating_condition = (
                f"({rating_condition} OR {bql_field} == NA)"
            )

        return rating_condition
    if search_filter.field == SearchField.PRICE:
        if (
            search_filter.operator
            != SearchOperator.BETWEEN
        ):
            raise ValueError(
                "Price requires the BETWEEN operator."
            )

        price_range: PriceRange = search_filter.value
        conditions = []

        if price_range.minimum is not None:
            conditions.append(
                f"{bql_field} >= {price_range.minimum:g}"
            )

        if price_range.maximum is not None:
            conditions.append(
                f"{bql_field} <= {price_range.maximum:g}"
            )

        if not conditions:
            return None

        return f"({' AND '.join(conditions)})"

    if search_filter.field == SearchField.COUPON:
        if (
            search_filter.operator
            != SearchOperator.BETWEEN
        ):
            raise ValueError(
                "Coupon requires the BETWEEN operator."
            )

        coupon_range: CouponRange = search_filter.value
        conditions = []

        if coupon_range.minimum is not None:
            conditions.append(
                f"{bql_field} >= {coupon_range.minimum:g}"
            )

        if coupon_range.maximum is not None:
            conditions.append(
                f"{bql_field} <= {coupon_range.maximum:g}"
            )

        if not conditions:
            return None

        return f"({' AND '.join(conditions)})"

    if search_filter.field == SearchField.ISSUER:
        if search_filter.operator != SearchOperator.EQUALS:
            raise ValueError(
                "Issuer requires the EQUALS operator."
            )

        return f"{bql_field} == {format_bql_value(search_filter.value)}"

    if search_filter.field == SearchField.CURRENCY:
        if search_filter.operator != SearchOperator.EQUALS:
            raise ValueError("Currency requires the EQUALS operator.")
        return f"{bql_field} == {format_bql_value(search_filter.value.upper())}"

    if search_filter.field == SearchField.COUNTRY:
        if search_filter.operator != SearchOperator.EQUALS:
            raise ValueError("country requires EQUALS.")
        return f"{bql_field} == {format_bql_value(search_filter.value.upper())}"

    if search_filter.field == SearchField.AMOUNT_OUTSTANDING:
        if search_filter.operator != SearchOperator.BETWEEN:
            raise ValueError("amount_outstanding requires BETWEEN.")
        value_range = search_filter.value
        conditions = []
        if value_range.minimum is not None:
            conditions.append(
                f"{bql_field} >= {round(value_range.minimum * 1_000_000):.0f}"
            )
        if value_range.maximum is not None:
            conditions.append(
                f"{bql_field} <= {round(value_range.maximum * 1_000_000):.0f}"
            )
        return f"({' AND '.join(conditions)})" if conditions else None

    if search_filter.field == SearchField.MATURITY:
        if search_filter.operator != SearchOperator.BETWEEN:
            raise ValueError("Maturity requires the BETWEEN operator.")
        date_range: DateRange = search_filter.value
        conditions = []
        if date_range.minimum is not None:
            conditions.append(f"{bql_field} >= {date_range.minimum.isoformat()}")
        if date_range.maximum is not None:
            conditions.append(f"{bql_field} <= {date_range.maximum.isoformat()}")
        return f"({' AND '.join(conditions)})" if conditions else None

    if search_filter.field in {
        SearchField.DELTA,
        SearchField.YIELD_TO_MATURITY,
    }:
        if search_filter.operator != SearchOperator.BETWEEN:
            raise ValueError(f"{search_filter.field.value} requires BETWEEN.")
        value_range = search_filter.value
        conditions = []
        if value_range.minimum is not None:
            conditions.append(f"{bql_field} >= {value_range.minimum:g}")
        if value_range.maximum is not None:
            conditions.append(f"{bql_field} <= {value_range.maximum:g}")
        return f"({' AND '.join(conditions)})" if conditions else None

    raise ValueError(
        f"Unsupported field: {search_filter.field}"
    )

def compile_query(query: BondSearchQuery) -> str:
    conditions = BQL_BASE_CONDITIONS.copy()
    universe_filter = next(
        (
            search_filter
            for search_filter in query.filters
            if search_filter.field == SearchField.BOND_UNIVERSE
            and search_filter.value
        ),
        None,
    )
    universe_value = (
        str(universe_filter.value).casefold()
        if universe_filter is not None
        else "convertible"
    )
    credit_filter = next(
        (
            search_filter
            for search_filter in query.filters
            if search_filter.field == SearchField.CREDIT_RATING
            and search_filter.value
        ),
        None,
    )
    high_yield_ratings = HIGH_YIELD_RATINGS
    merge_credit_into_universe = False
    if universe_value == "high_yield" and credit_filter is not None:
        selected_ratings = {
            rating.value for rating in credit_filter.value
        }
        high_yield_ratings = [
            rating
            for rating in HIGH_YIELD_RATINGS
            if rating in selected_ratings
        ]
        merge_credit_into_universe = True

    formatted_high_yield_ratings = ", ".join(
        format_bql_value(rating) for rating in high_yield_ratings
    )
    high_yield_condition = (
        f"BB_COMPOSITE IN [{formatted_high_yield_ratings}]"
    )
    if universe_value == "high_yield":
        conditions.append(high_yield_condition)
    elif universe_value == "convertible_or_high_yield":
        conditions.append(
            f"(CONVERTIBLE == 'Y' OR {high_yield_condition})"
        )
    else:
        conditions.append("CONVERTIBLE == 'Y'")
    if not any(
        search_filter.field == SearchField.AMOUNT_OUTSTANDING
        and search_filter.value
        for search_filter in query.filters
    ):
        conditions.append("AMT_OUTSTANDING >= 50000000")

    for search_filter in query.filters:
        if (
            merge_credit_into_universe
            and search_filter.field == SearchField.CREDIT_RATING
        ):
            continue
        condition = compile_filter(search_filter)

        if condition is not None:
            conditions.append(condition)

    filter_expression = " AND ".join(conditions)
    universe = (
        "filter(bondsuniv('active',CONSOLIDATEDUPLICATES='N'),"
        f"{filter_expression})"
    )

    # BQuery accepts GET/FOR syntax. This is equivalent to passing the
    # universe and requested field list to the Excel BQL function.
    return f"GET({BQL_GET_FIELDS}) FOR({universe})"
