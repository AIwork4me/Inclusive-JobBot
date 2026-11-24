# M0 Environment Report

- Collected: 2026-11-24, on the physical qualification machine
- Collector: `scripts/windows/collect_environment.ps1`
- Evidence: `evidence/M0/environment.json`, `evidence/M0/gpu_inventory.json`,
  `evidence/M0/dependency_inventory.json`
- Status: **PASS** (baseline frozen; later changes to any item must be recorded)

## Hardware and operating system

| Item | Value |
|---|---|
| Machine | HP ZBook Ultra G1a 14 inch Mobile Workstation PC |
| CPU | AMD RYZEN AI MAX+ PRO 395 w/ Radeon 8060S, 16 cores, 32 threads |
| Memory | 128 GB installed (8 modules, LPDDR5X-8000); 95.78 GB visible to the OS |
| GPU | AMD Radeon(TM) 8060S Graphics, PCI `1002:1586` rev D1 |
| GPU memory | 32 GB dedicated UMA segment (`qwMemorySize` = 34,359,738,368); the GPU can use shared system memory beyond it |
| GPU driver | 32.0.22018.5, dated 2025-09-17 |
| Vulkan | 1.4.320, AMD proprietary driver 25.20.18 (LLPC), `PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU`, device `0x1586` |
| OS | Microsoft Windows 11 Pro, 25H2, 10.0.26200 build 26200.9974, 64-bit |
| Locale / time zone | zh-CN / China Standard Time |
| System HIP runtime | `amdhip64_6.dll` 10.0.3652.0, `amdhip64_7.dll` 10.0.3661.0 (shipped with the driver) |

The `gfx1151` architecture identifier is not exposed by Windows CIM or Vulkan.
It is reported by the ROCm runtime itself when the llama.cpp ROCm build starts:
`ROCm0: AMD Radeon(TM) 8060S Graphics` on a build whose target list names
`gfx1151` (`evidence/IJ0/engine_install.json`).

The 8060S is the integrated GPU of the APU, not a Ryzen AI NPU and not a DEEPX
DX-M2. Nothing in this report is NPU evidence.

## Software baseline

| Tool | Version |
|---|---|
| Windows PowerShell | 5.1 (Desktop 5.1.26100.9818); all scripts in `scripts/windows` are verified on it |
| Python | 3.12.10, project environment in `.venv` |
| pip | 25.0.1 |
| Git | 2.56.1.windows.1 |
| GitHub CLI | 2.105.0, authenticated as `AIwork4me` |
| google-antigravity | 0.1.24 (Apache-2.0) |
| modelscope | 1.40.3 |
| llama.cpp | `1.0.0-dev (build 12359, commit b1b770d90)`, stable release `v1.0.0` |
| Ollama | 0.40.17, portable copy in `.tools/ollama-core`, optional baseline only |
| Node.js | not installed |

Exact package versions are in `requirements.lock`. Its SHA256 entries were
produced by `scripts/tools/lock_hashes.py`, which compares each file with the
digest published by `pypi.org`; the record is
`evidence/M0/lock_hash_crosscheck.json`.

## GPU backends available to llama.cpp

| Build | Result of `--list-devices` |
|---|---|
| CPU | no devices (no GPU backend library in this build) |
| Vulkan | `Vulkan0: AMD Radeon(TM) 8060S Graphics (111227 MiB, 105666 MiB free)` |
| ROCm/HIP | `ROCm0: AMD Radeon(TM) 8060S Graphics (91612 MiB, 91452 MiB free)` |

The ROCm build needs `hipblas.dll`, which is not in the release archive. The
libraries come from ROCm 10.0.0 wheels in `runtime/llama-cpp/rocm-libs`
(`scripts/windows/install_rocm_runtime.ps1`).

## Security state

| Item | Value |
|---|---|
| Smart App Control | Off (turned off by the machine owner on 2026-11-24) |
| User-mode code integrity enforcement | 0 (not enforced) |
| Kernel-mode code integrity enforcement | 2 (enforced) |
| Virtualization-based security | running |
| Defender real-time protection | on |

History: Smart App Control was on at the start and blocked the unsigned
official llama.cpp binaries. The project did not change the setting. See
`BLOCKERS.md` B-001.

Other observations:

- The machine is reached through a remote display session (a Microsoft Remote
  Display Adapter is present). Project scripts never change network settings.
- Project scripts use a process-scoped `-ExecutionPolicy Bypass`; the machine
  and user execution policies are Undefined.

## Network facts that affect reproducibility

| Destination | Observed |
|---|---|
| `files.pythonhosted.org` | TLS connections reset (`UNEXPECTED_EOF_WHILE_READING`) |
| `raw.githubusercontent.com`, `ollama.com` | unreliable from this network |
| `pypi.org` metadata API, `api.github.com`, `modelscope.cn`, `stable.repo.amd.com` | reachable |
| GitHub release assets | about 100 KB/s per connection; parallel range requests reach roughly 9 MB/s |
| System proxy | disabled; loopback bypass list present |

Consequences are recorded in `DECISIONS.md` D-002.

## Differences from the assumptions in the mission

| Assumption | Measured |
|---|---|
| Unified memory 128 GB | 128 GB installed; 95.78 GB visible to the OS because 32 GB is a dedicated GPU segment |
| CPU "AMD Ryzen AI MAX+ 395 / PRO 395" | AMD RYZEN AI MAX+ **PRO** 395 |
| Ollama as primary runtime | Replaced by llama.cpp through ECO-01; Ollama kept as optional baseline |

## Redaction

Evidence is written with the account's user directory replaced by
`<REDACTED>` and the host name by `<HOST>`. Serial numbers, IP addresses and
tokens are never collected. `scripts/tools/scan_sensitive.py` must report zero
findings before any commit.
