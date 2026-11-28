"""EA03-B — independent reference Oracle for N03 Batch B (C09-C16).

Obligation A (``validate_ground_truth``): is the STORED expected answer
actually correct for the public task? Every field is derived from the
PUBLIC payload (schema / details / instruction / grammar / task_steps /
message / text / candidates / mention / passage / question /
tool_output) under the Batch B handoff contract; stored construction
metadata is CROSS-CHECKED, never the truth authority:

- C09: the record is the public ``details`` projected onto the declared
  flat ``schema`` (canonicalization = projection); per-field type
  conformance (string/integer/boolean/number/enum); a stored record
  with dropped or extra or type-mutated fields cannot validate.
- C10: the document equals the public ``details`` under the declared
  nested schema; the declared exact array cardinality is parsed from
  the PUBLIC instruction ("exactly N item(s)" / zh "恰好包含N个条目")
  and cross-checked against the schema array ``min`` and the actual
  details array length (three-way agreement).
- C11: grammar arity is derived by counting the declared ``<...>``
  placeholders; each public ``task_step`` is translated by an
  independently authored bilingual step table (surface phrase ->
  declared statement); the program is the statements in step order and
  op_count their number; undeclared tokens or arity mismatches are
  structural defects.
- C12: every declared slot value is derived from the public message by
  a typed bilingual extraction table keyed by the PUBLIC schema slot
  names and types (iso-date / hh:mm / number / boolean / enum /
  string); partial derivation is NOT_ESTABLISHED (field-level), never
  promoted to VALID; null is only valid where the message truly does
  not state the slot.
- C13: the mention is parsed for (name, attribute assignments)
  (EN "the X with (k v, k v)" / zh "属性k为v…的那位X"); candidates are
  matched on exact name equality PLUS full attribute agreement; the
  unique match is the truth; zero matches is NOT_ESTABLISHED and
  multiple matches AMBIGUOUS (recency NEVER decides - the public
  instruction says attribute agreement beats recency).
- C14: every numeric field is located in the public text via a
  bilingual anchor table derived from the PUBLIC schema field names;
  comma thousands-forms are normalized; sign preserved; exact value
  (no rounding); integer vs float distinction follows the surface.
- C15: the conversion is recomputed from the factors supplied in the
  public text (arithmetic recomputation); kind derived from the public
  unit vocabulary (currency codes vs physical units); rounding rule as
  declared in the stored alternatives is treated as the pinned
  contract disclosed in the dataset documentation: exact for
  multiplication, 2-decimal rounding for division.
- C16: the answer is recomputed by a typed query over the public
  tool_output, with the query type derived from the PUBLIC question
  text (bilingual); the stale_note field is excluded per the PUBLIC
  instruction; unanswerable questions are NOT_ESTABLISHED.

Obligation B (``evaluate_response``): only VALID ground truth supports
qualified response evaluation; anything else is NOT_EVALUABLE.
Software errors are never model failures.

Independence: imports NOTHING from IJ-NANO production or builder code
(test-enforced in tests/ij_eval_assurance/test_oracle_batch_b.py).
Verdicts: VALID / INVALID / AMBIGUOUS / NOT_ESTABLISHED — never silent
removal.
"""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from .interpreter_b import parse_response as _interp_parse
from .oracle import (GroundTruthResult, GroundTruthVerdict, ResponseResult,
                     ResponseVerdict)

BATCH_B = tuple(f"C{i:02d}" for i in range(9, 17))

_CURRENCIES = ("USD", "EUR", "JPY", "CNY", "GBP")
_PHYS_UNITS = ("kg", "g", "km", "m")


def _num(text: str):
    """Normalize a surface number (comma forms) to int/float."""
    t = str(text).replace(",", "").strip()
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    try:
        v = float(t)
    except ValueError:
        return None
    if v == int(v) and "." not in t and "e" not in t.lower():
        v = int(t)
    return -v if neg else v


# ---------------------------------------------------------------------------
# C09 — flat record extraction
# ---------------------------------------------------------------------------
def _type_ok(kind: str, value) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and \
            not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "enum":
        return isinstance(value, str)
    return False


