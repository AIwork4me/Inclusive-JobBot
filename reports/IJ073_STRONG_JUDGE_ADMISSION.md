# IJ-0.7.3 larger Judge admission

| Candidate | Frozen artifact | Local weight identity | Radeon runtime admission | Matched development quality |
|---|---|---|---|---|
| M14 · Ministral-3-14B-Instruct-2512 | ModelScope revision `40c4c0d04dcbf3785f2e8d27cec5907924d94f08`, Q8_0, 14,359,311,776 bytes | PASS | NOT_RUN | NOT_RUN |
| G31 · Gemma-4-31B-it | ModelScope revision `fe0edf3f21539d03ac7cf97f0f2448a825d5e7b1`, Q8_0, 32,635,677,632 bytes | PASS | NOT_RUN | NOT_RUN |

Both GGUF files match the pinned length and SHA256. The model publishers identify the original models as Apache 2.0. The local assets are quantized derivatives listed separately in the manifest. [Asset pins](../evaluation/aeve/larger_candidate_pins.json) · [Mistral model card](https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512) · [Gemma model card](https://huggingface.co/google/gemma-4-31B-it)

The Radeon slot is assigned to the frozen Q2 queue. Each larger candidate still needs its own runtime proof with an 8,192-token configured context, full Vulkan offload, process-bound counters, and raw generation. Matched development quality and independent qualification will determine the allowed Judge roles.

## Reproduction

From the Atlas worktree, set `PYTHONPATH` to the repository root and `src`. The script accepts `--assets` for the local asset root. Use `--download` if the pinned GGUF is absent and `--verify-asset` to replay weight verification only.

```text
python -m evaluation.aeve.larger_candidate_admission M14 --verify-asset
python -m evaluation.aeve.larger_candidate_admission G31 --verify-asset
```

Use `--matched-development` in place of `--verify-asset` when the Radeon slot is available. The runtime admission command writes a portable report with the generated wire responses and GPU counters. A candidate that clears runtime preflight receives the same 24 blinded development packets under each of the three existing prompt arms. The paired 72-request comparison per candidate retains each request, original response, independently captured generation, citations and scores.

Replay a completed portable cohort with `python -m evaluation.aeve.larger_development <portable-directory>`.

## Additional independent families researched

The additional registry pins exact ModelScope files for O20 (gpt-oss-20b MXFP4), P14 (Phi-4 Q8_0) and L70 (Llama 3.3 70B Q4_K_M). Each length and SHA256 matches the corresponding Hugging Face LFS metadata. Their runtime and matched development are NOT_RUN. M14 and G31 retain their original pinned registry. [Additional registry](../evaluation/aeve/additional_candidate_pins.json)

The llama.cpp maintainers document native MXFP4 support on Vulkan. The local O20 admission still needs to exercise the deployed Harmony template and verify the output boundary. Microsoft's Phi-4 GGUF is an English-focused release. Meta's Llama 3.3 lists eight supported languages and the selected GGUF is a third-party quantization. The bilingual physical comparison determines the observed language coverage for both families. [llama.cpp MXFP4 announcement](https://github.com/ggml-org/llama.cpp/discussions/15095) · [Microsoft Phi-4 GGUF](https://huggingface.co/microsoft/phi-4-gguf) · [Meta Llama 3.3](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)

| Candidate | Publisher information relevant to intake | Local qualification |
|---|---|---|
| OpenAI gpt-oss-20b | Apache 2.0. The publisher reports MXFP4 runs within 16 GB and requires Harmony formatting. Pin the matching local parser and template before edge admission. [Model card](https://huggingface.co/openai/gpt-oss-20b) | NOT_RUN |
| Microsoft Phi-4 | MIT. The publisher describes a 16K context and an English-focused model. Chinese equivalence needs its own matched runs. [Model card](https://huggingface.co/microsoft/phi-4) | NOT_RUN |
| Meta Llama 3.3 70B Instruct | Llama 3.3 Community License. A local quantized configuration would need an exact artifact and workstation memory proof. [Model card](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) | NOT_RUN |

These candidates add potential family coverage. Their publisher-reported capabilities establish neither Radeon compatibility nor suitability for AEVE judgments.
