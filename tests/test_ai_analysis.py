import pandas as pd

from server.ai_analysis import (
    analysis_result_to_dataframe,
    build_analysis_instructions,
    execute_analysis_code,
)


def test_executes_analysis_against_a_dataset_copy():
    dataset = pd.DataFrame({"price": [5, 40, 10]})

    result = execute_analysis_code(
        "result = dataset.sort_values('price')",
        dataset,
    )

    assert result["price"].tolist() == [5, 10, 40]
    assert dataset["price"].tolist() == [5, 40, 10]


def test_converts_scalar_dictionary_to_one_table_row():
    dataframe = analysis_result_to_dataframe(
        {"metric": "Average price", "value": 95.5}
    )

    assert dataframe.to_dict("records") == [
        {"metric": "Average price", "value": 95.5}
    ]


def test_converts_series_to_a_table():
    dataframe = analysis_result_to_dataframe(
        pd.Series({"USD": 3, "EUR": 2})
    )

    assert dataframe.columns.tolist() == ["index", "value"]
    assert dataframe["value"].tolist() == [3, 2]


def test_analysis_instructions_include_bql_and_dataset_schema():
    dataset = pd.DataFrame({"price": [100.0], "rating": ["BBB"]})
    bql = "GET(PX_LAST) FOR('Example Corp')"

    instructions = build_analysis_instructions(dataset, bql)

    assert bql in instructions
    assert "- price: float64" in instructions
    assert f"- rating: {dataset['rating'].dtype}" in instructions
    assert "dataset` is authoritative" in instructions
