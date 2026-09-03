import pytest

from server.bql_compiler import compile_query
from server.interpreter import interpret_request
from shared.models import BondSearchQuery


def test_compiles_required_convertible_corporate_universe():
    bql = compile_query(BondSearchQuery(filters=[]))

    assert bql == (
        "GET(SECURITY_DES, BB_COMPOSITE, PX_LAST, CPN, MATURITY, CRNCY, "
        "DELTA, YIELD(YIELD_TYPE=YTM), LONG_COMP_NAME) "
        "FOR(filter(bondsuniv('active',"
        "CONSOLIDATEDUPLICATES='N'),"
        "SRCH_ASSET_CLASS == 'Corporates' AND CONVERTIBLE == 'Y' AND "
        "AMT_OUTSTANDING >= 50000000))"
    )


def test_compiles_single_credit_rating():    
    query = interpret_request(
        "Show me convertible bonds rated BBB"
    )

    bql = compile_query(query)

    assert "BB_COMPOSITE IN ['BBB']" in bql


def test_compiles_missing_credit_rating():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "credit_rating",
                    "operator": "in",
                    "value": ["NR"],
                }
            ]
        }
    )

    assert (
        "(BB_COMPOSITE IN ['NR', 'N.A'] OR BB_COMPOSITE == NA)"
        in compile_query(query)
    )


def range_query(field, minimum=None, maximum=None):
    return BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": field,
                    "operator": "between",
                    "value": (
                        {"minimum": minimum, "maximum": maximum}
                        if minimum is not None or maximum is not None
                        else None
                    ),
                }
            ]
        }
    )


def test_compiles_new_numeric_filters():
    expected_fields = {
        "delta": "DELTA",
        "yield_to_maturity": "YIELD(YIELD_TYPE=YTM)",
    }
    for field, bql_field in expected_fields.items():
        bql = compile_query(range_query(field, 1.5, 5.5))
        assert f"{bql_field} >= 1.5" in bql
        assert f"{bql_field} <= 5.5" in bql


def test_omits_unsupported_conversion_premium_from_bql():
    bql = compile_query(range_query("conversion_premium", 10, 30))

    assert "CNV_PREM" not in bql


def test_compiles_country_filter():
    query = BondSearchQuery.model_validate({"filters": [
        {"field": "country", "operator": "equals", "value": "fr"},
    ]})

    bql = compile_query(query)

    assert "CNTRY_OF_RISK == 'FR'" in bql


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("convertible", "CONVERTIBLE == 'Y'"),
        ("high_yield", "BB_COMPOSITE IN ['BB+'"),
        (
            "convertible_or_high_yield",
            "(CONVERTIBLE == 'Y' OR BB_COMPOSITE IN ['BB+'",
        ),
    ],
)
def test_compiles_bond_universe(value, expected):
    query = BondSearchQuery.model_validate({"filters": [{
        "field": "bond_universe",
        "operator": "equals",
        "value": value,
    }]})

    assert expected in compile_query(query)


def test_compiles_amount_outstanding_in_usd_millions():
    bql = compile_query(range_query("amount_outstanding", 75, 250))

    assert "AMT_OUTSTANDING >= 75000000" in bql
    assert "AMT_OUTSTANDING <= 250000000" in bql


def test_defaults_amount_outstanding_to_fifty_million():
    bql = compile_query(BondSearchQuery(filters=[]))

    assert "AMT_OUTSTANDING >= 50000000" in bql


def test_merges_high_yield_universe_with_selected_ratings():
    query = BondSearchQuery.model_validate({"filters": [
        {
            "field": "bond_universe",
            "operator": "equals",
            "value": "high_yield",
        },
        {
            "field": "credit_rating",
            "operator": "in",
            "value": ["A", "BBB", "BB+", "BB", "B"],
        },
    ]})

    bql = compile_query(query)

    assert bql.count("BB_COMPOSITE IN") == 1
    assert "BB_COMPOSITE IN ['BB+', 'BB', 'B']" in bql
    assert "'A'" not in bql
    assert "'BBB'" not in bql


def test_compiles_maturity_and_currency_filters():
    query = BondSearchQuery.model_validate({"filters": [
        {"field": "maturity", "operator": "between", "value": {
            "minimum": "2027-01-01", "maximum": "2030-12-31"
        }},
        {"field": "currency", "operator": "equals", "value": "usd"},
    ]})
    bql = compile_query(query)
    assert "MATURITY >= 2027-01-01" in bql
    assert "MATURITY <= 2030-12-31" in bql
    assert "CRNCY == 'USD'" in bql


def test_compiles_minimum_price():
    assert "PX_LAST >= 90" in compile_query(
        range_query("price", minimum=90)
    )


def test_compiles_maximum_price():
    assert "PX_LAST <= 110" in compile_query(
        range_query("price", maximum=110)
    )


def test_compiles_bounded_price():
    bql = compile_query(range_query("price", 90, 110))
    assert "PX_LAST >= 90" in bql
    assert "PX_LAST <= 110" in bql


def test_compiles_exact_price():
    bql = compile_query(range_query("price", 100, 100))
    assert "PX_LAST >= 100" in bql
    assert "PX_LAST <= 100" in bql


def test_compiles_minimum_coupon():
    assert "CPN >= 1.5" in compile_query(
        range_query("coupon", minimum=1.5)
    )


def test_compiles_maximum_coupon():
    assert "CPN <= 4.5" in compile_query(
        range_query("coupon", maximum=4.5)
    )


def test_compiles_bounded_coupon():
    bql = compile_query(range_query("coupon", 1.5, 4.5))
    assert "CPN >= 1.5" in bql
    assert "CPN <= 4.5" in bql


def test_compiles_exact_coupon():
    bql = compile_query(range_query("coupon", 2.5, 2.5))
    assert "CPN >= 2.5" in bql
    assert "CPN <= 2.5" in bql


def test_null_price_and_coupon_compile_to_unfiltered_universe():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {"field": "price", "operator": "between", "value": None},
                {"field": "coupon", "operator": "between", "value": None},
            ]
        }
    )

    bql = compile_query(query)
    assert bql.startswith("GET(")
    assert "FOR(filter(bondsuniv('active'" in bql


def test_compiles_single_issuer_and_escapes_apostrophe():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "issuer",
                    "operator": "equals",
                    "value": "O'Brien Holdings",
                }
            ]
        }
    )

    assert (
        "LONG_COMP_NAME == 'O''Brien Holdings'"
        in compile_query(query)
    )


def test_null_issuer_compiles_to_unfiltered_universe():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {
                    "field": "issuer",
                    "operator": "equals",
                    "value": None,
                }
            ]
        }
    )

    bql = compile_query(query)
    assert bql.startswith("GET(")
    assert "FOR(filter(bondsuniv('active'" in bql
