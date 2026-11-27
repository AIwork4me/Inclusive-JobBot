# IJ-0.7.2 A1 evidence reproduction

The public artifacts can be verified from a fresh clone on Linux or Windows. Python 3.12 is the CI runtime. The archive checks and deterministic witnesses below require `jsonschema` and `pytest`. The physical runner also uses the installed SDK version for provenance and the pinned Radeon runtime. [Exact gate status](../atlas/gates.json) · [CI workflow](../.github/workflows/evidence-validation.yml)

## Verify a fresh checkout

Run from a new directory on Linux. On Windows use `py -3.12 -m venv .venv`, `.venv\Scripts\python.exe` and `$env:PYTHONPATH = 'src'` for the same commands.

```bash
git clone --branch mission/ij-0.7.1-jobbot-agentic-capability-atlas-v1 https://github.com/AIwork4me/Inclusive-JobBot.git
cd Inclusive-JobBot
git rev-parse HEAD
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install pytest==9.2.0 jsonschema==4.26.0
export PYTHONPATH=src
python scripts/tools/scan_sensitive.py
python scripts/tools/verify_atlas_artifacts.py
python scripts/tools/verify_ij06_evidence.py
python -m scripts.tools.verify_ij07_artifacts
python scripts/tools/atlas_progress.py --check
python -m scripts.tools.atlas_failure_ledger --check
python -m scripts.tools.atlas_compare_pc_p_factorial --progress --check
python -m scripts.tools.atlas_compare_pc_p_factorial --full-matrix --check
python -m scripts.tools.atlas_compare_pc_p_factorial --wire A --check
python -m scripts.tools.atlas_compare_pc_p_factorial --wire B --check
python -m scripts.tools.atlas_compare_pc_p_factorial --wire G --check
python -m scripts.tools.atlas_compare_pc_p_factorial --wire H --check
python -m scripts.tools.atlas_compare_pc_s_multitool --stream-pairs --check
python -m scripts.tools.atlas_compare_pc_s_multitool --draft-guard-pairs --check
python -m scripts.tools.atlas_multitool_witness --extended --check
python -m scripts.tools.atlas_multitool_witness --unicode --check
python -m scripts.tools.atlas_multitool_witness --observed-draft-controls --check
python -m scripts.tools.atlas_planning_plan_controls --check
python -m scripts.tools.atlas_audit_plan_ambiguity --preconditions --check
python -m pytest -q -o asyncio_mode= tests/evidence
```

The factorial verifier reconstructs scores from the archived run fingerprints, case journals and first-response captures. The witness commands run deterministic software checks over frozen inputs. The witness commands do not require model weights or a GPU. [Artifact digests](../atlas/artifact_manifest.json) · [Checkpoint counts](../evidence/IJ072/benchmark_validity/pc-p-factorial-progress.json)

## Reproduce physical inference

Use a separate clean Windows worktree for the exact source commit in the archive. Read the run configuration for each candidate and arm before launch. It binds the checked observer build, model and template hashes, settings, dataset, seed and runtime source. The observer runs a loopback llama.cpp server and stores PID-bound Radeon counters and sampled source records. Use new output paths for changed inputs and keep a single active run on the Radeon. [PC-P roster and treatments](../atlas/benchmarks/pc_p_factorial.json) · [Physical run identities](../evidence/IJ072/benchmark_validity/pc-p-factorial-progress.json)

The operator handoff indexes the archived PC-S and PC-P runtime sources and the current A1 resume point. Qwen3-14B weights are pinned with a ModelScope revision and a file digest. Each PC-P bundle includes the sealed configuration and input hashes together with its trial data. [Operator handoff](../HANDOFF.md) · [Qwen3-14B pin](../atlas/benchmarks/pc_s_qwen3_14b.json) · [Example PC-P archive](../evidence/IJ072/benchmark_validity/pc-p-a-clean-p3-032/bundle.json)

The matched draft run used the clean workstation worktree `.scratch/ij072-draft-runtime` at `230b51e611ef5ff0d2078db5f23b352c85ef4775`. From that tree, use `legacy` and `observed` in order with the same pinned model and observer. The command below writes to a new reproduction output. A strict FAIL can still yield complete physical coverage.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$arm = 'legacy'
python -m scripts.tools.atlas_pc_s --suite multi --candidate J --draft-guard-control $arm --model ../../.tools/models/Qwen3-14B-GGUF/Qwen3-14B-Q8_0.gguf --engine-dir ../../.tools/ij07-toolchoice-p4b-vulkan --output ".runtime/reproduce-draft-$arm" --batch-size 37
```

The draft proof binds prior observed reviews to model calls and independently recorded SQLite snapshots. [Legacy archive](../evidence/IJ072/benchmark_validity/pc-s-j-multitool-draft-legacy/coverage.json) · [Observed profile archive](../evidence/IJ072/benchmark_validity/pc-s-j-multitool-draft-observed/coverage.json)
