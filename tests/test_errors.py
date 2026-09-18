from shared.errors import is_no_results, short_error


def test_error_display_omits_diagnostics_and_limits_length():
    assert short_error("Connection failed\n\nDiagnostics:\nraw response") == "Connection failed"
    assert len(short_error("Error " * 1000)) <= 160
    assert "\n" not in short_error("First line\nSecond line")


def test_empty_bql_response_is_recognized():
    error = "No results found; check BQL token limit not hit\n\nDiagnostics:\nquery"
    assert is_no_results(error)
    assert short_error(error) == "No results found."
    assert not is_no_results("Bloomberg connection failed")