def _c09(payload: dict, expected: dict) -> GroundTruthResult:
    schema = payload.get("schema") or {}
    details = payload.get("details") or {}
    if not schema or not isinstance(details, dict):
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing schema/details",))
    derived, missing = {}, []
    for key, kind in schema.items():
        if key not in details:
            missing.append(key)
            continue
        if not _type_ok(kind, details[key]):
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED,
                {"record": derived},
                reasons=(f"public details field {key!r} violates declared "
                         f"type {kind!r}",))
        derived[key] = details[key]
    if missing:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, {"record": derived},
            reasons=(f"details missing declared fields: {sorted(missing)}",))
    stored = expected.get("record")
    if stored == derived:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.VALID, {"record": derived},
            verified_fields=tuple(sorted(derived)))
    extra = sorted(set(stored or {}) - set(derived))
    dropped = sorted(set(derived) - set(stored or {}))
    why = []
    if dropped:
        why.append(f"stored record dropped fields: {dropped}")
    if extra:
        why.append(f"stored record has extra fields: {extra}")
    for k in sorted(set(derived) & set(stored or {})):
        if stored[k] != derived[k] or \
                type(stored[k]) is not type(derived[k]):
            why.append(f"record.{k}: stored {stored[k]!r} != derived "
                       f"{derived[k]!r}")
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                             {"record": derived},
                             reasons=tuple(why) or
                             ("stored record != derived record",))


# ---------------------------------------------------------------------------
# C10 — nested document with exact array cardinality
# ---------------------------------------------------------------------------
_C10_COUNT_EN = re.compile(r"exactly (\d+) items?", re.I)
_C10_COUNT_ZH = re.compile(r"恰好包含(\d+)个条目")


def _c10_declared_count(payload: dict):
    instr = payload.get("instruction") or ""
    m = _C10_COUNT_EN.search(instr) or _C10_COUNT_ZH.search(instr)
    return int(m.group(1)) if m else None


def _c10_projection(spec: dict, value):
    """Recursively project ``value`` onto the declared nested schema."""
    if not isinstance(spec, dict):
        return ("opaque", value)
    t = spec.get("type")
    if t == "object":
        fields = spec.get("fields") or {}
        if not isinstance(value, dict):
            return ("bad", "not an object")
        out, why = {}, []
        for k, sub in fields.items():
            if k not in value:
                why.append(f"missing field {k!r}")
                continue
            r = _c10_projection(sub, value[k])
            if r[0] == "bad":
                why.append(f"{k}: {r[1]}")
            else:
                out[k] = r[1]
        return ("bad", "; ".join(why)) if why else ("ok", out)
    if t == "array":
        if not isinstance(value, list):
            return ("bad", "not an array")
        items = []
        for i, el in enumerate(value):
            r = _c10_projection(spec.get("item") or {}, el)
            if r[0] == "bad":
                return ("bad", f"item[{i}]: {r[1]}")
            items.append(r[1])
        return ("ok", items)
    # leaf type
    if not _type_ok(str(t), value):
        return ("bad", f"violates declared type {t!r}")
    return ("ok", value)


def _c10(payload: dict, expected: dict) -> GroundTruthResult:
    schema = payload.get("schema") or {}
    details = payload.get("details") or {}
    declared = _c10_declared_count(payload)
    status, doc = _c10_projection(schema, details)
    if status != "ok":
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"details/schema mismatch: {doc}",))
    derived = {"document": doc}
    # locate the (single) declared array for cardinality cross-checks
    array_counts = []

    def _walk(spec, val):
        if isinstance(spec, dict):
            if spec.get("type") == "array" and isinstance(val, list):
                array_counts.append((len(val), spec.get("min")))
                for el in val:
                    _walk(spec.get("item") or {}, el)
            elif spec.get("type") == "object":
                for k, sub in (spec.get("fields") or {}).items():
                    if k in val:
                        _walk(sub, val[k])

    _walk(schema, details)
    if declared is None:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 derived, reasons=(
                                     "declared cardinality not parseable "
                                     "from public instruction",))
    why = []
    for actual, smin in array_counts:
        if actual != declared:
            why.append(f"details array length {actual} != declared exact "
                       f"count {declared}")
        if smin is not None and smin != declared:
            why.append(f"schema array min {smin} != declared exact count "
                       f"{declared}")
    derived["array_size"] = declared
    stored_doc = expected.get("document")
    stored_size = expected.get("array_size")
    if stored_doc is not None:
        if stored_doc != doc:
            why.append("stored document != projected details")
        else:
            for k in sorted(set(stored_doc) ^ set(doc)) or ():
                pass  # dict equality already covered above
    if stored_size is not None and stored_size != declared:
        why.append(f"stored array_size {stored_size} != declared {declared}")
    if why:
        # projection agreement + cardinality: a mismatch is a defect
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("document", "array_size"))


