from server.ai_interpreter import interpret_request_with_ai
from server.bql_compiler import compile_query


query = interpret_request_with_ai(
    "Show me convertible bonds with oiajds credit rating"
)

print(query.model_dump_json(indent=2))

print("\nGenerated BQL:")
print(compile_query(query))