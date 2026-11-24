# Native MiniCPM5 parser diagnostic suite

The immutable original 26 fixtures stay under `benchmarks/tool_calling/fixtures`. The v1.0.0 expansion adds 130 named cases. The v1.1.0 expansion adds 16 paired original/escaped nested control cases. The direct parser probe includes the 26 immutable inputs as raw observations and scores the chosen expanded suite. Deterministic random cuts use seed 20261124. No model weights are needed for the C++ probe.

## Native build

Use a separate upstream checkout and launch CMake from a Visual Studio x64 developer shell on Windows. For Linux use a recent C++ toolchain with CMake and Ninja. CMake builds the probe against upstream `llama-common`. The optional `test-chat` target is upstream's own template suite.

```powershell
git clone https://github.com/ggml-org/llama.cpp.git .scratch/ij06-upstream
git -C .scratch/ij06-upstream checkout --detach b1b770d90d94cad9e9ea5b993bdbc383a522fb28
$probeConfig = (Resolve-Path benchmarks/tool_calling_v2/parser/probe.cmake).Path
cmake -S .scratch/ij06-upstream -B .scratch/ij06-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_APP=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DGGML_NATIVE=OFF "-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=$probeConfig"
cmake --build .scratch/ij06-build --target test-chat ij06-native-probe llama-server --parallel 8
```

With the verified ModelScope weights on disk, extract `tokenizer.chat_template` without newline conversion when reproducing the Windows diagnostic. The upstream 1B template can serve as a model-free parser reference. Its byte identity is different. Pass the exact selected template path to the script.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/run_ij06_parser_tests.ps1 -Probe .scratch/ij06-build/bin/ij06-native-probe.exe -ChatTemplate .scratch/templates/gguf_embedded.jinja -Output .scratch/ij06-p0-direct.json -Lexical
```

For a candidate reproduction, first keep the P0 binary in its own directory. Apply the two patches to a separate clean pinned checkout and configure a distinct build directory with the same CMake options.

```powershell
$parser = (Resolve-Path benchmarks/tool_calling_v2/parser).Path
git -C .scratch/ij06-candidate apply "$parser/minicpm5-terminal-integrity.patch"
git -C .scratch/ij06-candidate apply "$parser/minicpm5-native-json-lexical.patch"
```

Pass both patch paths to `-Patch` from a PowerShell session. Add `-Lexical -RequireNativePass` to require every applicable candidate native and parity case. On Linux, pass both patch paths as separate `--patch` options to `python -m benchmarks.tool_calling_v2.parser.run_direct` with `PYTHONPATH=src`.

## API replay

Launch the configured pinned Windows server with the existing managed launcher. Pick a new output directory per backend.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/run_ij06_parser_tests.ps1 -Output .scratch/ij06-vulkan-wire
```

Use `-Resume` to continue an incomplete replay on the same backend, executable, configuration and fixture revision. The wire replay records both raw replies, a per-case checkpoint and finish summary. When evaluating a separately built static CPU candidate, launch it with `--host 127.0.0.1 --device none -ngl 0 --offline` on a distinct free port. Pass the explicit loopback URL, candidate binary, PID and build patch paths. Candidate mode verifies the listening process and compares its model identity with the ModelScope manifest.

The validation exit codes are 0 for a passing check, 1 when a measured conformance check fails and 2 if wire execution cannot be completed. An expected decoder rejection of invalid raw arguments is visible in combined wire status. The strict arguments dimension scores such a rejection as PASS. End-to-end execution is outside these replay commands.

## Dynamic Windows GPU candidate

Apply both P4 patches to the pinned checkout in a separate source tree. Configure a Release x64 Ninja build with `BUILD_SHARED_LIBS=ON`, `GGML_BACKEND_DL=ON`, `GGML_NATIVE=OFF`, `LLAMA_BUILD_SERVER=ON`, `LLAMA_BUILD_TOOLS=ON`, tests/examples/app/prebuilt UI/OpenSSL disabled, and `LLAMA_BUILD_COMMIT=b1b770d90d94cad9e9ea5b993bdbc383a522fb28`, `LLAMA_BUILD_NUMBER=12359`. Under MSVC set initial C++ flags to `/utf-8 /EHsc`. Build `llama-server` and `ggml-cpu`.

Keep Vulkan and ROCm dynamic distributions separate. Copy the built binaries into independent candidate directories. Add the verified b12359 `ggml-vulkan.dll` to the Vulkan candidate or the verified `ggml-hip.dll`, `amdhip64_7.dll`, `amd_comgr.dll` and `rocm_kpack.dll` to the ROCm candidate. Use the pinned project-local ROCm runtime. Match the exact loaded process, device, offload count and process counters.

    powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/run_ij06_parser_candidate_gpu.ps1 -Backend vulkan -CandidateDirectory .tools/ij06-p4b-vulkan -Output .runtime/ij06-parser-p4b-vulkan

With the expanded suite, P4b intentionally rejects five nested duplicate-key wire messages. The combined wire command reports their failures and exits 1. Inspect the independent native, strict-arguments and parity dimensions. Pass `-SdkOutput` for a separate real SDK run on the same candidate.
