from shared.models import CreditRating
from pydantic import BaseModel, model_validator


RATING_ORDER = [
    CreditRating.AAA,
    CreditRating.AA_PLUS,
    CreditRating.AA,
    CreditRating.AA_MINUS,
    CreditRating.A_PLUS,
    CreditRating.A,
    CreditRating.A_MINUS,
    CreditRating.BBB_PLUS,
    CreditRating.BBB,
    CreditRating.BBB_MINUS,
    CreditRating.BB_PLUS,
    CreditRating.BB,
    CreditRating.BB_MINUS,
    CreditRating.B_PLUS,
    CreditRating.B,
    CreditRating.B_MINUS,
    CreditRating.CCC_PLUS,
    CreditRating.CCC,
    CreditRating.CCC_MINUS,
    CreditRating.CC,
    CreditRating.C,
    CreditRating.D,
]


class CreditRatingCriteria(BaseModel):
    minimum: CreditRating | None = None
    maximum: CreditRating | None = None
    selected_ratings: list[CreditRating] | None = None

    @model_validator(mode="after")
    def validate_selection(self):
        has_range = (
            self.minimum is not None
            or self.maximum is not None
        )

        has_selection = self.selected_ratings is not None

        if has_range and has_selection:
            raise ValueError(
                "Use either a rating range or selected ratings, not both."
            )

        return self


