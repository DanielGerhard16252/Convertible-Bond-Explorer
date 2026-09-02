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
    SearchField.CONVERSION_PREMIUM: "CNV_PREM",
    SearchField.DELTA: "DELTA",
    SearchField.YIELD_TO_MATURITY: "YLD_YTM_MID",
}

BQL_GET_FIELDS = (
    "SECURITY_DES, BB_COMPOSITE, PX_LAST, CPN, MATURITY, CRNCY, "
    "CNV_PREM, DELTA, YLD_YTM_MID, LONG_COMP_NAME"
)
BQL_BASE_CONDITIONS = [
    "SRCH_ASSET_CLASS == 'Corporates'",
    "CONVERTIBLE == 'Y'",
    "AMT_OUTSTANDING >= 50000000",
]


def format_bql_value(value: str) -> str:
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def compile_filter(search_filter) -> str | None:
    if not search_filter.value:
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
        SearchField.CONVERSION_PREMIUM,
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

    for search_filter in query.filters:
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
