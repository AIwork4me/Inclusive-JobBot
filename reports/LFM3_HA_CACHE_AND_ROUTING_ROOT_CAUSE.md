# LFM3 cache and adapter routing diagnosis

Sixteen Radeon cells crossed four weights and four process configurations. The experiment used the pinned engine, the scale-one GGUFs, three short admission prompts and three long warm prefixes. Each numerical reply retained four sampled token IDs and 32 native pre-sampling log probabilities per generated position. The observer kept the sampled IDs separate from the top-ranked pre-sampling IDs. All sixteen cells had physical GPU proof. [Replayed factorial](../evidence/IJSLM/lfm3-ha-1.1/cache-factorial.json) · [Native numeric archive](../evidence/IJSLM/lfm3-ha-1.1/cache-factorial.json.gz)

| Settings | Numerical repeat, short | Numerical repeat, warm | Original checkpoint creates/restores | Original warm prefill/decode, ms |
|---|---:|---:|---:|---:|
| Defaults | 0/4 | 0/4 | 29/8 | 150.3 / 36.0 |
| Cache RAM disabled | 0/4 | 0/4 | 29/7 | 156.7 / 34.9 |
| Checkpoints disabled | 0/4 | 0/4 | 0/0 | 330.7 / 36.1 |
| Both disabled | 0/4 | 0/4 | 0/0 | 337.6 / 36.0 |

The denominator is four weight configurations. A passing cell needs all three prefixes to reproduce the four-token sequence and native rankings and probabilities at tolerance 1e-5. The sampled sequences all repeated in the paired probes. Each cell nevertheless failed the numerical repeatability and unrelated-input isolation contract. The three adapted cells in each configuration also failed the scale-zero restoration contract. With checkpoints disabled, all three initial adapted scale-zero runs matched Original in both prompt modes. Those comparisons bind initial routing. Restoration and same-prefix results qualify different state paths.

Disabling checkpoints removed observed restores and increased warm Original prefill by about 180 ms with either cache RAM setting. Disabling cache RAM removed the cache update events and changed warm prefill by about 7 ms in these cells. The warm medians in the table aggregate the stage medians. Original's largest logged cached entry was 25.268 MiB with defaults and 19.043 MiB with checkpoints disabled. Peak process and GPU memory by cell are retained separately. These are single process launches per cell. The sampled tokens and latency do not explain the remaining log-probability drift by themselves.

For each same-prefix pair, the mean absolute log-probability drift uses the token IDs present in both top-32 lists at each of the four generation positions. Cache RAM toggles produced the same drift at the displayed precision when the checkpoint setting was held fixed. The cache-by-checkpoint difference-in-differences rounded to zero at six decimal places for all four weights in both prefix modes.

| Warm-prefix weight | Checkpoints enabled | Checkpoints disabled |
|---|---:|---:|
| Original | 0.013840 | 0.007845 |
| OpenCode | 0.024301 | 0.000152 |
| Pi | 0.024018 | 0.000012 |
| Hermes | 0.021075 | 0.004225 |

The short-prefix responses showed a different checkpoint effect by weight. Disabling checkpoints decreased drift for Original and Pi and increased it for OpenCode and Hermes. The ranked-vector repeatability disposition remains FAIL in every cell. These contrasts isolate effects of the two process flags in the captured configuration while leaving the residual state mechanism unresolved.

`server-context.cpp` creates and restores context checkpoints independently from its RAM prompt-cache objects. `lfm-base.cpp` reads and stores the recurrent short-convolution state in the graph. The existing one-token fixed-adapter admission remains PASS for its original scope. The four-token experiment establishes a separate FAIL and carries zero core attribution. [Pinned server source](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/server-context.cpp) · [Pinned short convolution](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/src/models/lfm-base.cpp)

## Direct ShortConv state

