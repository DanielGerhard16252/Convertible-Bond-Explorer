"""Canonical Bloomberg column matching shared by retrieval and presentation."""


def column_key(name: str) -> str:
    return "".join(str(name).split()).replace("_", "").casefold().removesuffix("()")
