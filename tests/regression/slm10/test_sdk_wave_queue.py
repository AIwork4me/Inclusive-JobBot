import json
from pathlib import Path

import pytest

from benchmarks.slm10.sdk_wave_queue import expected_wave, reconcile


def test_wave_directory_does_not_imply_completion(tmp_path):
    expected = expected_wave("A", 0)
    folder = tmp_path / expected["wave"]
    folder.mkdir()
    with pytest.raises(ValueError, match="interrupted legacy wave"):
        reconcile(folder, expected)


def test_reservation_detects_wrong_expected_identity(tmp_path):
    expected = expected_wave("A", 0)
    folder = tmp_path / expected["wave"]
    folder.mkdir()
    (folder / "reservation.json").write_text(json.dumps(expected_wave("B", 0)))
    with pytest.raises(ValueError, match="expected trial identity"):
        reconcile(folder, expected)


def test_legacy_evidence_must_match_scheduled_wave():
    from benchmarks.slm10.sdk_ablation_summary import OUTPUT
    from benchmarks.slm10.sdk_wave_queue import verified_run

    folder = OUTPUT / "wave-A-00"
    correct = expected_wave("A", 0)
    assert len(verified_run(folder, correct, correct["cases"])) == 3
    wrong = expected_wave("A", 1)
    with pytest.raises(ValueError, match="scheduled"):
        verified_run(folder, wrong, wrong["cases"])


def test_wave_expected_ids_are_unique_and_deterministic():
    a = expected_wave("A", 0)
    assert a == expected_wave("A", 0)
    assert len(set(a["trial_ids"])) == 24
    assert set(a["trial_ids"]).isdisjoint(expected_wave("B", 0)["trial_ids"])
    assert set(a["trial_ids"]).isdisjoint(expected_wave("A", 1)["trial_ids"])

def test_verified_legacy_wave_is_sealed_without_redispatch(tmp_path, monkeypatch):
    from shutil import copytree

    from benchmarks.slm10 import sdk_wave_queue
    from benchmarks.slm10.sdk_ablation_summary import OUTPUT

    diagnostics = tmp_path / "diagnostics"
    wave = diagnostics / "A-00"
    portable = wave / "portable"
    copytree(OUTPUT / "wave-A-00", portable)
    monkeypatch.setattr(sdk_wave_queue, "invoke", lambda *_: pytest.fail("verified trial was redispatched"))
    sdk_wave_queue.resume_wave(tmp_path, diagnostics, "A", 0)
    assert sdk_wave_queue.verify_seal(wave, expected_wave("A", 0)) == [portable]
    sdk_wave_queue.resume_wave(tmp_path, diagnostics, "A", 0)
    with (portable / "native.jsonl.gz").open("ab") as archive:
        archive.write(b"tampered")
    with pytest.raises(ValueError, match="artifact digest"):
        sdk_wave_queue.verify_seal(wave, expected_wave("A", 0))


def test_interrupted_reserved_case_blocks_automatic_redispatch(tmp_path):
    expected = expected_wave("A", 0)
    folder = tmp_path / expected["wave"]
    folder.mkdir()
    (folder / "reservation.json").write_text(json.dumps(expected))
    assert reconcile(folder, expected) == ({}, expected["cases"])
    (folder / "cases" / expected["cases"][0]).mkdir(parents=True)
    with pytest.raises(ValueError, match="interrupted reservation"):
        reconcile(folder, expected)
