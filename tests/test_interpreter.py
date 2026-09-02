import pytest

from server.interpreter import interpret_request
from shared.models import CreditRating


def test_interprets_bbb_rating():
    query = interpret_request("Show me convertible bonds rated BBB")

    assert len(query.filters) == 1
    assert query.filters[0].value == [CreditRating.BBB]


def test_rejects_request_without_rating():
    with pytest.raises(ValueError):
        interpret_request("Show me some convertible bonds")