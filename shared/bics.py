"""FI BICS configuration shared by the controls, AI, and query compiler.

Edit BICS_LEVEL_2_VALUES using exact Bloomberg labels, then restart the application.
The UI and AI both use this list; unknown selections are rejected.
Multiple selected Level 2 sectors are ORed (a bond can match any selection).
"""

BICS_LEVEL_2_VALUES = [
    "Banking",
    "Consumer Discretionary Products",
    "Consumer Discretionary Services",
    "Consumer Staple Products",
    "Financial Services",
    "Health Care",
    "Industrial Products",
    "Industrial Services",
    "Insurance",
    "Materials",
    "Media",
    "National",
    "Oil & Gas",
    "Real Estate",
    "Regional & Local",
    "Renewable Energy",
    "Retail & Wholesale - Staples",
    "Retail & Whsle - Discretionary",
    "Software & Tech Services",
    "Supranationals",
    "Tech Hardware & Semiconductors",
    "Telecommunications",
    "Utilities",
]

FI_BICS_FILTERS = {
    "fi_bics_level_2": {
        "label": "Sector",
        "bql_field": "CLASSIFICATION_NAME(BICS,2)",
        "options": BICS_LEVEL_2_VALUES,
    },
}


def configured_options(field: str) -> tuple[str, ...]:
    config = FI_BICS_FILTERS[field]
    return tuple(config["options"]) if config["bql_field"] else ()
