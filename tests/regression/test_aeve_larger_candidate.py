import hashlib

import pytest

from evaluation.aeve import larger_candidate_admission as admission


def test_resumable_download_reuses_partial_and_verifies_bytes(tmp_path, monkeypatch):
    model = b"synthetic-model-fixture"
    pin = {"code":"test","file":"model.gguf","size":len(model),"sha256":hashlib.sha256(model).hexdigest(),
           "repo":"owner/artifact","revision":"1"*40}
    folder = tmp_path/".tools/models/AEVE-larger-candidates"
    folder.mkdir(parents=True)
    partial = folder/"model.gguf.part"
    partial.write_bytes(model[:5])

    def execute(flags, *, check):
        assert ["--continue-at","-"] == flags[flags.index("--continue-at"):flags.index("--continue-at")+2]
        assert pin["revision"] in flags[-1]
        with partial.open("ab") as stream:
            stream.write(model[5:])

    monkeypatch.setattr(admission.subprocess,"run",execute)
    final = admission.download(pin,tmp_path)
    assert final.read_bytes() == model and not partial.exists()
    final.write_bytes(model[::-1])
    with pytest.raises(ValueError,match="ModelScope"):
        admission.local_asset(pin,tmp_path)
