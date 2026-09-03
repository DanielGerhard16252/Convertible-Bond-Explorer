from enum import Enum
from datetime import date

from pydantic import BaseModel, Field


class SearchField(str, Enum):
    CREDIT_RATING = "credit_rating"
    PRICE = "price"
    COUPON = "coupon"
    ISSUER = "issuer"
    MATURITY = "maturity"
    CURRENCY = "currency"
    CONVERSION_PREMIUM = "conversion_premium"
    DELTA = "delta"
    YIELD_TO_MATURITY = "yield_to_maturity"
    COUNTRY = "country"
    BOND_UNIVERSE = "bond_universe"
    AMOUNT_OUTSTANDING = "amount_outstanding"

class SearchOperator(str, Enum):
    IN = "in"
    BETWEEN = "between"
    EQUALS = "equals"


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
    NOT_RATED = "NR"

class PriceRange(BaseModel):
    minimum: float | None = None
    maximum: float | None = None

class CouponRange(BaseModel):
    minimum: float | None = None
    maximum: float | None = None


class DateRange(BaseModel):
    minimum: date | None = None
    maximum: date | None = None

class SearchFilter(BaseModel):
    field: SearchField
    operator: SearchOperator
    value: list[CreditRating] | PriceRange | CouponRange | DateRange | str | None = None


class BondSearchQuery(BaseModel):
    filters: list[SearchFilter]
