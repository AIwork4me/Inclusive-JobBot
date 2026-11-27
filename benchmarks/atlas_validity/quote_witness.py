"""Public-input deterministic witness for the TC-V2 holdout quote family."""

import re

CATALOG_ID = re.compile(r"(?<![A-Z0-9-])CAT-[A-Z0-9-]+(?![A-Z0-9-])")


def read_current_quote(prompt, tools, execute):
    """Read the catalog ID in the request and return the current quote fields."""
    catalog_ids = CATALOG_ID.findall(prompt)
    if len(catalog_ids) != 1 or not {"rate", "currency"}.issubset(re.findall(r"[a-z]+", prompt)):
        raise ValueError("unsupported public quote request")
    item_tool = next((tool["function"] for tool in tools if tool["function"]["name"] == "read_item"), None)
    if item_tool is None or item_tool["parameters"]["required"] != ["item_id"]:
        raise ValueError("public catalog tool is unavailable")
    quote = execute(item_tool["name"], {"item_id": catalog_ids[0]})
    if "error" in quote:
        raise ValueError("public catalog lookup failed")
    return {"rate": quote["quoted_rate"], "currency": quote["rate_currency"]}
