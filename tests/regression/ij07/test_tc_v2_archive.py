"""Software fixtures exercising the competitive TC-V2 archive and stats handoff."""

import gzip
import json

import pytest

from benchmarks.competitive_slm import statistics, tc_v2_archive as archive, tc_v2_batch as batch
from benchmarks.competitive_slm import tc_v2_candidate as candidate
from business_tools import BusinessStore


class SyntheticJournal:
    def __init__(self, folder):
        self.root = folder
        self.root.mkdir()
        self.cases, self.roster = batch.make_roster("full")
        self.tag = "f" * 32
        self.launch = {
            "pid": 42, "owns_port": True, "status": "PASS", "backend": "vulkan",
            "gpu": candidate.VULKAN_DEVICE, "build": "synthetic-engine",
            "template_sha256": statistics.digest("embedded fixture"), "layers_offloaded": 4, "layers_total": 4,
            "args": ["--ctx-size", "8192"], "trace_file": self.tag + "-source.jsonl",
            "counter_file": self.tag + "-gpu.jsonl",
        }
        self.config = {
            "candidate": "B", "backend": "vulkan", "track": "controlled", "gpu": candidate.VULKAN_DEVICE,
            "engine": {"profile": candidate.ENGINE_PROFILE, "build": "synthetic-engine", "layers": 4},
            "template": {"sha256": self.launch["template_sha256"]}, "budgets": candidate.BUDGETS,
            "model": {"official_model_id": "example/synthetic", "quantization": "Q8_0"},
            "controls_sha256": statistics.digest("synthetic controls"),
            "dataset_sha256": self.roster[0]["dataset_sha256"], "dataset_manifest_sha256": self.roster[0]["manifest_sha256"],
        }
        self.configuration_sha256 = statistics.digest(self.config)
        config = {
            "scope": batch.RUN_SCOPE, "arm_configuration_sha256": self.configuration_sha256, "port": 8102,
            "roster": self.roster, "environment_sha256": statistics.digest({}),
        }
        self.run = {
            "scope": batch.RUN_SCOPE, "evidence_class": "synthetic_software_test", "configuration": self.config,
            "configuration_sha256": self.configuration_sha256, "run_configuration": config,
            "run_configuration_sha256": statistics.digest(config),
            "run_id": "ij07-competitive-tcv2-roster-" + "a" * 32, "sessions": {self.tag: self.launch},
        }
        self.plan = statistics.frozen_suite("TC-V2")
        arm = {
            "model": "example/synthetic", "backend": "vulkan", "track": "controlled", "device": "gfx1151",
            "quantization": "Q8_0", "thinking": "frozen_case_requirement", "protocol": "native-tool-calling",
            "configuration_sha256": self.configuration_sha256, "controls_sha256": self.config["controls_sha256"],
        }
        self.plan.update(schema_version=1, bootstrap={"samples": 100, "seed": 31},
                         arms={"B": arm, "D": {**arm, "model": "example/comparator",
                                                "configuration_sha256": statistics.digest("D config")}},
                         comparisons=[{"id": "B-D", "left": "B", "right": "D", "vary": "model"}])
        for name in ("attempts", "trajectories", "sqlite"):
            (self.root / name).mkdir()
        batch.legacy.write_json(self.root / f"{self.tag}-launch.json", self.launch)
        (self.root / f"{self.tag}-server.log").write_text("C:\\Users\\PrivatePerson\\private.log", encoding="utf-8")
        (self.root / self.launch["trace_file"]).write_text('{"sampled_bytes_hex":"abcd"}\n', encoding="utf-8")
        gpu_counters = (
            {"kind": "gpu_engine", "instance": "pid_42_fixture", "engtype": "Compute", "utilization": 12},
            {"kind": "gpu_process_memory", "instance": "pid_42_fixture", "committed_bytes": 112},
        )
        (self.root / self.launch["counter_file"]).write_text(
            "".join(json.dumps(row) + "\n" for row in gpu_counters), encoding="utf-8",
        )
        for trial, status in zip(self.roster, ("PASS", "FAIL", "BLOCKED")):
            self.write_trial(trial, status)
        proof = batch._complete_session(self.root, self.tag, self.launch, True)
        proof["checkpoints_sha256"] = {
            path.stem: batch._checkpoint_hashes(path, self.root / "trajectories" / path.name)
            for path in (self.root / "attempts").glob("*.json")
        }
        self.launch["proof"] = proof
        batch.legacy.write_json(self.root / "run.json", self.run)

    def write_trial(self, trial, status):
        fields = batch._identity(self.run, trial, self.tag)
        journal = self.root / "attempts" / f"{trial['key']}.json"
        batch.qualify.write_checkpoint(journal, fields)
        if status == "BLOCKED":
            return
        database = self.root / "sqlite" / fields["database"]
        BusinessStore(database, initial={})
        trajectory = {
            **fields, "trajectory_status": status, "source_capture_status": "PASS", "requests": [],
            "attempt_sha256": batch.legacy.sha256_of(journal), "database_sha256": batch.legacy.sha256_of(database),
            "findings": [{"code": "F03_MODEL_ARGUMENT_ERROR", "detail": "private-business-name"}]
            if status == "FAIL" else [],
        }
        batch.qualify.write_checkpoint(self.root / "trajectories" / journal.name, trajectory)

    def export(self, folder, *, panel="full", plan_sha=None):
        return archive.export(
            self.root, folder, panel=panel, plan=self.plan,
            plan_sha256=plan_sha or statistics.digest(self.plan),
        )


