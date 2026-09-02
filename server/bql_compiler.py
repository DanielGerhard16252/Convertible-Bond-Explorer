from shared.models import (
    BondSearchQuery,
    SearchField,
    SearchOperator,
)


BQL_FIELD_MAP = {
    SearchField.CREDIT_RATING: "BLOOMBERG_RATING_FIELD",
}


def format_bql_value(value: str) -> str:
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def compile_filter(search_filter) -> str:
    if search_filter.operator != SearchOperator.EQUAL:
        raise ValueError(
            f"Unsupported operator: {search_filter.operator}"
        )

    bql_field = BQL_FIELD_MAP[search_filter.field]

    return (
        f"{bql_field} == "
        f"{format_bql_value(search_filter.value.value)}"
    )


def compile_query(query: BondSearchQuery) -> str:
    conditions = [
        compile_filter(search_filter)
        for search_filter in query.filters
    ]

    filter_expression = " AND ".join(conditions)

    return (
        "FILTER("
        "ACTIVE_CONVERTIBLE_BOND_UNIVERSE, "
        f"{filter_expression}"
        ")"
    )