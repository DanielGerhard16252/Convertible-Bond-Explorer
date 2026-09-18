"""Compact messages suitable for dialogs, status labels, and result cells."""


def is_no_results(error) -> bool:
    message = str(error).split("Diagnostics:", 1)[0].casefold()
    return any(text in message for text in (
        "no results found", "no dataframes to combine", "no options returned",
    ))


def short_error(error) -> str:
    if is_no_results(error):
        return "No results found."
    lines = str(error).strip().splitlines()
    message = " ".join(lines[0].split()) if lines else "Request failed."
    for marker in ("Diagnostics:", "BQL request:"):
        message = message.split(marker, 1)[0].strip()
    return message[:157].rstrip() + "..." if len(message) > 160 else message or "Request failed."