# ---------------------------------------------------------------------------
# C11 — DSL program derivation
# ---------------------------------------------------------------------------
_STEP_EN = [
    (re.compile(r"^move from (\S+) to (\S+)$"), "MOVE"),
    (re.compile(r"^pick up (\S+)$"), "PICK"),
    (re.compile(r"^scan (\S+)$"), "SCAN"),
    (re.compile(r"^drop (\S+)$"), "DROP"),
    (re.compile(r"^charge at (\S+)$"), "CHARGE"),
]
_STEP_ZH = [
    (re.compile(r"^从(\S+)移动到(\S+)$"), "MOVE"),
    (re.compile(r"^拾取(\S+)$"), "PICK"),
    (re.compile(r"^扫描(\S+)$"), "SCAN"),
    (re.compile(r"^放下(\S+)$"), "DROP"),
    (re.compile(r"^(?:在(\S+))?对接充电$"), "CHARGE"),
]
_STEP_PREFIX = re.compile(r"^\s*step\s*\d+\s*[:：]\s*", re.I)


def _c11(payload: dict, expected: dict) -> GroundTruthResult:
    grammar = payload.get("grammar") or {}
    steps = payload.get("task_steps") or []
    if not grammar or not steps:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing grammar/task_steps",))
    arity = {tok: desc.count("<") for tok, desc in grammar.items()}
    statements, why = [], []
    for raw_step in steps:
        s = _STEP_PREFIX.sub("", str(raw_step)).strip()
        token, args = None, None
        for pat, tok in _STEP_EN + _STEP_ZH:
            m = pat.match(s)
            if m:
                token = tok
                args = [a for a in m.groups() if a]
                break
        if token is None:
            why.append(f"step not derivable: {s!r}")
            continue
        if token not in arity:
            why.append(f"derived token {token!r} not declared in grammar")
            continue
        if len(args) != arity[token]:
            why.append(f"{token} needs {arity[token]} argument(s), step "
                       f"yields {len(args)}: {s!r}")
            continue
        statements.append(" ".join([token] + args))
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 None, reasons=tuple(why))
    derived = {"program": "\n".join(statements),
               "op_count": len(statements)}
    stored_prog = expected.get("program")
    stored_count = expected.get("op_count")
    mismatch = []
    if stored_prog != derived["program"]:
        mismatch.append("stored program != derived program")
    if stored_count != derived["op_count"]:
        mismatch.append(f"stored op_count {stored_count!r} != derived "
                        f"{derived['op_count']!r}")
    if mismatch:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(mismatch))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("program", "op_count"))


# ---------------------------------------------------------------------------
# C12 — slot fill
# ---------------------------------------------------------------------------
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME = re.compile(r"\d{1,2}:\d{2}")


def _c12_string_slot(key: str, msg: str):
    """Bilingual extraction for string slots, keyed by the PUBLIC slot
    name (each slot's surface position is fixed by the family's message
    template, which is public in every case)."""
    k = key.lower()
    if k == "patient":
        m = re.search(r"book\s+(.+?)\s+in\s+", msg, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r"请为(.+?)预约", msg)
        return m.group(1).strip() if m else None
    if k == "department":
        m = re.search(r"\bin\s+(\S+)\s+on\s+", msg, re.I)
        if m:
            return m.group(1).strip()
        # zh: the department name INCLUDES its 科 suffix (皮肤科/心内科
        # are whole names) — derive up to the clause comma, never
        # truncate the suffix
        m = re.search(r"预约([^，,。]+)[，,]", msg)
        return m.group(1).strip() if m else None
    if k == "city":
        m = re.search(r"to\s+([^,]+),", msg, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r"寄往([^，,。]+)[，,]", msg)
        return m.group(1).strip() if m else None
    if k == "room":
        m = re.search(r"room\s+([^,]+?)(?:\s+at\s+\d|,|$)", msg, re.I)
        return m.group(1).strip() if m else None
    if k == "address":
        m = re.search(r"to\s+([^,]+),", msg, re.I)
        return m.group(1).strip() if m else None
    return None


def _c12_typed_slot(key: str, kind: str, msg: str):
    k = key.lower()
    if kind == "iso-date":
        m = _DATE.search(msg)
        return m.group(0) if m else None
    if kind == "hh:mm":
        m = _TIME.search(msg)
        return m.group(0) if m else None
    if kind == "number":
        m = re.search(r"weighs\s+([\d,\.]+)\s*kg", msg, re.I)
        if m:
            return _num(m.group(1))
        m = re.search(r"重([\d,\.]+)公斤", msg)
        return _num(m.group(1)) if m else None
    if kind == "boolean":
        if k == "insured":
            if re.search(r"不保价", msg):
                return False
            if re.search(r"\binsured\b", msg, re.I) or \
                    re.search(r"保价", msg):
                return True
        return None
    if kind == "enum":
        if k == "service":
            m = re.search(r"[（(]([a-z_]+)[)）]", msg)
            if m:                        # canonical form in parentheses
                return m.group(1)
            m = re.search(r"use\s+([a-z_]+)\s+service", msg, re.I)
            return m.group(1).lower() if m else None
        return None
    if kind == "string":
        return _c12_string_slot(key, msg)
    return None


