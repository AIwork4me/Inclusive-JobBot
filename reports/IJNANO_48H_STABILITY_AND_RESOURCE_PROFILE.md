# IJ-NANO-48H Stability and Resource Profile

Scope: all 3,840 physically executed trials (E1 1,920 + E2 1,920) on
RX 7900 XTX / llama.cpp b12359 Vulkan / Q8_0(+F16 LoRA), 2026-11-28
04:41Z–13:22Z. This is a multi-campaign working session with per-block
server lifecycle — NOT a single-configuration uninterrupted soak; no
such claim is made.

## Latency (end-to-end per trial, single-request)

| Metric | Value |
|---|---|
| Mean | 4.46 s |
| P50 | 4.52 s |
| P95 | 8.43 s |
| P99 | 8.49 s |
| Max | 8.99 s |

| Configuration | n | Mean | P95 |
|---|---:|---:|---:|
| MiniCPM5-2B | 640 | 2.94 s | 5.68 s |
| LFM3-1.7B (W0) | 640 | 3.68 s | 5.99 s |
| Qwen3.5-2B | 640 | 4.60 s | 5.09 s |
| LFM3+W1_pi | 640 | 5.09 s | 8.46 s |
| LFM3+W2_opencode | 640 | 5.33 s | 8.45 s |
| LFM3+W3_hermes | 640 | 5.13 s | 8.43 s |

Adapter inference costs ~+1.4s mean per trial (LoRA application
overhead on Vulkan), ~+38% vs W0.

## Throughput and reliability

- 3,840 trials in ~8.7h of dispatch across 5 sequential campaigns
  (~7.3 trials/min sustained incl. canaries and server lifecycle).
- Mean completion tokens 664/trial (budget 1024).
- Transport failures: **0**. Quarantined benchmark trials: **0**.
  Canary failures post-integration: **0** (one recorded preflight
  defect with zero dispatches). Circuit-breaker openings: 1 (the
  recorded defect; recovered via requalification path).
- Server restarts: one per model per block boundary by design
  (fixed-configuration isolated processes); no unplanned restarts.
- Server-health telemetry (`/metrics`) sampled between blocks (8
  samples per 8-block campaign, batch B shown; identical pattern
  elsewhere): all servers healthy at every sample; no latency drift
  beyond the distributions above; no request failures recorded.

## Resource identity

- GPU: AMD Radeon RX 7900 XTX 24GB (gfx1100), driver 32.0.21030.2001;
  every server fully offloaded (43/43, 25/25, 25/25 layers).
- Engine: llama.cpp b12359, exe sha256 38c5affb… (== sealed N02R
  identity), Vulkan backend; identical context/cache flags across all
  six configurations (recorded in admission evidence).
- Weights: Q8_0 bases byte-verified; adapters F16 GGUF sha256-verified
  against upstream LFS digests (306 lora tensors, 62.8 MiB buffer).

## Known limitations

- GPU memory/temperature/utilization were not continuously sampled
  (no cross-vendor counter path without system-level installs, which
  need the owner); `/metrics`-based server health and per-trial
  latency/token telemetry are the recorded resource evidence.
- TTFT not captured (non-streaming endpoint) — reported missing, not
  zero.
- Energy not measured.
