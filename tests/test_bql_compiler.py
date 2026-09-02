from server.bql_compiler import compile_query
from server.interpreter import interpret_request
from shared.models import BondSearchQuery


def test_compiles_single_credit_rating():    
    query = interpret_request(
        "Show me convertible bonds rated BBB"
    )

    bql = compile_query(query)

    assert "BLOOMBERG_RATING_FIELD IN ['BBB']" in bql


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


def test_compiles_minimum_price():
    assert "BLOOMBERG_PRICE_FIELD >= 90" in compile_query(
        range_query("price", minimum=90)
    )


def test_compiles_maximum_price():
    assert "BLOOMBERG_PRICE_FIELD <= 110" in compile_query(
        range_query("price", maximum=110)
    )


def test_compiles_bounded_price():
    bql = compile_query(range_query("price", 90, 110))
    assert "BLOOMBERG_PRICE_FIELD >= 90" in bql
    assert "BLOOMBERG_PRICE_FIELD <= 110" in bql


def test_compiles_exact_price():
    bql = compile_query(range_query("price", 100, 100))
    assert "BLOOMBERG_PRICE_FIELD >= 100" in bql
    assert "BLOOMBERG_PRICE_FIELD <= 100" in bql


def test_compiles_minimum_coupon():
    assert "BLOOMBERG_COUPON_FIELD >= 1.5" in compile_query(
        range_query("coupon", minimum=1.5)
    )


def test_compiles_maximum_coupon():
    assert "BLOOMBERG_COUPON_FIELD <= 4.5" in compile_query(
        range_query("coupon", maximum=4.5)
    )


def test_compiles_bounded_coupon():
    bql = compile_query(range_query("coupon", 1.5, 4.5))
    assert "BLOOMBERG_COUPON_FIELD >= 1.5" in bql
    assert "BLOOMBERG_COUPON_FIELD <= 4.5" in bql


def test_compiles_exact_coupon():
    bql = compile_query(range_query("coupon", 2.5, 2.5))
    assert "BLOOMBERG_COUPON_FIELD >= 2.5" in bql
    assert "BLOOMBERG_COUPON_FIELD <= 2.5" in bql


def test_null_price_and_coupon_compile_to_unfiltered_universe():
    query = BondSearchQuery.model_validate(
        {
            "filters": [
                {"field": "price", "operator": "between", "value": None},
                {"field": "coupon", "operator": "between", "value": None},
            ]
        }
    )

    assert compile_query(query) == "ACTIVE_CONVERTIBLE_BOND_UNIVERSE"
