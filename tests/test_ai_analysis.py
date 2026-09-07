from types import SimpleNamespace

import pandas as pd
import pytest

import server.ai_analysis as ai_analysis
from server.ai_analysis import build_analysis_instructions, run_post_analysis


def test_analysis_instructions_include_bql_and_dataset_records():
    dataset = pd.DataFrame({"price": [100.0], "rating": ["BBB"]})
    bql = "GET(PX_LAST) FOR('Example Corp')"

    instructions = build_analysis_instructions(dataset, bql)

    assert bql in instructions
    assert "'price': 100.0" in instructions
    assert "'rating': 'BBB'" in instructions
    assert "dataset` is authoritative" in instructions


def test_analysis_instructions_replace_nan_with_none():
    instructions = build_analysis_instructions(
        pd.DataFrame({"price": [float("nan")]}),
        "GET(PX_LAST) FOR(BONDS)",
    )

    assert "'price': None" in instructions


def test_run_post_analysis_returns_response_text(monkeypatch):
    submitted = {}

    class Responses:
        def create(self, **kwargs):
            submitted.update(kwargs)
            return SimpleNamespace(output_text="Bond A has the highest yield.")

    monkeypatch.setattr(
        ai_analysis,
        "client",
        SimpleNamespace(responses=Responses()),
    )
    dataset = pd.DataFrame({"bond": ["Bond A"], "yield": [5.2]})

    result = run_post_analysis(
        "Which bond has the highest yield?",
        dataset,
        "GET(SECURITY_DES) FOR(BONDS)",
    )

    assert result == "Bond A has the highest yield."
    assert submitted["input"] == "Which bond has the highest yield?"
    assert submitted["tools"] == [{"type": "web_search"}]
    assert "'bond': 'Bond A'" in submitted["instructions"]


@pytest.mark.parametrize(
    ("query", "dataset", "bql_query", "message"),
    [
        (
            " ",
            pd.DataFrame({"bond": ["Bond A"]}),
            "GET(ID) FOR(BONDS)",
            "Post-analysis instructions cannot be empty",
        ),
        (
            "Summarise",
            pd.DataFrame(),
            "GET(ID) FOR(BONDS)",
            "There are no filtered results to analyse",
        ),
        (
            "Summarise",
            pd.DataFrame({"bond": ["Bond A"]}),
            " ",
            "Generated BQL context cannot be empty",
        ),
    ],
)
def test_run_post_analysis_validates_inputs(
    query,
    dataset,
    bql_query,
    message,
):
    with pytest.raises(ValueError, match=message):
        run_post_analysis(query, dataset, bql_query)
