from shared.models import (
    BondSearchQuery,
    SearchField,
    SearchOperator,
    PriceRange,
    CreditRating,
)


BQL_FIELD_MAP = {
    SearchField.CREDIT_RATING: "BLOOMBERG_RATING_FIELD",
    SearchField.PRICE: "BLOOMBERG_PRICE_FIELD",
}


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
    
        formatted_ratings = ", ".join(
            format_bql_value(rating.value)
            for rating in search_filter.value
        )

        return f"{bql_field} IN [{formatted_ratings}]"
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

    raise ValueError(
        f"Unsupported field: {search_filter.field}"
    )

def compile_query(query: BondSearchQuery) -> str:
    conditions = []

    for search_filter in query.filters:
        condition = compile_filter(search_filter)

        if condition is not None:
            conditions.append(condition)

    if not conditions:
        return "ACTIVE_CONVERTIBLE_BOND_UNIVERSE"

    filter_expression = " AND ".join(conditions)

    return (
        "FILTER("
        "ACTIVE_CONVERTIBLE_BOND_UNIVERSE, "
        f"{filter_expression}"
        ")"
    )