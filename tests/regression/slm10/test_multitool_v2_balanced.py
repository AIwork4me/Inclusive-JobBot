from collections import Counter
from copy import deepcopy
import json

import pytest


@pytest.fixture(scope="module")
def cohort():
    from benchmarks.slm10.multitool_v2_balanced import candidate

    return candidate()


BANDS = ((2, 3), (4, 5), (6, 10), (11, 15), (16, 20))
CATEGORIES = ("parallel", "serial", "aggregation", "conditional", "typed_transfer", "recovery",
              "scope_update", "authorization")
LANGUAGES = ("en", "zh", "mixed")


def test_balanced_roster_covers_all_depths_and_cross_strata(cohort):
    rows, repeats = cohort
    cases = [public for public, _, _ in rows]
    assert len(cases) == len({case["case_id"] for case in cases}) == 600
    assert len({case["message"] for case in cases}) == 600
    assert Counter(case["category"] for case in cases) == dict.fromkeys(CATEGORIES, 75)
    assert Counter(case["language"] for case in cases) == dict.fromkeys(LANGUAGES, 200)
    exact = Counter((case["category"], case["language"], case["required_actions"]) for case in cases)
    assert set(exact) == {(category, language, depth) for category in CATEGORIES
                          for language in LANGUAGES for depth in range(2, 21)}
    assert Counter(case["required_actions"] for case in cases) == {
        depth: 60 if depth <= 5 else 24 for depth in range(2, 21)
    }
    for low, high in BANDS:
        band = [case for case in cases if low <= case["required_actions"] <= high]
        assert len(band) == 120
        assert Counter(case["category"] for case in band) == dict.fromkeys(CATEGORIES, 15)
        assert Counter(case["language"] for case in band) == dict.fromkeys(LANGUAGES, 40)
        assert Counter((case["category"], case["language"]) for case in band) == {
            (category, language): 5 for category in CATEGORIES for language in LANGUAGES
        }
        assert sum(case["case_id"] in repeats for case in band) == 20
    assert all(len(graph["actions"]) == public["required_actions"] for public, _, graph in rows)


def test_shape_rejects_roster_with_unbalanced_short_bands(cohort):
    from benchmarks.slm10.multitool_v2_balanced import shape

    rows, repeats = cohort
    rows = deepcopy(rows)
    source = next(row for row in rows if row[0]["category"] == "parallel" and row[0]["required_actions"] == 2
                  and row[0]["case_id"] not in repeats and row[0]["case_id"].endswith("-1"))
    target = next(row for row in rows if row[0]["category"] == source[0]["category"]
                  and row[0]["language"] == source[0]["language"] and row[0]["required_actions"] == 4)
    source[0]["required_actions"] = 4
    source[2]["actions"] = target[2]["actions"]
    with pytest.raises(ValueError, match="first-trial.*balance"):
        shape(rows, repeats)


def test_balanced_trials_keep_matched_arms_and_get_distinct_replay_identities(cohort):
    from benchmarks.slm10.multitool_v2_balanced import trial_roster
    from benchmarks.slm10.multitool_v2_candidate import candidate as original

    rows, repeats = cohort
    assert len(repeats) == len(set(repeats)) == 100
    assert not {public["case_id"] for public, _, _ in original()[0]} & {public["case_id"] for public, _, _ in rows}
    roster = trial_roster("A", rows, repeats)
    assert len(roster) == len({row["trial_id"] for row in roster}) == 1500
    assert {row["suite"] for row in roster} == {"MULTITOOL-V2/candidate-0.2"}
    assert Counter(row["track"] for row in roster) == {"direct_first": 600, "sdk_first": 600, "sdk_repeat": 300}
    by_track = {track: {row["case_id"]: (row["input_sha256"], row["world_sha256"], row["oracle_sha256"], row["seed"])
                        for row in roster if row["track"] == track} for track in ("direct_first", "sdk_first")}
    assert by_track["direct_first"] == by_track["sdk_first"]
    assert Counter(row["case_id"] for row in roster if row["track"] == "sdk_repeat") == dict.fromkeys(repeats, 3)


def test_balanced_candidate_replays_portable_software_controls_and_reserves_formal_review():
    from benchmarks.slm10.multitool_v2_balanced import FOLDER, files

    outputs, report = files()
    for name, expected in outputs.items():
        assert (FOLDER / name).read_bytes() == expected
    manifest = json.loads(outputs["manifest.json"])
    assert manifest["cohort_strata"]["case_bands"] == {f"{low}-{high}": 120 for low, high in BANDS}
    assert manifest["attributed_physical_trials"] == 0
    assert manifest["formal_dispatch"] == "BLOCKED"
    assert manifest["formal_roster_freeze"] == "NOT_RUN"
    assert report["software_qualification"] == "PASS"
    assert report["independent_witnesses"] == {"PASS": 600, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0}
    assert report["coverage"]["independent_business_and_content_review"] == "NOT_RUN"
    assert report["coverage"]["persisted_authorized_draft"] == "NOT_RUN"
    assert report["physical_execution"] == "NOT_RUN"
    assert {control["status"] for control in report["controls"].values()} == {"PASS"}
    assert {control["status"] for control in report["balanced_controls"].values()} == {"PASS"}
    assert report["balanced_controls"]["reordered_parallel_across_turns"]["observed"] == "PASS"
    assert report["balanced_controls"]["retry_same_turn"]["observed"] == "FAIL"
    assert report["balanced_controls"]["ineligible_consent_branch"]["observed"] == "FAIL"
    assert report["balanced_controls"]["action_budget_exceeded"]["observed"] == "FAIL"
    assert report["balanced_controls"]["missing_call_identity"]["observed"] == "BLOCKED"