The pinned Radeon runtime saved 208 native slot states across the same four weight and four setting combinations. The diagnostic used one frozen short prompt and one warm prefix, with one recurrent cell, 13 layers and 12,288 F32 values per layer. It decoded the packed prompt and read the live recurrent rows, excluding the serialized checkpoint appendix. All 16 launches carried Radeon proof. A replay recovered ten complete default/Original snapshots after a report serialization failure. Those records retain the saved token hashes and omit two transport fields that were unavailable from the files. [Physical tensor replay](../evidence/IJSLM/lfm3-ha-1.1/shortconv-state-panel.json) · [Slot-state reader](../benchmarks/slm10/ha11_shortconv.py)

All 32 consecutive-save observer controls were byte-identical. Across the 32 immediate generation repeats, the stored token lists matched every time and only two of 13 ShortConv layers were byte-identical in each group. The largest per-group absolute changes ranged from about 0.0107 to 0.0228. Both cache flags disabled still produced this tensor drift. This binds the repeatability failure to observable recurrent-state differences. The upstream operation responsible for the residual with both flags disabled remains unresolved.

| Process settings | Short state restored after unrelated input | Warm state restored after unrelated input |
|---|---:|---:|
| Default | 0/4 | 1/4 |
| Cache RAM disabled | 0/4 | 0/4 |
| Checkpoints disabled | 3/4 | 4/4 |
| Both disabled | 0/4 | 4/4 |

The table requires all 13 layer rows and the stored token list to match. The warm-state restoration result follows checkpoint removal in these measurements. The short-prefix outcome also depends on the RAM-cache setting. Across 24 comparisons to corresponding Original references, the scale-zero runs preserved the saved token lists and had two byte-identical layers out of 13. The scale-one restoration after the zero-scale transition was byte-identical in two of 24 comparisons, both Pi warm-prefix cases with checkpoints disabled. These contrasts include the preceding state history of each diagnostic stage.

## Native routing

In the pinned source, `server-schema.cpp` parses the per-request adapter list through `parse_lora_request` in `server-common.cpp`. The parser accepts numeric IDs into a map without comparing keys to loaded adapter indices. `server_context::construct_lora_list` then iterates only loaded indices and gives every omitted index scale zero. The true loaded index stays present with scale zero for an unknown-only override. `launch_slot_with_task` uses that constructed list, separately from the default-scale branch. [Adapter request parser](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/server-common.cpp) · [Slot routing](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/tools/server/server-context.cpp)

The isolated numerical fixture observed HTTP 200 on all nine unknown-ID probes across OpenCode, Pi and Hermes. Four-token sequences matched both explicit scales. The first-token distributions were closer to scale zero in all nine pairs, and six matched the corresponding initial scale-zero distribution exactly. Three differed. The full-vector classifier returned OTHER because sequence-wide probabilities also differed under known-scale restoration. The source demonstrates scale-zero configuration semantics. The physical traces do not establish fresh-base numerical equivalence for the unknown route or identify which state caused the residual. The raw route remains FAIL.

The fixed guarded SDK and Direct chat paths validate the alias and deny adapter or scale overrides. The SDK boundary also uses a separate random route per trial and checks the trusted callback session. Duplicate JSON keys fail at the strict parser before forwarding. Isolated diagnostics use the native loopback listener to read properties and evaluate routing. Another process on the workstation can reach that listener directly. Endpoint-wide bypass prevention, dynamic adapter switching and concurrent routing remain unqualified.

The candidate patch validates loaded indices before slot use or global adapter mutation. In the Windows CPU-only build, all 22 HTTP and state checks passed. The candidate rejected negative, out-of-range and mixed known/unknown IDs through native completion, OpenAI chat and global routes. The global adapter list stayed unchanged after rejection and accepted the loaded ID and scale controls. Candidate Radeon qualification remains NOT_RUN. [Candidate patch](../patches/lfm3-ha-1.1/llama-b12359-reject-unknown-lora-id.patch) · [CPU build](../evidence/IJSLM/lfm3-ha-1.1/native-routing-candidate-build.json) · [CPU HTTP controls](../evidence/IJSLM/lfm3-ha-1.1/native-routing-candidate-controls.json)
