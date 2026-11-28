# SDK specialization and causal ablation on Radeon

The pilot executed three development tasks on each of the three priority models. The tasks cover English and mixed-language single-tool, dependent-tool and authorization cases. The six requested arms produced 54 physical diagnostic observations. The real SDK control adds nine runs, and the scoped duplicate guard adds six. Formal trial attribution is zero. [Configuration](../atlas/slm/v1.0/sdk-causal-experiment.json) · [Evidence](../evidence/IJSLM/sdk-causal/manifest.json)

| Arm | Intervention | Evidence unit |
|---|---|---|
| A0 | Frozen Direct baseline | Full task |
| SDK control | Effective SDK request and original result packaging | Full task |
| A1 | Byte-identical provider request at the first captured result | Matched next decision |
| A2 | Remove the Markdown formatting directive | Matched next decision |
| A3 | Serialize the verified tool result as compact JSON | Matched next decision |
| A4 | Include completed actions from earlier callback evidence | Matched next decision |
| A5 | Real SDK with the compact result adapter | Full task |
| Guard | Reuse a verified immutable read for an identical action in scope | Full task |

On the English single-tool task, the LFM3 A1 replay repeated the read. A2, A3 and A4 each stopped with the correct JSON. A5 completed with one callback. MiniCPM5 repeated in A1 through A4 for the same task. Qwen3.5 stopped with fenced JSON in A1, A3 and A4 in that task. A2 produced another tool proposal. The next-decision controls preserve the same matched history and exclude later callbacks. These effects are scoped to the observed cases. [LFM3 pilot](../evidence/IJSLM/sdk-causal/pilot-B/report.json) · [MiniCPM5 pilot](../evidence/IJSLM/sdk-causal/pilot-A/report.json) · [Qwen3.5 pilot](../evidence/IJSLM/sdk-causal/pilot-D/report.json)

The guard protected two callbacks in the MiniCPM5 dependent-tool pilot. The model continued proposing actions and the task still lacked a terminal answer. The guard applies only to verified successful static reads and excludes release, recovery and scope changes. Its protection belongs to the host. A5 changes SDK integration. A2 through A4 change model-visible context through experimental runtime controls.

The published panel covers 90 of 90 model–task combinations and 513 of 540 requested A0–A5 physical observations. Ten slots are BLOCKED because matched result history was absent. Seventeen A4 slots are NOT_RUN because the source request did not support the planned intervention. The separately identified 90 SDK controls and 54 applicable guard captures bring the physical total to 657. [Per-slot coverage](../evidence/IJSLM/sdk-causal/ablation-coverage.json)

Across the 30 tasks per model, exact final JSON rose from 19 to 23 in LFM3, from six to nine in MiniCPM5, and from six to ten in Qwen3.5 between SDK control and compact serialization. These development observations carry their own scope. The independent LFM3 holdout is pinned for a matched Radeon retest. [Ablation summary](../evidence/IJSLM/sdk-causal/ablation-summary.json) · [Holdout runner](SLM10_ADAPTER_DEVELOPMENT_ENTRY_POINT.md)

The missing A3/A4 slots and independent held-out execution remain open. The current SDK boundary buffers SSE before validation. Its first-visible-text measurements describe buffered delivery. The provider-delta experiment measures native SSE at the socket separately.


## Transport and typed action controls

The Qwen3.5 observer on/off control used identical tool-free Direct request bytes. Parsed output, usage and stop reason agreed. Native first content arrived at 53.49 ms with observation off and 70.885 ms with it on in this single pair. A latency effect remains unqualified in this single pair. The large real SDK response was 677,986 bytes. The old 512 KiB limit rejected it, and the revised 1 MiB limit still rejected its length termination. It therefore provides a negative control for incomplete SSE. [Transport evidence](../evidence/IJSLM/sdk-causal/transport-v1/report.json)

The frozen typed extension separates catalog development from four new held-out families. Its action-instance verifier covers nested schemas, multi-entity tools, legal retries and producer-linked observations. Eight scoped software qualification controls passed. Extension GPU results and whole-suite qualification remain pending. [Extension manifest](../atlas/slm/v1.0/sdk-extension/manifest.json)

The independent transport retest shortened the payload to 1,060 words and preserved the 2,400-token cap and frame validation. The real SDK received the exact 602,124-byte response and a valid stop. The original cumulative limit rejected those same bytes and the revised limit accepted them. The buffered visible-text onset was 29,681 ms and SDK task wall time was 30,693 ms for this synthetic case. [Retest](../evidence/IJSLM/sdk-causal/transport-v1-1/report.json)