def _c12(payload: dict, expected: dict) -> GroundTruthResult:
    schema = payload.get("schema") or {}
    msg = payload.get("message") or ""
    if not schema or not msg:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing schema/message",))
    derived, unestablished = {}, []
    for key, kind in schema.items():
        v = _c12_typed_slot(key, str(kind), msg)
        if v is None:
            unestablished.append(key)
        else:
            derived[key] = v
    if unestablished:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, {"slots": derived},
            reasons=(f"slot values not independently derivable: "
                     f"{sorted(unestablished)}",),
            unverified_fields=tuple(sorted(unestablished)))
    stored = expected.get("slots") or {}
    why = []
    if set(stored) != set(derived):
        why.append(f"stored slot keys {sorted(stored)} != declared schema "
                   f"{sorted(derived)}")
    for k in sorted(set(stored) & set(derived)):
        if stored[k] != derived[k] or type(stored[k]) is not type(derived[k]):
            why.append(f"slots.{k}: stored {stored[k]!r} != derived "
                       f"{derived[k]!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 {"slots": derived}, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             {"slots": derived},
                             verified_fields=tuple(sorted(derived)))


# ---------------------------------------------------------------------------
# C13 — mention resolution
# ---------------------------------------------------------------------------
_MENTION_EN = re.compile(
    r"the\s+(.+?)\s+with\s*\(([^)]*)\)", re.I)
_MENTION_ZH = re.compile(r"属性(.+?)的那位(.+)")


def _c13_parse_mention(mention: str):
    m = _MENTION_EN.search(mention)
    if m:
        name = m.group(1).strip()
        attrs = {}
        for part in m.group(2).split(","):
            kv = part.strip().split(None, 1)
            if len(kv) == 2:
                attrs[kv[0]] = kv[1].strip()
        return name, attrs
    m = _MENTION_ZH.search(mention)
    if m:
        attrs = {}
        for part in re.split("[、，]", m.group(1)):
            mm = re.match(r"(.+?)为(.+)", part.strip())
            if mm:
                attrs[mm.group(1)] = mm.group(2)
        return m.group(2).strip(), attrs
    # bare-name mention (no attribute parenthetical): resolution is by
    # unique name agreement; articles stripped, attributes empty
    name = mention.strip()
    name = re.sub(r"^the\s+", "", name, flags=re.I).strip()
    name = re.sub(r"^那位", "", name).strip()
    if name:
        return name, {}
    return None, None


def _c13(payload: dict, expected: dict) -> GroundTruthResult:
    mention = payload.get("mention") or ""
    candidates = payload.get("candidates") or []
    name, attrs = _c13_parse_mention(mention)
    if not name or attrs is None:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"mention not parseable: "
                                          f"{mention!r}",))
    matches = []
    for c in candidates:
        if str(c.get("name", "")).strip() != name:
            continue
        ca = c.get("attrs") or {}
        if all(ca.get(k) == v for k, v in attrs.items()):
            matches.append(c.get("id"))
    if len(matches) == 0:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED,
            {"name": name, "attrs": attrs},
            reasons=("no candidate matches the mention attributes",))
    if len(matches) > 1:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.AMBIGUOUS,
            {"name": name, "attrs": attrs, "matches": sorted(matches)},
            reasons=(f"{len(matches)} candidates match; unique attribute "
                     "agreement fails",))
    derived = {"resolution": matches[0], "name": name, "attrs": attrs}
    stored = expected.get("resolution")
    con = expected.get("construction") or {}
    why = []
    if stored != matches[0]:
        why.append(f"stored resolution {stored!r} != derived {matches[0]!r}")
    cmatch = con.get("match") or {}
    if cmatch:
        if cmatch.get("name") != name:
            why.append("construction name != mention name")
        if cmatch.get("attrs") != attrs:
            why.append("construction attrs != mention attrs")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("resolution",))


