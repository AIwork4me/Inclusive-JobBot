"""Build portable SDK observations while retaining exact private captures."""

from hashlib import sha256

from scripts.tools.scan_sensitive import identity_patterns


LOCAL_IDENTITIES = identity_patterns()


def redact_text(value):
    for label, pattern in LOCAL_IDENTITIES.items():
        replacement = "Users/<REDACTED>" if label in {"user_path", "bash_user_path"} else "<REDACTED>"
        value = pattern.sub(replacement, value)
    return value


def portable(value):
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if not isinstance(value, dict):
        return value
    result = {key: portable(item) for key, item in value.items()
              if key not in {"prompt_token_ids", "sampled_bytes_hex", "pre_parser_bytes_hex", "private_response_hex"}}
    if "prompt_token_ids" in value:
        result["prompt_token_ids_publication"] = "omitted because token IDs can contain private prompt paths"
    for key in ("sampled_bytes_hex", "pre_parser_bytes_hex"):
        if key in value:
            raw = bytes.fromhex(value[key])
            text = raw.decode("utf-8", errors="surrogateescape")
            redacted = redact_text(text)
            result[key] = redacted.encode("utf-8", errors="surrogateescape").hex()
            if redacted != text:
                result.pop("sampled_token_ids", None)
                result[key + "_original_sha256"] = sha256(raw).hexdigest()
    return result