@pytest.fixture
def source(tmp_path):
    return SyntheticJournal(tmp_path / "source")


def test_archive_projects_privacy_safe_statuses_and_is_stats_ready(tmp_path, source):
    output = tmp_path / "archive"
    source.export(output)
    assert {path.name for path in output.iterdir()} == {"archive.json", "trials.jsonl.gz", "statistics.json.gz"}
    payload = gzip.decompress((output / "trials.jsonl.gz").read_bytes())
    assert b"private-business-name" not in payload and b"PrivatePerson" not in payload
    manifest, bundle = archive.verify(output, plan=source.plan, plan_sha256=statistics.digest(source.plan), source=source.root)
    assert manifest["runtime"]["thinking"] == "frozen_case_requirement"
    assert manifest["status_counts"] == {"PASS": 1, "FAIL": 1, "BLOCKED": 1, "NOT_RUN": 1147}
    assert manifest["streaming_pair_counts"] == {"PASS": 0, "FAIL": 0, "BLOCKED": 1, "NOT_RUN": 499}
    assert bundle["evidence_class"] == "synthetic_software_test"
    assert bundle["runs"][source.run["run_id"]]["thinking"] == "frozen_case_requirement"
    assert len(bundle["rows"]) == 650
    assert archive.combine([output], plan=source.plan, plan_sha256=statistics.digest(source.plan)) == bundle
    with pytest.raises(ValueError, match="duplicate run"):
        archive.combine([output, output], plan=source.plan, plan_sha256=statistics.digest(source.plan))
    report = statistics.analyze(source.plan, bundle, expected_plan_sha256=statistics.digest(source.plan))
    assert report["arms"]["B"]["first"]["overall"]["status_counts"] == {
        "PASS": 1, "FAIL": 1, "BLOCKED": 1, "NOT_RUN": 497,
    }


def test_export_refuses_scope_plan_and_changed_raw_evidence(tmp_path, source):
    output = tmp_path / "archive"
    with pytest.raises(ValueError, match="frozen staged roster"):
        source.export(output, panel="primary")
    with pytest.raises(ValueError, match="plan digest"):
        source.export(output, plan_sha="0" * 64)
    for definition in source.plan["arms"].values():
        definition["thinking"] = False
    with pytest.raises(ValueError, match="thinking"):
        source.export(output)
    for definition in source.plan["arms"].values():
        definition["thinking"] = "frozen_case_requirement"
    database = next((source.root / "sqlite").glob("*.sqlite"))
    database.write_bytes(b"changed synthetic sqlite")
    with pytest.raises(ValueError, match="SQLite.*digest"):
        source.export(output)
    assert not output.exists()


def test_changed_archived_payload_and_diagnostic_source_fail_closed(tmp_path, source):
    output = tmp_path / "archive"
    source.export(output)
    compressed = output / "trials.jsonl.gz"
    compressed.write_bytes(gzip.compress(b'{"status":"PASS"}\n'))
    with pytest.raises(ValueError, match="compressed"):
        archive.verify(output, plan=source.plan, plan_sha256=statistics.digest(source.plan))
    source.run["scope"] = "single competitive TC-V2 trajectory"
    batch.legacy.write_json(source.root / "run.json", source.run)
    with pytest.raises(ValueError, match="competitive roster"):
        source.export(tmp_path / "other")


def test_verification_distinguishes_archive_readback_and_original_source_recheck(tmp_path, source):
    output = tmp_path / "archive"
    source.export(output)
    source.run["extra_local_note"] = "changed after snapshot"
    batch.legacy.write_json(source.root / "run.json", source.run)
    options = {"plan": source.plan, "plan_sha256": statistics.digest(source.plan)}
    archive.verify(output, **options)
    with pytest.raises(ValueError, match="no longer matches"):
        archive.verify(output, source=source.root, **options)