# ---------------------------------------------------------------------------
# C14 — numeric extraction with anchors
# ---------------------------------------------------------------------------
_ANCHORS = {
    # schema field -> (EN anchor regex, ZH anchor regex); the number is
    # captured group 1 in both. Authored from the public surface forms.
    "credit_usd": (r"credit of (-?[\d,]+(?:\.\d+)?) USD", r"入账(-?[\d,]+(?:\.\d+)?)美元"),
    "fee_eur": (r"fee of (-?[\d,]+(?:\.\d+)?) EUR", r"手续费(-?[\d,]+(?:\.\d+)?)欧元"),
    "adjustment_gbp": (r"adjustment of (-?[\d,]+(?:\.\d+)?) GBP", r"调整项(-?[\d,]+(?:\.\d+)?)英镑"),
    "uptime_delta_pct": (r"changed by (-?[\d,]+(?:\.\d+)?) percent", r"可用率变化(-?[\d,]+(?:\.\d+)?)个百分点"),
    "error_delta": (r"error count delta (-?[\d,]+(?:\.\d+)?)", r"错误数变化(-?[\d,]+(?:\.\d+)?)"),
    "sessions": (r"sessions today (-?[\d,]+(?:\.\d+)?)", r"今日会话数(-?[\d,]+(?:\.\d+)?)"),
    "on_hand": (r"on hand (-?[\d,]+(?:\.\d+)?)", r"库存(-?[\d,]+(?:\.\d+)?)"),
    "reorder_qty": (r"reorder (-?[\d,]+(?:\.\d+)?)", r"补货(-?[\d,]+(?:\.\d+)?)"),
    "defect_count": (r"defects (-?[\d,]+(?:\.\d+)?)", r"缺陷(-?[\d,]+(?:\.\d+)?)"),
}


def _c14(payload: dict, expected: dict) -> GroundTruthResult:
    schema = payload.get("schema") or {}
    text = payload.get("text") or ""
    if not schema or not text:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing schema/text",))
    derived, unestablished = {}, []
    for key in schema:
        en, zh = _ANCHORS.get(key.lower(), (None, None))
        val = None
        for pat in (en, zh):
            if not pat:
                continue
            m = re.search(pat, text)
            if m:
                val = _num(m.group(1))
                break
        if val is None:
            unestablished.append(key)
        else:
            derived[key] = val
    if unestablished:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, {"values": derived},
            reasons=(f"numeric anchors not located for: "
                     f"{sorted(unestablished)}",),
            unverified_fields=tuple(sorted(unestablished)))
    stored = expected.get("values") or {}
    why = []
    if set(stored) != set(derived):
        why.append(f"stored value keys {sorted(stored)} != schema "
                   f"{sorted(derived)}")
    for k in sorted(set(stored) & set(derived)):
        s, d = stored[k], derived[k]
        if isinstance(s, str) or isinstance(s, bool):
            why.append(f"values.{k}: stored is not a number")
        elif float(s) != float(d) or (
                isinstance(s, float) != isinstance(d, float) and
                float(s) != float(d)):
            why.append(f"values.{k}: stored {s!r} != derived {d!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 {"values": derived}, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID,
                             {"values": derived},
                             verified_fields=tuple(sorted(derived)))


# ---------------------------------------------------------------------------
# C15 — unit/currency conversion recomputation
# ---------------------------------------------------------------------------
_CUR_RATE_EN = re.compile(
    r"1\s*(USD)\s*=\s*([\d,\.]+)\s*([A-Z]{3})")
_CUR_RATE_ZH = re.compile(r"1\s*USD\s*=\s*([\d,\.]+)\s*([A-Z]{3})")
_CUR_AMT_EN = re.compile(
    r"Convert\s+([\d,\.]+)\s*([A-Z]{3})\s+to\s+([A-Z]{3})")
_CUR_AMT_ZH = re.compile(r"将\s*([\d,\.]+)\s*([A-Z]{3})\s*兑换为\s*([A-Z]{3})")
_UNIT_EN = re.compile(
    r"Express\s+([\d,\.]+)\s*([a-z]+)\s+in\s+([a-z]+)\s*\(\s*1\s*([a-z]+)"
    r"\s*=\s*([\d,\.]+)\s*([a-z]+)\s*\)")
_UNIT_ZH = re.compile(
    r"将\s*([\d,\.]+)\s*([a-z]+)\s*换算为\s*([a-z]+)\s*[（(]\s*1\s*([a-z]+)"
    r"\s*=\s*([\d,\.]+)\s*([a-z]+)\s*[)）]")


def _round2(x: float):
    return float(Decimal(str(x)).quantize(Decimal("0.01"),
                                          rounding=ROUND_HALF_UP))


