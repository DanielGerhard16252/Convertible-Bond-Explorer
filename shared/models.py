from enum import Enum
from datetime import date
import json
import math

from pydantic import BaseModel, Field, model_validator
from shared.search_choices import categorical_filters, configured_options


class SearchField(str, Enum):
    CREDIT_RATING = "credit_rating"
    PRICE = "price"
    COUPON = "coupon"
    ISSUER = "issuer"
    ISIN = "isin"
    MATURITY = "maturity"
    CURRENCY = "currency"
    CONVERSION_PREMIUM = "conversion_premium"
    YIELD_TO_MATURITY = "yield_to_maturity"
    YIELD_TO_WORST = "yield_to_worst"
    PAYMENT_RANK = "payment_rank"
    COUNTRY = "country"
    BOND_UNIVERSE = "bond_universe"
    AMOUNT_OUTSTANDING = "amount_outstanding"
    ASSET_CLASSES = "asset_classes"
    FI_BICS_LEVEL_2 = "fi_bics_level_2"

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
        if self.value is not None:
            if self.field in {SearchField.CURRENCY, SearchField.COUNTRY}:
                allowed_operators = {SearchOperator.IN, SearchOperator.EQUALS}
            elif self.field in {SearchField.ISSUER, SearchField.ISIN, SearchField.BOND_UNIVERSE}:
                allowed_operators = {SearchOperator.EQUALS}
            elif self.field in {SearchField.CREDIT_RATING, SearchField.ASSET_CLASSES} or self.field.value in categorical_filters():
                allowed_operators = {SearchOperator.IN}
            else:
                allowed_operators = {SearchOperator.BETWEEN}
            if self.operator not in allowed_operators:
                expected = " or ".join(sorted(op.value.upper() for op in allowed_operators))
                raise ValueError(f"{self.field.value} requires {expected}")
        if self.field.value in categorical_filters():
            if self.operator != SearchOperator.IN:
                raise ValueError(f"{self.field.value} requires IN")
            if self.value is None:
                return self
            if not isinstance(self.value, list):
                raise ValueError(f"{self.field.value} requires a list of configured options")
            allowed = {option.casefold(): option
                       for option in configured_options(self.field.value)}
            selected = []
            for option in self.value:
                canonical = allowed.get(str(option).strip().casefold())
                if canonical is None:
                    raise ValueError(f"Unknown or unconfigured {self.field.value} option: {option}")
                if canonical not in selected:
                    selected.append(canonical)
            self.value = selected or None
            return self
        if self.field == SearchField.ISIN and self.value is not None:
            import re
            if not isinstance(self.value, str):
                raise ValueError("isin requires one 12-character ISIN")
            self.value = self.value.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", self.value):
                raise ValueError("isin requires two letters, nine letters/digits, and a final digit")
        if self.field == SearchField.CREDIT_RATING and self.value is not None:
            if not isinstance(self.value, list):
                raise ValueError("credit_rating requires a list")
            self.value = [CreditRating(rating) for rating in self.value]
        elif self.field == SearchField.CURRENCY and self.value is not None:
            values = self.value if isinstance(self.value, list) else str(self.value).split(",")
            self.value = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
            if not self.value or any(len(code) != 3 or not code.isascii() or not code.isalpha() for code in self.value):
                raise ValueError("currency requires three-letter codes, for example GBP, EUR, USD")
        elif self.field == SearchField.COUNTRY and self.value is not None:
            if not isinstance(self.value, list):
                self.value = [str(self.value)]
            self.value = [str(country) for country in self.value]
        elif self.field == SearchField.ASSET_CLASSES and self.value is not None:
            if not isinstance(self.value, list):
                self.value = [str(self.value)]
            allowed = {"Corporates", "Governments"}
            invalid = set(self.value) - allowed
            if invalid:
                raise ValueError(
                    "asset_classes only accepts Corporates and Governments"
                )
        elif self.field == SearchField.BOND_UNIVERSE and self.value is not None:
            if not isinstance(self.value, str) or self.value not in {"convertible", "high_yield"}:
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
            SearchField.YIELD_TO_WORST,
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
                        "in millions of the bond currency"
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
        if self.field == SearchField.ISSUER and self.value is not None:
            if not isinstance(self.value, str):
                raise ValueError("issuer requires one issuer name")
            self.value = self.value.strip() or None
        if isinstance(self.value, (PriceRange, CouponRange, DateRange)):
            low, high = self.value.minimum, self.value.maximum
            if not isinstance(self.value, DateRange):
                if any(value is not None and not math.isfinite(value) for value in (low, high)):
                    raise ValueError(f"{self.field.value} requires finite numbers")
            if low is not None and high is not None and low > high:
                raise ValueError(f"{self.field.value} minimum exceeds maximum")
        return self


class BondSearchQuery(BaseModel):
    filters: list[SearchFilter]
    post_analysis: str | None = None
    max_number: int | None = Field(default=None, gt=0, strict=True)

    @model_validator(mode="after")
    def reject_duplicate_filters(self):
        seen = set()
        for item in self.filters:
            if item.value is None:
                continue
            if item.field in seen:
                raise ValueError(f"Duplicate filter: {item.field.value}")
            seen.add(item.field)
        return self

    def find_filter(self, field: SearchField) -> SearchFilter | None:
        """Return the first populated filter for a field."""
        return next(
            (item for item in self.filters if item.field == field and item.value),
            None,
        )

    @property
    def universe(self) -> str:
        selected = self.find_filter(SearchField.BOND_UNIVERSE)
        return str(selected.value).casefold() if selected else "high_yield"
