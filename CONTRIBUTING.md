# Contributing

## Development setup

```powershell
pwsh -File scripts/windows/bootstrap.ps1
pwsh -File scripts/windows/install_llama_cpp.ps1
pwsh -File scripts/windows/install_rocm_runtime.ps1   # ROCm/HIP backend only
pwsh -File scripts/windows/download_models_modelscope.ps1
pwsh -File scripts/windows/start_llama_server.ps1 -Backend vulkan -Model q8
```

On a network where `files.pythonhosted.org` is unreliable, pass
`-IndexUrl https://pypi.tuna.tsinghua.edu.cn/simple` to `bootstrap.ps1`.

Windows Smart App Control must not block unsigned executables, because the
official llama.cpp release binaries are not Authenticode-signed. The project
never changes that setting; `install_llama_cpp.ps1` reports a blocked binary.

## Rules that are not negotiable

- Every test and gate result is `PASS`, `FAIL`, `BLOCKED` or `NOT_RUN`. Do not
  merge these values and do not change one without evidence.
- Label mocks, fixtures, CPU runs and synthetic data as what they are.
- Bind every result to its identities: commit, engine build, model revision and
  digest, backend, dataset digest.
- No silent fallback between engines, backends or model versions.
- Never commit model weights, engine binaries, credentials, real names, user
  directory paths, host names or private business data. Run
  `python scripts/tools/scan_sensitive.py` before committing; it must report
  zero findings.
- Keep `scripts/windows/*.ps1` ASCII-only. Windows PowerShell 5.1 mis-decodes
  BOM-less scripts that contain non-ASCII text.

## Workflow

1. Create a feature branch from
   `mission/ij-1.0-windows-fullstack-qualification`.
2. Make small logical commits with a message that says what changed and why.
3. Update `TASK_LEDGER.md` and `MISSION_STATE.json` for finished work.
4. Open a pull request that states the scope, the real test results, the
   evidence paths, known limitations and a reproduction command.
5. Never force-push and never rewrite history on a shared branch.

## Tests

Run `.venv/Scripts/python.exe -m unittest discover -s tests -v` for the
benchmark harness regression tests. The
[tool-calling benchmark guide](benchmarks/tool_calling/README.md) gives the
commands for collecting real model and GPU evidence on the physical
qualification machine. Mock-based CI, when added, is labelled as mock.
A personal Windows machine is never registered as a public self-hosted runner.