def _c15(payload: dict, expected: dict) -> GroundTruthResult:
    text = payload.get("text") or ""
    if not text:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing text",))
    is_currency = any(c in text for c in _CURRENCIES) and \
        not re.search(r"\b(kg|g|km|m)\b", text)
    if is_currency:
        rate = amount = src = tgt = None
        m = _CUR_RATE_EN.search(text)
        if m:
            rate, src = _num(m.group(2)), m.group(3)
        else:
            m = _CUR_RATE_ZH.search(text)
            if m:
                rate, src = _num(m.group(1)), m.group(2)
        m = _CUR_AMT_EN.search(text) or _CUR_AMT_ZH.search(text)
        if m:
            amount, src2, tgt = _num(m.group(1)), m.group(2), m.group(3)
            if src2:
                src = src2
        if rate is None or amount is None or tgt is None:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("currency factors not parseable from public text",))
        if tgt != "USD":
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=(f"conversion to {tgt!r} has no supplied factor",))
        derived = {"conversion": {"value": _round2(amount / rate),
                                  "unit": "USD"},
                   "surface": {"amount": amount, "rate": rate},
                   "kind": "currency"}
    else:
        m = _UNIT_EN.search(text) or _UNIT_ZH.search(text)
        if not m:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("unit factors not parseable from public text",))
        amount, src, tgt, fsrc, factor, ftgt = m.groups()
        amount, factor = _num(amount), _num(factor)
        if src != fsrc or tgt != ftgt:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("declared factor units do not match the "
                         "conversion direction",))
        value = amount * factor
        if value == int(value):
            value = float(value)
        derived = {"conversion": {"value": value, "unit": tgt},
                   "surface": {"amount": amount, "factor": factor},
                   "kind": "units"}
    stored = expected or {}
    con = stored.get("conversion") or {}
    surf = stored.get("surface") or {}
    why = []
    if not con:
        why.append("stored conversion missing")
    else:
        if con.get("unit") != derived["conversion"]["unit"]:
            why.append(f"stored unit {con.get('unit')!r} != derived "
                       f"{derived['conversion']['unit']!r}")
        sv, dv = con.get("value"), derived["conversion"]["value"]
        if not isinstance(sv, (int, float)) or isinstance(sv, bool):
            why.append("stored value is not a number")
        elif abs(float(sv) - float(dv)) > 0.005 + 1e-9:
            why.append(f"stored value {sv!r} != recomputed {dv!r}")
    if stored.get("kind") and stored["kind"] != derived["kind"]:
        why.append(f"stored kind {stored['kind']!r} != derived "
                   f"{derived['kind']!r}")
    if surf:
        for k in ("amount", "rate", "factor"):
            if k in surf and k in derived["surface"] and \
                    float(surf[k]) != float(derived["surface"][k]):
                why.append(f"surface.{k}: stored {surf[k]!r} != derived "
                           f"{derived['surface'][k]!r}")
    if why:
        return GroundTruthResult("", "", GroundTruthVerdict.INVALID,
                                 derived, reasons=tuple(why))
    return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                             verified_fields=("conversion", "surface",
                                              "kind"))


# ---------------------------------------------------------------------------
# C16 — grounded short answer over tool output
# ---------------------------------------------------------------------------
def _c16_query(question: str):
    q = question.strip()
    ql = q.lower()
    if "shipped" in ql or "已发货" in q or "发货" in q:
        return "shipped"
    if "pending" in ql:
        return "pending_id"
    if "最早" in q and ("到达" in q or "eta" in ql):
        return "min_eta"
    if "清算" in q and "总额" in q:
        return "sum_cleared"
    if "total" in ql and "cleared" in ql:
        return "sum_cleared"
    return None


