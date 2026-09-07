from enum import Enum
from datetime import date
import json

from pydantic import BaseModel, model_validator


class SearchField(str, Enum):
    CREDIT_RATING = "credit_rating"
    PRICE = "price"
    COUPON = "coupon"
    ISSUER = "issuer"
    MATURITY = "maturity"
    CURRENCY = "currency"
    CONVERSION_PREMIUM = "conversion_premium"
    YIELD_TO_MATURITY = "yield_to_maturity"
    COUNTRY = "country"
    BOND_UNIVERSE = "bond_universe"
    AMOUNT_OUTSTANDING = "amount_outstanding"
    ASSET_CLASSES = "asset_classes"

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
    value: list[CreditRating] | list[str] | PriceRange | CouponRange | DateRange | str | None = None

    @model_validator(mode="before")
    @classmethod
    def decode_json_range_string(cls, data):
        if not isinstance(data, dict):
            return data
        value = data.get("value")
        if not isinstance(value, str) or not value.strip().startswith("{"):
            return data

        try:
            decoded_value = json.loads(value)
        except json.JSONDecodeError as error:
            field = data.get("field", "range")
            raise ValueError(
                f"{field} contains an invalid JSON range"
            ) from error

        normalized_data = data.copy()
        normalized_data["value"] = decoded_value
        return normalized_data

    @model_validator(mode="after")
    def validate_value_for_field(self):
        if self.field == SearchField.CREDIT_RATING and self.value is not None:
            if not isinstance(self.value, list):
                raise ValueError("credit_rating requires a list")
            self.value = [CreditRating(rating) for rating in self.value]
        elif self.field == SearchField.COUNTRY and self.value is not None:
            if not isinstance(self.value, list):
                self.value = [str(self.value)]
            self.value = [str(country) for country in self.value]
        elif self.field == SearchField.ASSET_CLASSES and self.value is not None:
            if not isinstance(self.value, list):
                self.value = [str(self.value)]
            allowed = {"Corporates", "Governments", "Municipals"}
            invalid = set(self.value) - allowed
            if invalid:
                raise ValueError(
                    "asset_classes only accepts Corporates, Governments, "
                    "and Municipals"
                )
        elif self.field == SearchField.BOND_UNIVERSE and self.value is not None:
            if self.value not in {"convertible", "high_yield"}:
                raise ValueError(
                    "bond_universe must be convertible or high_yield"
                )
        elif isinstance(self.value, list):
            raise ValueError(f"{self.field.value} does not accept a list")

        numeric_range_fields = {
            SearchField.PRICE,
            SearchField.COUPON,
            SearchField.CONVERSION_PREMIUM,
            SearchField.YIELD_TO_MATURITY,
            SearchField.AMOUNT_OUTSTANDING,
        }
        if self.field in numeric_range_fields and self.value is not None:
            if (
                self.field == SearchField.AMOUNT_OUTSTANDING
                and isinstance(self.value, str)
            ):
                normalized = (
                    self.value.strip().upper().replace(",", "")
                )
                for suffix in ("MM", "M"):
                    if normalized.endswith(suffix):
                        normalized = normalized[:-len(suffix)].strip()
                        break
                try:
                    self.value = PriceRange(minimum=float(normalized))
                except ValueError as error:
                    raise ValueError(
                        "amount_outstanding must be a minimum/maximum range "
                        "in USD millions"
                    ) from error
            elif not isinstance(self.value, (PriceRange, CouponRange)):
                raise ValueError(
                    f"{self.field.value} must contain minimum and maximum values"
                )

        if (
            self.field == SearchField.MATURITY
            and self.value is not None
            and not isinstance(self.value, DateRange)
        ):
            raise ValueError(
                "maturity must contain minimum and maximum dates"
            )
        return self


class BondSearchQuery(BaseModel):
    filters: list[SearchFilter]
    post_analysis: str | None = None
