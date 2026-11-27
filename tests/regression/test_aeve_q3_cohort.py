from hashlib import sha256

import pytest

from evaluation.aeve import q3_cohort


def row(case, split, family, episode, *, trial=None):
    return {"case_id": case, "partition": split, "template_family": family, "episode": episode,
            "dimension": "D20", "risk": "read", "source_trial_id": trial,
            "source_sha256": "1" * 64, "packet_sha256": sha256(case.encode()).hexdigest(),
            "business_proof_sha256": "3" * 64}


def archived(case="archived"):
    return {case: {"class": "physical_trial", "case_id": "shared-episode", "sources": [
        ["capture.json.gz", "row-1", "1" * 64],
    ]}}


def test_cohort_requires_new_families_and_bound_physical_episodes():
    roster = [row("dev", "development", "old", "old-1"),
              row("new", "sealed_qualification", "new", "new-1"),
              row("trace", "sealed_qualification", "archive-workflow", "human-readable",
                  trial="archived")]
    result = q3_cohort.validate(roster, archived())
    assert result == {"development": 1, "calibration": 0, "sealed_qualification": 2,
                      "qualification_physical_episodes": 1, "qualification_new_template_families": 1}
    with pytest.raises(ValueError, match="bound"):
        q3_cohort.validate(roster, {})


def test_cross_partition_template_and_archived_repeats_are_rejected():
    cases = [row("dev", "development", "old", "old-1"),
             row("q3", "sealed_qualification", "old", "new-2"),
             row("trace", "sealed_qualification", "archive-a", "one", trial="archived")]
    with pytest.raises(ValueError, match="template"):
        q3_cohort.validate(cases, archived())
    cases[1]["template_family"] = "new"
    cases.append(row("repeat", "calibration", "archive-b", "another", trial="repeat"))
    with pytest.raises(ValueError, match="episode"):
        q3_cohort.validate(cases, {**archived(), **archived("repeat")})


def test_an_unsupported_independent_business_proof_cannot_enter_qualification():
    cases = [row("q3", "sealed_qualification", "new", "one"),
             row("trace", "sealed_qualification", "archive-a", "two", trial="archived")]
    cases[0]["business_proof_sha256"] = ""
    with pytest.raises(ValueError, match="business proof"):
        q3_cohort.validate(cases, archived())