def _c16(payload: dict, expected: dict) -> GroundTruthResult:
    tool = payload.get("tool_output") or {}
    question = payload.get("question") or ""
    if not tool or not question:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("missing tool_output/question",))
    qtype = _c16_query(question)
    if qtype is None:
        return GroundTruthResult(
            "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
            reasons=(f"question type not derivable: {question!r}",),
            unverified_fields=("answer",))
    if qtype == "shipped":
        status = tool.get("status")
        if not isinstance(status, str):
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("live status field absent",))
        ans = "yes" if status.upper() == "SHIPPED" else "no"
    elif qtype == "pending_id":
        pend = [e.get("id") for e in (tool.get("entries") or [])
                if e.get("flag") == "PENDING"]
        if len(pend) == 0:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("no PENDING entry",))
        if len(pend) > 1:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.AMBIGUOUS, None,
                reasons=(f"{len(pend)} PENDING entries",))
        ans = str(pend[0])
    elif qtype == "min_eta":
        etas = [s.get("eta") for s in (tool.get("shipments") or [])
                if s.get("eta")]
        if not etas:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("no shipment etas",))
        ans = min(etas)
    else:                                                    # sum_cleared
        amounts = [e.get("amount") for e in (tool.get("entries") or [])
                   if e.get("flag") == "CLEARED" and
                   isinstance(e.get("amount"), (int, float))]
        if not amounts:
            return GroundTruthResult(
                "", "", GroundTruthVerdict.NOT_ESTABLISHED, None,
                reasons=("no CLEARED amounts",))
        total = sum(amounts)
        ans = str(int(total)) if float(total) == int(total) else str(total)
    derived = {"answer": ans, "query": qtype}
    stored = expected.get("answer")
    if stored is None:
        return GroundTruthResult("", "", GroundTruthVerdict.NOT_ESTABLISHED,
                                 derived, reasons=("no stored answer",))
    sn = str(stored).strip().rstrip("。.").strip()
    dn = str(ans).strip().rstrip("。.").strip()
    numeric_eq = False
    try:
        numeric_eq = float(sn) == float(dn)
    except (ValueError, TypeError):
        pass
    if sn.lower() == dn.lower() or numeric_eq:
        return GroundTruthResult("", "", GroundTruthVerdict.VALID, derived,
                                 verified_fields=("answer",))
    return GroundTruthResult("", "", GroundTruthVerdict.INVALID, derived,
                             reasons=(f"stored answer {stored!r} != "
                                      f"recomputed {ans!r}",))


# ---------------------------------------------------------------------------
# Obligation A dispatch
# ---------------------------------------------------------------------------
_HANDLERS = {"C09": _c09, "C10": _c10, "C11": _c11, "C12": _c12,
             "C13": _c13, "C14": _c14, "C15": _c15, "C16": _c16}


def validate_ground_truth(case: dict, expectation: dict) -> GroundTruthResult:
    """Obligation A: independently validate the STORED Batch B answer."""
    payload = case.get("public_payload") or {}
    expected = (expectation or {}).get("expected")
    prim = case.get("primitive")
    if expected is None:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=("no stored expectation",))
    handler = _HANDLERS.get(prim)
    if handler is None:
        return GroundTruthResult(case.get("case_id", ""), prim,
                                 GroundTruthVerdict.NOT_ESTABLISHED,
                                 reasons=(f"primitive {prim} outside Batch B "
                                          "oracle scope",))
    r = handler(payload, expected)
    return GroundTruthResult(case.get("case_id", ""), prim, r.verdict,
                             r.recomputed, r.reasons, r.verified_fields,
                             r.unverified_fields)


# ---------------------------------------------------------------------------
# Obligation B — reference evaluation of raw responses
# ---------------------------------------------------------------------------
def _norm_answer(x) -> str:
    s = str(x).strip().strip('"').strip("'").strip()
    return s.rstrip("。.").strip()


def _answers_equal(a, b) -> bool:
    na, nb = _norm_answer(a), _norm_answer(b)
    if na.lower() == nb.lower():
        return True
    try:
        return float(na) == float(nb)
    except (ValueError, TypeError):
        return False


