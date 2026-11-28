import hashlib

import pytest

from evaluation.aeve import larger_candidate_admission as admission


def test_larger_development_requests_keep_the_existing_blind_pairing():
    from evaluation.aeve.larger_development import matched_requests

    mistral, gemma = matched_requests("M14"), matched_requests("G31")
    assert len(mistral) == len(gemma) == 72
    assert [(row["case_id"], row["arm"]) for row in mistral] == [
        (row["case_id"], row["arm"]) for row in gemma
    ]
    for left, right in zip(mistral, gemma, strict=True):
        assert left["body"]["model"] == "ij07-candidate-m14"
        assert right["body"]["model"] == "ij07-candidate-g31"
        assert {k: v for k, v in left["body"].items() if k != "model"} == {
            k: v for k, v in right["body"].items() if k != "model"
        }
        assert set(left["packet"]) == {"task", "events", "dimension"}


def test_resumable_download_reuses_partial_and_verifies_bytes(tmp_path, monkeypatch):
    model = b"synthetic-model-fixture"
    pin = {"code":"test","file":"model.gguf","size":len(model),"sha256":hashlib.sha256(model).hexdigest(),
           "repo":"owner/artifact","revision":"1"*40}
    folder = tmp_path/".tools/models/AEVE-larger-candidates"
    folder.mkdir(parents=True)
    partial = folder/"model.gguf.part"
    partial.write_bytes(model[:5])

    def execute(flags, *, capture_output, check):
        assert flags[flags.index("--range")+1] == f"5-{len(model)-1}"
        assert pin["revision"] in flags[-1]
        from pathlib import Path
        from subprocess import CompletedProcess
        output = Path(flags[flags.index("--output")+1])
        output.write_bytes(model[5:])
        return CompletedProcess(flags,0,b"206",b"")

    monkeypatch.setattr(admission.subprocess,"run",execute)
    final = admission.download(pin,tmp_path)
    assert final.read_bytes() == model and not partial.exists()
    final.write_bytes(model[::-1])
    with pytest.raises(ValueError,match="ModelScope"):
        admission.local_asset(pin,tmp_path)
