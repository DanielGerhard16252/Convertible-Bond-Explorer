"""Live bond searches using the shared desktop result contract."""

from server.bloomberg_api import execute_bql
from server.bql_compiler import compile_query, get_result_columns
from server.benchmarks import get_benchmark_options


def search_bql(query, include_benchmarks=False):
    results = execute_bql(
        compile_query(query), requested_columns=get_result_columns(query),
        field_values_only=True,
    )
    include_benchmarks = include_benchmarks and query.universe == "convertible"
    if include_benchmarks and not results.empty:
        results = get_benchmark_options(results)
    results.attrs.update(
        bond_universe=query.universe, include_benchmarks=include_benchmarks,
        data_source="Bloomberg BQL",
    )
    return results
