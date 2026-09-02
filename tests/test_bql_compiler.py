from server.bql_compiler import compile_query
from server.interpreter import interpret_request


def test_compiles_single_credit_rating():    
    query = interpret_request(
        "Show me convertible bonds rated BBB"
    )

    bql = compile_query(query)

    assert "BLOOMBERG_RATING_FIELD IN ['BBB']" in bql