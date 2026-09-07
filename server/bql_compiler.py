from shared.models import (
    BondSearchQuery,
    CreditRating,
    SearchField,
    SearchFilter,
    SearchOperator,
)

BQL_FIELD_MAP = {
    SearchField.CREDIT_RATING: "BB_COMPOSITE",
    SearchField.PRICE: "PX_LAST",
    SearchField.COUPON: "CPN",
    SearchField.ISSUER: "LONG_COMP_NAME",
    SearchField.MATURITY: "MATURITY",
    SearchField.CURRENCY: "CRNCY",
    SearchField.YIELD_TO_MATURITY: "YIELD(YIELD_TYPE=YTM)",
    SearchField.COUNTRY: "CNTRY_OF_RISK",
    SearchField.AMOUNT_OUTSTANDING: "AMT_OUTSTANDING",
}

BQL_RESULT_COLUMNS = (
    "ID",
    "SECURITY_DES",
    "CV_COMMON_TICKER_EXCH",
    "CRNCY",
    "INDUSTRY_SECTOR",
    "BB_COMPOSITE",
    "PX_LAST",
    "CV_CNVS_PX",
    "CPN",
    "YIELD(YIELD_TYPE=YTM)",
    "MATURITY",
    "DELTA",
    "LONG_COMP_NAME",
)
BQL_GET_FIELDS = ", ".join(BQL_RESULT_COLUMNS[1:])
HIGH_YIELD_RATINGS = (
    "BB+", "BB", "BB-", "B+", "B", "B-",
    "CCC+", "CCC", "CCC-", "CC", "C", "D",
)
IGNORED_FILTER_FIELDS = {
    SearchField.CONVERSION_PREMIUM,
    SearchField.BOND_UNIVERSE,
    SearchField.ASSET_CLASSES,
}
NUMERIC_RANGE_FIELDS = {
    SearchField.PRICE,
    SearchField.COUPON,
    SearchField.YIELD_TO_MATURITY,
}


def format_bql_value(value: str) -> str:
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def require_operator(
    search_filter: SearchFilter,
    expected_operator: SearchOperator,
) -> None:
    if search_filter.operator != expected_operator:
        raise ValueError(
            f"{search_filter.field.value} requires "
            f"{expected_operator.value.upper()}."
        )


def compile_range(
    bql_field: str,
    minimum,
    maximum,
) -> str | None:
    conditions = []
    if minimum is not None:
        conditions.append(f"{bql_field} >= {minimum}")
    if maximum is not None:
        conditions.append(f"{bql_field} <= {maximum}")
    return f"({' AND '.join(conditions)})" if conditions else None


def find_filter(
    query: BondSearchQuery,
    field: SearchField,
) -> SearchFilter | None:
    return next(
        (
            search_filter
            for search_filter in query.filters
            if search_filter.field == field and search_filter.value
        ),
        None,
    )


def compile_filter(search_filter: SearchFilter) -> str | None:
    if not search_filter.value:
        return None

    # CNV_PREM is not a valid BQL item. Omit conversion premium until a
    # supported Bloomberg expression is selected.
    if search_filter.field in IGNORED_FILTER_FIELDS:
        return None

    bql_field = BQL_FIELD_MAP[search_filter.field]

    if search_filter.field == SearchField.CREDIT_RATING:
        require_operator(search_filter, SearchOperator.IN)
        rating_values = []
        for rating in search_filter.value:
            if rating == CreditRating.NOT_RATED:
                rating_values.extend(["NR", "N.A"])
            else:
                rating_values.append(rating.value)

        formatted_ratings = ", ".join(
            format_bql_value(rating) for rating in rating_values
        )

        rating_condition = f"{bql_field} IN [{formatted_ratings}]"
        if CreditRating.NOT_RATED in search_filter.value:
            rating_condition = (
                f"({rating_condition} OR {bql_field} == NA)"
            )

        return rating_condition
    if search_filter.field in NUMERIC_RANGE_FIELDS:
        require_operator(search_filter, SearchOperator.BETWEEN)
        value_range = search_filter.value
        return compile_range(
            bql_field,
            f"{value_range.minimum:g}"
            if value_range.minimum is not None
            else None,
            f"{value_range.maximum:g}"
            if value_range.maximum is not None
            else None,
        )

    if search_filter.field == SearchField.ISSUER:
        require_operator(search_filter, SearchOperator.EQUALS)
        return f"{bql_field} == {format_bql_value(search_filter.value)}"

    if search_filter.field == SearchField.CURRENCY:
        require_operator(search_filter, SearchOperator.EQUALS)
        return f"{bql_field} == {format_bql_value(search_filter.value.upper())}"

    if search_filter.field == SearchField.COUNTRY:
        if search_filter.operator not in {
            SearchOperator.EQUALS,
            SearchOperator.IN,
        }:
            raise ValueError("country requires EQUALS or IN.")
        countries = (
            search_filter.value
            if isinstance(search_filter.value, list)
            else [search_filter.value]
        )
        formatted_countries = ", ".join(
            format_bql_value(country.upper()) for country in countries
        )
        return f"{bql_field} IN [{formatted_countries}]"

    if search_filter.field == SearchField.AMOUNT_OUTSTANDING:
        require_operator(search_filter, SearchOperator.BETWEEN)
        value_range = search_filter.value
        return compile_range(
            bql_field,
            f"{round(value_range.minimum * 1_000_000):.0f}"
            if value_range.minimum is not None
            else None,
            f"{round(value_range.maximum * 1_000_000):.0f}"
            if value_range.maximum is not None
            else None,
        )

    if search_filter.field == SearchField.MATURITY:
        require_operator(search_filter, SearchOperator.BETWEEN)
        value_range = search_filter.value
        return compile_range(
            bql_field,
            value_range.minimum.isoformat()
            if value_range.minimum is not None
            else None,
            value_range.maximum.isoformat()
            if value_range.maximum is not None
            else None,
        )

    raise ValueError(f"Unsupported field: {search_filter.field}")


def compile_query(query: BondSearchQuery) -> str:
    conditions = []
    universe_filter = find_filter(query, SearchField.BOND_UNIVERSE)
    universe_value = (
        str(universe_filter.value).casefold()
        if universe_filter is not None
        else "convertible"
    )
    asset_class_filter = find_filter(query, SearchField.ASSET_CLASSES)
    asset_classes = (
        asset_class_filter.value
        if asset_class_filter is not None
        else ["Corporates"]
    )
    formatted_asset_classes = ", ".join(
        format_bql_value(asset_class) for asset_class in asset_classes
    )
    high_yield_asset_condition = (
        f"SRCH_ASSET_CLASS IN [{formatted_asset_classes}]"
    )
    credit_filter = find_filter(query, SearchField.CREDIT_RATING)
    high_yield_ratings = list(HIGH_YIELD_RATINGS)
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
    convertible_condition = (
        "(CONVERTIBLE == 'Y' AND "
        "SRCH_ASSET_CLASS == 'Corporates')"
    )
    high_yield_branch = (
        f"({high_yield_condition} AND {high_yield_asset_condition})"
    )
    if universe_value == "high_yield":
        conditions.append(high_yield_branch)
    elif universe_value == "convertible":
        conditions.append(convertible_condition)
    else:
        raise ValueError(f"Unsupported bond universe: {universe_value}")
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
