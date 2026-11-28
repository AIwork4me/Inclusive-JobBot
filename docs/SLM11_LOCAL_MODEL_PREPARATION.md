# Local models for supplemental SLM evaluation

Gemma-4-E2B is present on the shared Windows workstation as the existing frozen Q8_0 GGUF. The file is 4,967,491,520 bytes and matches the complete SHA256 pin. The existing pinned runtime has independent Radeon admission and physical TC-V3 seals. [Admission report](../reports/SLM11_GEMMA4_RADEON_ADMISSION.md)

Use the mission worktree and the shared asset root. The command only reads and hashes the registered file. It does not reserve the GPU.

```powershell
$assets = (Resolve-Path -LiteralPath '../..').Path
$python = Join-Path $assets '.venv/Scripts/python.exe'
$env:PYTHONPATH = 'src'
& $python -m benchmarks.slm10.local_model_preflight --assets $assets --gemma
```

For a future model, keep its verified GGUF under the shared repository asset root. Use `--candidate-manifest <file>` in place of `--gemma`. Use the `G` object in the [local preparation record](../atlas/slm/v1.0/local-model-preflight.json) as the field template. Supply the exact path, bytes, SHA256, architecture class, parameter counts and source. Supported architecture classes are `DENSE`, `PER_LAYER_EMBEDDINGS` and `MIXTURE_OF_EXPERTS`. Total, effective and active counts retain separate fields. Use null for a metric the publisher does not establish. Mixture-of-experts records require separately sourced active and total counts.

Add `--max-active-parameters 2000000000` when the supplemental benchmark has a strict 2B active limit. The filter uses the explicit active count. Gemma's 2.3B effective figure describes its per-layer embeddings profile. Its source inventory reports 5,123,178,051 total parameters. [Publisher model card](https://gemma.ai/models/gemma-4/model-card/)

Keep the new model revision and tokenizer/template and runtime hashes in the separate admission record. A passing file check permits asset preparation. Only a matching physical run can establish backend placement, parser behavior, SDK transport, dispatcher compatibility and performance. Any future roster receives a new experiment ID and contributes zero trials to this frozen 36,550-trial core.
