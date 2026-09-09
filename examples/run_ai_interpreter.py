"""Run with python -m examples.run_ai_interpreter [request]."""

import argparse

from server.ai_interpreter import interpret_request_with_ai
from server.bql_compiler import compile_query


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", default="Show me BBB-rated convertible bonds")
    args = parser.parse_args()
    query = interpret_request_with_ai(args.request)
    print(query.model_dump_json(indent=2))
    print("\nGenerated BQL:")
    print(compile_query(query))


if __name__ == "__main__":
    main()
