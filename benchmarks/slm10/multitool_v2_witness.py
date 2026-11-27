"""Replay public requests through a read-only synthetic service without an oracle."""

from collections import Counter
from copy import deepcopy

from jsonschema import Draft202012Validator

from benchmarks.tool_calling_v2.oracle import decode_object
from evaluation.aeve.runtime import canonical


class Scenario:
    def __init__(self, public, world):
        self.records, self.event = world["records"], world["event"]
        self.schemas = {name: Draft202012Validator(definition["parameters"])
                        for name, definition in public["tools"].items()}
        self.attempts = Counter()
        self.pending, self.consent = None, None
        self.delivered = []

    def read(self, tool, arguments, turn, call_id):
        if tool not in self.schemas or not self.schemas[tool].is_valid(arguments):
            raise ValueError("tool or argument is out of contract")
        if tool in ("read_public_excerpt", "read_redaction_guide"):
            required = "permitted" if tool == "read_public_excerpt" else "withheld"
            if self.consent is None or self.consent[0] >= turn or self.consent[1:] != (required, arguments["ref"]):
                raise ValueError("guide access lacks prior consent evidence")
        locator = canonical(arguments).decode()
        key = (tool, locator)
        attempt = self.attempts[key]
        series = self.records.get(tool, {}).get(locator, ())
        if attempt >= len(series):
            raise ValueError("unknown read or exhausted retry schedule")
        self.attempts[key] += 1
        result = deepcopy(series[attempt])
        if tool == "read_consent":
            self.consent = (turn, result["decision"], result["guide_ref"]) if "decision" in result else None
        if self.event and tool == self.event["after_tool"]:
            self.pending = {"event_id": self.event["event_id"], "after_call_id": call_id,
                            "before_turn": turn + 1, "message": self.event["message"]}
        return result, locator

    def take_event(self, turn):
        if self.pending is None or self.pending["before_turn"] != turn:
            raise ValueError("moderation does not match the triggering observation")
        event, self.pending = self.pending, None
        self.delivered.append(event)
        return event


def parse_message(message):
    _, sep, data = message.rpartition("\nDATA ")
    if not sep:
        raise ValueError("public input lacks the structured request")
    return decode_object(data)


class Reference:
    def __init__(self, scenario):
        self.scenario = scenario
        self.calls = []
        self._turn = 0

    def read(self, tool, arguments, *, sources=None):
        call_id = f"witness-{len(self.calls) + 1}"
        result, locator = self.scenario.read(tool, arguments, self._turn, call_id)
        links = {argument: {"action_id": source[0], "call_id": source[1], "key": source[2]}
                 for argument, source in (sources or {}).items()}
        self.calls.append({"call_id": call_id, "completion_id": f"witness-turn-{self._turn}", "turn": self._turn,
                           "tool": tool, "arguments_raw": canonical(arguments).decode(), "observation": result,
                           "observation_sources": links, "observation_locator": locator})
        return result

    def advance(self):
        self._turn += 1

    def batch(self, tool, args):
        values = []
        for index, arguments in enumerate(args):
            if index and index % 16 == 0:
                self.advance()
            if tool is None:
                name, arguments = arguments
            else:
                name = tool
            values.append(self.read(name, arguments))
        self.advance()
        return values

    def linked(self, tool, ref, key):
        identity = self.calls[-1]["call_id"]
        action_id = f"step-{len(self.calls)}"
        return self.read(tool, {"ref": ref}, sources={"ref": (action_id, identity, key)})

    def follow(self, result):
        while result.get("next_ref"):
            self.advance()
            result = self.linked(result["next_tool"], result["next_ref"], "next_ref")
        return result


def _solve(public, ref):
    if "targets" in public:
        targets = public["targets"]
        readings = ref.batch(None, [(target["tool"], {"ref": target["ref"]}) for target in targets])
        return {"values": {target["ref"]: reading["value"] for target, reading in zip(targets, readings, strict=True)}}
    if "start" in public:
        start = public["start"]
        terminal = ref.follow(ref.read(start["tool"], {"ref": start["ref"]}))
        return {"label": terminal["label"]}
    if "collections" in public:
        names = public["collections"]
        archived = ref.batch("read_archive_total", [{"ref": name} for name in names])
        live = ref.read("read_live_totals", {"refs": names})["counts"]
        conflicts = [name for name, old in zip(names, archived, strict=True) if old["units"] != live[name]]
        return {"total": sum(live[name] for name in names), "conflicts": conflicts}
    if "gate" in public:
        gate = ref.read("read_maintenance_gate", {"ref": public["gate"]})
        tool, field = ("read_open_route", "main_ref") if gate["open"] else ("read_bypass_route", "bypass_ref")
        ref.advance()
        terminal = ref.follow(ref.linked(tool, gate[field], field))
        return {"destination": terminal["destination"]}
    if "captions" in public:
        source = ref.batch("read_caption", [{"ref": key} for key in public["captions"]])
        return ref.read("preview_caption", {"preview": {"entries": [entry["entry"] for entry in source],
                                                       "preserve_order": True, "format": public["format"]}})
    if "primary" in public:
        initial = ref.read("read_image_source", {"ref": public["primary"]})
        ref.advance()
        if initial["status"] == "retryable":
            secondary = ref.read("read_image_source", {"ref": public["primary"]})
        else:
            secondary = ref.linked("read_alternate_source", initial["mirror_ref"], "mirror_ref")
        return {"checksum": ref.follow(secondary)["checksum"]}
    if "booking" in public:
        ref.read("read_booking", {"ref": public["booking"]})
        ref.advance()
        update = parse_message(ref.scenario.take_event(ref._turn)["message"])
        features = ref.batch("read_venue_access", [{"venue": update["venue"], "ref": key} for key in update["refs"]])
        return {"venue": update["venue"],
                "features": {key: result["feature"] for key, result in zip(update["refs"], features, strict=True)}}
    if "consent" in public:
        consent = ref.read("read_consent", {"ref": public["consent"]})
        while "next_ref" in consent:
            ref.advance()
            consent = ref.linked("read_consent", consent["next_ref"], "next_ref")
        ref.advance()
        tool = {"permitted": "read_public_excerpt", "withheld": "read_redaction_guide"}[consent["decision"]]
        guide = ref.linked(tool, consent["guide_ref"], "guide_ref")
        return {"decision": consent["decision"], "note": guide["note"]}
    raise ValueError("unrecognized public workflow")


def witness(public, world):
    scenario = Scenario(public, world)
    reference = Reference(scenario)
    answer = _solve(parse_message(public["message"]), reference)
    return {"complete": True, "calls": reference.calls, "answer": answer, "events": scenario.delivered}
