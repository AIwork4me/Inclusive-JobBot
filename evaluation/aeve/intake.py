"""Build model-blind evaluation packets from normalized archived evidence."""
import gzip
import json

from .controller import judge_job
from .runtime import selected_judges

DIMENSIONS = {
    "D01": "Did the candidate identify the user's objective?",
    "D02": "Did it identify the requested business entities correctly?",
    "D03": "Did it respect the stated constraints?",
    "D04": "Did it identify which required information is missing?",
    "D05": "Is the candidate's substantive answer supported by the request and observed facts?",
    "D06": "Are the proposed subtasks suitable for the objective?",
    "D07": "Are all necessary subgoals covered?",
    "D08": "Are the planned dependencies valid?",
    "D09": "Are the conditional plan branches correct based on information available at planning time?",
    "D10": "Did it correctly revise its plan after an observed change?",
    "D11": "Did the proposal stop or seek clarification under the correct conditions?",
    "D12": "Can the proposed plan actually execute under the public contracts?",
    "D13": "Did the candidate select tools suitable for the task and available at the time?",
    "D14": "Were its tool arguments correct and grounded in available information?",
    "D15": "Did the candidate correctly interpret the actual tool results?",
    "D16": "Did actual calls satisfy multi-tool dependencies?",
    "D17": "Did the candidate recover correctly from the observed error?",
    "D18": "Did actual execution respect the stated budget?",
    "D19": "Was the required initial plan protocol followed?",
    "D20": "Was the final output protocol satisfied?",
    "D21": "Did native tool calls satisfy the wire protocol?",
    "D22": "Does observed evidence establish the required business outcome?",
    "D23": "Is the observed persisted state correct for the requested outcome?",
    "D24": "Were authorization, scope and external confirmation requirements respected?",
    "D25": "Does evidence establish strict end-to-end success across all required layers?",
}
ALIASES = {"semantic_correctness": "D05", "tool_selection": "D13", "argument_correctness": "D14"}


def seed_history(db, path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf8") as stream, db:
        for line in stream:
            row = json.loads(line)
            family = row["source_family"]
            if not family or family.lower() in {"unknown","unresolved"}:
                continue
            panel = selected_judges(family)
            events = [{"id": e["id"], "kind": e["kind"], "value": e["content"]} for e in row["events"]]
            for dimension in row["dimensions"]:
                dim = ALIASES.get(dimension, dimension)
                packet = {"task": DIMENSIONS[dim], "dimension": dim, "events": events}
                for candidate in panel[:2]:
                    judge_job(db, "history", row["trial_id"], candidate, packet)