def _compare(prim: str, payload: dict, parsed, truth: dict) -> tuple:
    """Typed comparison of a reference-parsed value against derived truth."""
    if prim == "C09":
        rec = truth.get("record") or {}
        if not isinstance(parsed, dict):
            return False, ("parsed record is not an object",)
        if set(parsed) != set(rec):
            return False, (f"record fields {sorted(parsed)} != "
                           f"{sorted(rec)}",)
        for k in sorted(rec):
            if parsed[k] != rec[k] or type(parsed[k]) is not type(rec[k]):
                return False, (f"record.{k}: {parsed[k]!r} != {rec[k]!r}",)
        return True, ()
    if prim == "C10":
        doc = truth.get("document") or {}
        size = truth.get("array_size")
        if not isinstance(parsed, dict):
            return False, ("parsed document is not an object",)

        def _arrays(v):
            out = []
            if isinstance(v, dict):
                for k, x in v.items():
                    if isinstance(x, list):
                        out.append(len(x))
                    out.extend(_arrays(x))
            elif isinstance(v, list):
                for x in v:
                    out.extend(_arrays(x))
            return out

        if parsed != doc:
            return False, ("document != projected details",)
        counts = _arrays(parsed)
        if size is not None and any(c != size for c in counts):
            return False, (f"array cardinality {counts} != declared {size}",)
        return True, ()
    if prim == "C11":
        prog = truth.get("program") or ""
        want = [ln for ln in prog.splitlines() if ln.strip()]
        got = [str(s) for s in (parsed or [])]
        if got != want:
            return False, (f"program lines {got!r} != {want!r}",)
        return True, ()
    if prim == "C12":
        slots = truth.get("slots") or {}
        if not isinstance(parsed, dict):
            return False, ("parsed slots not an object",)
        if set(parsed) != set(slots):
            return False, (f"slot keys {sorted(parsed)} != "
                           f"{sorted(slots)}",)
        for k in sorted(slots):
            if parsed[k] != slots[k] or type(parsed[k]) is not type(slots[k]):
                return False, (f"slots.{k}: {parsed[k]!r} != "
                               f"{slots[k]!r}",)
        return True, ()
    if prim == "C13":
        ids = {str(c.get("id")) for c in payload.get("candidates") or []}
        if str(parsed) not in ids:
            return False, (f"resolution {parsed!r} not a candidate id",)
        return (str(parsed) == truth.get("resolution")), (
            f"resolution {parsed!r} != {truth.get('resolution')!r}",)
    if prim == "C14":
        vals = truth.get("values") or {}
        if not isinstance(parsed, dict):
            return False, ("parsed values not an object",)
        if set(parsed) != set(vals):
            return False, (f"value keys {sorted(parsed)} != {sorted(vals)}",)
        for k in sorted(vals):
            if isinstance(parsed[k], bool) or \
                    not isinstance(parsed[k], (int, float)):
                return False, (f"values.{k} is not a number",)
            if float(parsed[k]) != float(vals[k]):
                return False, (f"values.{k}: {parsed[k]!r} != "
                               f"{vals[k]!r} (no rounding tolerance)",)
        return True, ()
    if prim == "C15":
        con = truth.get("conversion") or {}
        if not isinstance(parsed, dict):
            return False, ("parsed conversion not an object",)
        if parsed.get("unit") != con.get("unit"):
            return False, (f"unit {parsed.get('unit')!r} != "
                           f"{con.get('unit')!r}",)
        pv, tv = parsed.get("value"), con.get("value")
        if isinstance(pv, bool) or not isinstance(pv, (int, float)):
            return False, ("value is not a number",)
        if abs(float(pv) - float(tv)) > 0.005 + 1e-9:
            return False, (f"value {pv!r} != recomputed {tv!r}",)
        return True, ()
    if prim == "C16":
        return _answers_equal(parsed, truth.get("answer")), (
            f"answer {parsed!r} != recomputed {truth.get('answer')!r}",)
    return False, (f"primitive {prim} outside Batch B comparison scope",)


def evaluate_response(case: dict, expectation: dict,
                      response) -> ResponseResult:
    """Obligation B: evaluate a RAW response against derived truth."""
    prim = case.get("primitive", "")
    case_id = case.get("case_id", "")
    try:
        parsed, parse_class, parse_reasons = _interp_parse(
            prim, case.get("public_payload") or {}, response)
    except Exception as exc:                     # software error, never model
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE,
            reasons=(f"interpreter software error: {type(exc).__name__}: "
                     f"{exc}",))
    if parse_class == "EMPTY_OUTPUT":
        return ResponseResult(case_id, prim, ResponseVerdict.EMPTY_OUTPUT,
                              reasons=parse_reasons or ("empty output",))
    try:
        gt = validate_ground_truth(case, expectation)
        if gt.verdict is not GroundTruthVerdict.VALID:
            return ResponseResult(
                case_id, prim, ResponseVerdict.NOT_EVALUABLE, parsed=parsed,
                truth=gt.recomputed,
                reasons=(f"ground truth not independently established "
                         f"({gt.verdict.value}); qualified response "
                         f"evaluation refused",))
        truth = gt.recomputed
        if parse_class != "OK":
            return ResponseResult(case_id, prim, ResponseVerdict.INCORRECT,
                                  parsed=parsed, truth=truth,
                                  reasons=parse_reasons or
                                  ("malformed output",))
        ok, why = _compare(prim, case.get("public_payload") or {},
                           parsed, truth)
        if ok:
            return ResponseResult(case_id, prim, ResponseVerdict.CORRECT,
                                  parsed=parsed, truth=truth)
        return ResponseResult(case_id, prim, ResponseVerdict.INCORRECT,
                              parsed=parsed, truth=truth, reasons=why)
    except Exception as exc:                     # software error, never model
        return ResponseResult(
            case_id, prim, ResponseVerdict.NOT_EVALUABLE, parsed=parsed,
            reasons=(f"reference-path software error: "
                     f"{type(exc).__name__}: {exc}",))
