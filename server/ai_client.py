"""Create AI clients only for explicit requests, and close them afterwards."""

import os

from openai import OpenAI

from shared.config import load_app_environment


def create_client() -> OpenAI:
    load_app_environment()
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("Set OPENAI_API_KEY in the environment or .env to use AI features.")
    return OpenAI(timeout=120.0, max_retries=1)


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "").strip() or "gpt-5.6"
