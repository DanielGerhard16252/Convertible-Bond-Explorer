import re

from shared.models import (
    BondSearchQuery,
    CreditRating,
    SearchField,
    SearchFilter,
    SearchOperator,
)


RATING_PATTERN = re.compile(
    r"\b(?:AAA|AA\+|AA-|AA|A\+|A-|A|"
    r"BBB\+|BBB-|BBB|BB\+|BB-|BB|"
    r"B\+|B-|B|CCC\+|CCC-|CCC|CC|C|D)\b",
    re.IGNORECASE,
)


def interpret_request(text: str) -> BondSearchQuery:
    match = RATING_PATTERN.search(text)

    if match is None:
        raise ValueError("No supported credit rating found")

    rating = CreditRating(match.group(0).upper())

    return BondSearchQuery(
        filters=[
            SearchFilter(
                field=SearchField.CREDIT_RATING,
                operator=SearchOperator.EQUAL,
                value=rating,
            )
        ]
    )