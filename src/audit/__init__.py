"""Content digests for business evidence."""

import hashlib
import json

from business_tools import encode_state


def content_digest(value):
    stable = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def write_evidence(path, value):
    """Publish a checkpoint atomically using the simulator's exact numbers."""
    temporary = path.with_suffix(".tmp")
    fields = [f"  {encode_state(key)}: {encode_state(item)}" for key, item in value.items()]
    temporary.write_text("{\n" + ",\n".join(fields) + "\n}\n", encoding="utf-8", newline="\n")
    temporary.replace(path)
