# llama.cpp runtime

Engine binaries are never committed. `scripts/windows/install_llama_cpp.ps1`
downloads the pinned official release into this directory and records its
identity in `evidence/IJ0/engine_install.json`.

| Directory | Contents |
|---|---|
| `cpu/` | official CPU build: no GPU backend library is present, so this is the pure CPU path |
| `vulkan/` | official Vulkan build: CPU build plus `ggml-vulkan.dll` |
| `rocm/` | official ROCm build: CPU build plus `ggml-hip.dll` and HIP runtime DLLs |
| `rocm-libs/` | ROCm 10.0.0 wheels with hipBLAS, rocBLAS and hipBLASLt, which the ROCm build imports but the release archive does not contain |

Pinned identity: `configs/llama_cpp/engine.json` (stable release `v1.0.0`,
build `b12359`, commit `b1b770d90`). On Windows the ROCm wheels take about
2.8 GB and `ggml-hip.dll` is 1.1 GB on disk.

```powershell
pwsh -File scripts/windows/install_llama_cpp.ps1
pwsh -File scripts/windows/install_rocm_runtime.ps1
```
