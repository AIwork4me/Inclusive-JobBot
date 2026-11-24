# Models

Model weights are never committed. This directory holds local copies that
`scripts/windows/download_models_modelscope.ps1` fetches from ModelScope.

- `model_manifest.json` - pinned ModelScope repository revisions and the
  SHA256 of every file. Committed; the single source of truth for scripts.
- `MiniCPM5-2B-GGUF/` - `MiniCPM5-2B-F16.gguf`, `MiniCPM5-2B-Q8_0.gguf`,
  `MiniCPM5-2B-Q4_K_M.gguf` used by llama-server.
- `MiniCPM5-2B/` - the original BF16 safetensors, config, tokenizer and
  `chat_template.jinja`, kept as the reference for template checks and for the
  future DX-M2 migration package.

MiniCPM5-2B is released under Apache-2.0 (statement in the upstream model
card). Verify a local copy at any time:

```powershell
pwsh -File scripts/windows/download_models_modelscope.ps1 -VerifyOnly
```
