# IJ-SLM-1.1 resume audit

Date 2026-11-27, Asia/Shanghai.

## Repository and verification

The existing linked mission worktree was clean at the reviewed start point `b4d098a48e980f5862084238496b87630fb6cff4`. Its branch, GitHub branch, and open Draft PR #9 agreed. All 14 check runs at that SHA completed successfully. PR #6 supplies evaluation integrity evidence, PR #8 supplies cross-SDK research, and PR #11 consumes the NanoAgent engineering exchange. Their branches were accessed read-only.

| Draft PR | Reviewed head at resume |
| --- | --- |
| [#6](https://github.com/AIwork4me/Inclusive-JobBot/pull/6) | `06f25ab50db9e8ef074d9fb804de3191d7eadb98` |
| [#8](https://github.com/AIwork4me/Inclusive-JobBot/pull/8) | `56c6c74bf7216eb9cf65be4056c8db1964d23b05` |
| [#11](https://github.com/AIwork4me/Inclusive-JobBot/pull/11) | `1c26c1795ff43e7e5419ac032b111a5da8fa19f7` |

The [hosted GitHub replay](https://github.com/AIwork4me/Inclusive-JobBot/actions/runs/46017929174) compared the committed priority datasheets and NanoAgent exchange to their generators on both Linux and Windows at `5c507f22ec5b00a66d8fb4edfd728aa3920cf60b`. The first milestone's separate Atlas inventory check failed because the legacy Atlas digest index required the new files. Its successor regenerated that index and passed the evidence and privacy workflow. A fresh public Git partial clone verified the commit and tree connection for `afc787c4e5c2c429b3b8b21f2ba767a67ad57356` on the workstation. The full workstation checkout over HTTPS remained incomplete. The independent exact-SHA tarball download timed out after 300 seconds. Local Git objects were never substituted for either remote download.

## Physical identity and scheduler

- Windows workstation with AMD Ryzen AI MAX+ PRO 395, Radeon 8060S/gfx1151 and driver 32.0.22018.5. Windows reports 128 GiB installed and 95.8 GiB visible to the OS. Free space was about 1,568 GiB at the audit.
- The shared Windows mutex reported held while the frozen F control process ran. The live hashed host and GPU identities matched the approved handoff. The active llama.cpp build was `b12359-b1b770d90d94cad9e9ea5b993bdbc383a522fb28` on Vulkan. All nine binary hashes matched the published runtime identity in the current F session. The installed Antigravity SDK was 0.1.24 and its local harness hash matched the seal.
- All five locally staged GGUF files matched the pinned full-file SHA256. The [model registry](../atlas/slm/v1.0/model_registry.json) records exact artifact revisions and weights. The candidate G source identity reports 5,123,178,051 safetensors parameters, and its frozen Q8_0 GGUF occupies 4,967,491,520 bytes on disk. Google describes 2.3B effective and roughly 5.1B with embeddings, with an advertised 128K context and Apache 2.0 license. The frozen runtime uses its own 8,192-token profile. Actual Gemma GPU memory, tool parser behavior, callback, result delivery and repeat stability remain NOT_RUN. [Pinned model identity](../evidence/IJ07/model_identity/G.json) · [Google model card](https://gemma.ai/models/gemma-4/model-card/)
- The initial read-only replay found 4,950 A/B/D seals and 972 F seals. It observed 28 reservations in the running F batch, which were excluded from formal coverage. The publication snapshot now has 1,260 F seals. The [published progress](../atlas/slm/v1.0/physical_progress.json) records 6,210 verified TC-V3 trials and 30,340 core trials remaining. The GPU controller advanced separately throughout the publication.
- The existing LFM3 24-trial holdout and A/B/D 42-trace P0-E follow-up remain queued after the frozen controller. The locally queued Extension waits until the scheduler yields and all three P0-E portable reports establish their physical coverage. Formal MULTITOOL and Planning dispatch require independent reviewed credentials. Each diagnostic contributes zero core trials.

Valid seals, the live owner and the frozen queue reconcile for the observed snapshot. D25 and AG-11 remain BLOCKED. This audit covers resumption and the published measurement snapshot.
