"""Allowed categorical search values shared by the UI, AI and validation."""

from shared.bics import FI_BICS_FILTERS

PAYMENT_RANK_VALUES = (
    "1st lien", "2nd lien", "1.5 Lien", "Jr Subordinated", "Secured",
    "Sr Unsecured", "Unsecured", "Asset Backed", "Sr Non Preferred",
    "Sr Preferred", "Sr Subordinated",
)


def categorical_filters():
    return {**FI_BICS_FILTERS, "payment_rank": {
        "label": "Payment rank", "bql_field": "PAYMENT_RANK",
        "options": PAYMENT_RANK_VALUES,
    }}


def configured_options(field):
    config = categorical_filters()[field]
    return tuple(config["options"]) if config["bql_field"] else ()
