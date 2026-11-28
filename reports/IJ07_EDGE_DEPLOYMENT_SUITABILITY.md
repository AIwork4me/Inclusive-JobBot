# IJ-0.7 edge deployment suitability

The observed Windows configuration loads pinned Q8_0 GGUFs for six
small or effective-scale candidates plus the Qwen3-8B reference. The AMD
Radeon 8060S showed both process GPU activity and committed GPU memory
for each. A separate AMD WebGPU provider ran the official Aion INT4
model with CPU fallback disabled. Runtime and quantization differences
affect cross-model comparisons. [GPU model identity](IJ07_MODEL_ADMISSION_MATRIX.md)

For MiniCPM5-2B the historical test measured approximately 3.36–3.48 GB peak
process GPU committed memory while running Q8_0 and single-slot 8192
context. The 1.56 GB Q4_K_M file is a candidate for deployment; independent
accuracy and resource testing is still required. Current diagnostic
latencies include captured HTTP response timings and use the historical
synthetic service workload. [Performance](IJ07_GPU_PERFORMANCE.md)

Long soak, hardware energy, simultaneous service capacity and physical
DX-M2 regression remain `NOT_RUN`. The deployment requirements describe
attention, KV allocation, host controls and target simulator validation.
 [Portability requirements](../portability/deepx-dxm2/IJ07_DEPLOYMENT_REQUIREMENTS.md)
