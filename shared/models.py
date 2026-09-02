from enum import Enum

from pydantic import BaseModel, Field


class SearchField(str, Enum):
    CREDIT_RATING = "credit_rating"


class SearchOperator(str, Enum):
    EQUAL = "equal"


class CreditRating(str, Enum):
    AAA = "AAA"
    AA_PLUS = "AA+"
    AA = "AA"
    AA_MINUS = "AA-"
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    BBB_PLUS = "BBB+"
    BBB = "BBB"
    BBB_MINUS = "BBB-"
    BB_PLUS = "BB+"
    BB = "BB"
    BB_MINUS = "BB-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    CCC_PLUS = "CCC+"
    CCC = "CCC"
    CCC_MINUS = "CCC-"
    CC = "CC"
    C = "C"
    D = "D"


class SearchFilter(BaseModel):
    field: SearchField
    operator: SearchOperator
    value: CreditRating | None = None


class BondSearchQuery(BaseModel):
    filters: list[SearchFilter]