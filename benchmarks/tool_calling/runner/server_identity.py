"""Verify and record the identity of the managed local llama-server."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]


def read_json(path: pathlib.Path) -> dict:
  return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_of(path: pathlib.Path) -> str:
  with path.open("rb") as handle:
    return hashlib.file_digest(handle, "sha256").hexdigest()


def server_identity(base_url: str, alias: str) -> tuple[dict, dict, dict]:
  state = read_json(ROOT / ".runtime/llama-server/server.json")
  engine = read_json(ROOT / "configs/llama_cpp/engine.json")
  model_file = ROOT / state["model_file"]
  executable = ROOT / state["exe"]
  if (
      state.get("status") != "PASS" or not state.get("owns_port")
      or base_url != f"http://{state['host']}:{state['port']}"
  ):
    raise ValueError("Expected the ready managed llama-server on its recorded loopback address")

  # Check the current listener and process image; server.json can outlive the process.
  command = (
      f"$listeners = @(Get-NetTCPConnection -LocalPort {int(state['port'])} -State Listen -ErrorAction Stop); "
      "$listeners | Select-Object -ExpandProperty OwningProcess -Unique; "
      f"(Get-Process -Id {int(state['pid'])} -ErrorAction Stop).Path"
  )
  process = subprocess.run(
      ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
      capture_output=True, text=True, check=True, timeout=30,
  )
  owner, *image = process.stdout.strip().splitlines()
  if owner != str(state["pid"]) or len(image) != 1 or pathlib.Path(image[0]) != executable:
    raise ValueError("The current listener does not match the managed process")

  with urllib.request.urlopen(base_url + "/props", timeout=10) as reply:
    props = json.load(reply)
  build_tag, _, build_commit = props["build_info"].partition("-")
  if (
      build_tag != engine["build_tag"] or len(build_commit) < 8
      or not engine["build_commit"].startswith(build_commit) or props["model_alias"] != alias
      or pathlib.Path(props["model_path"]) != model_file
      or not props["chat_template_caps"]["supports_tool_calls"]
  ):
    raise ValueError("Live server build, model or tool-call capabilities do not match the managed launch")

  backend = state["backend"]
  install = read_json(ROOT / "evidence/IJ0/engine_install.json")
  backend_install = next(item for item in install["backends"] if item["backend"] == backend)
  executable_sha = sha256_of(executable)
  if install["build_tag"] != engine["build_tag"] or executable_sha != backend_install["exe_sha256"]:
    raise ValueError("The current llama-server executable differs from the pinned installation")
  manifest = read_json(ROOT / "models/model_manifest.json")
  model = next(
      (source, item)
      for source in manifest["models"] for item in source["files"]
      if ROOT / source["local_dir"] / item["path"] == model_file
  )
  source, entry = model
  model_sha = sha256_of(model_file)
  if model_sha != entry["sha256"]:
    raise ValueError("The current model file differs from the ModelScope manifest")

  gpu = None
  if backend in ("vulkan", "rocm"):
    if not state.get("layers_offloaded"):
      raise ValueError("GPU inference requires nonzero GPU offload")
    devices = [
        match.groups()
        for line in state["allocation_log_lines"]
        if (match := re.search(r"using device ((?:Vulkan|ROCm)\d+) \((.+?)\) \(", line))
    ]
    if len(devices) != 1:
      raise ValueError("Cannot identify the GPU in the current server log")
    device, name = devices[0]
    gpu = {"device": device, "name": name}
    if name == "AMD Radeon(TM) 8060S Graphics":
      gpu["architecture"] = "gfx1151"

  binaries = ["llama-server-impl.dll", "llama-common.dll", "llama.dll"]
  if backend in ("vulkan", "rocm"):
    binaries.append({"vulkan": "ggml-vulkan.dll", "rocm": "ggml-hip.dll"}[backend])
  arguments = state["arguments"].copy()
  log_option = arguments.index("--log-file")
  del arguments[log_option : log_option + 2]
  arguments = [value.replace(str(ROOT), "<REPO>") for value in arguments]
  return (
      {
          **{key: engine[key] for key in ("build_tag", "build_commit", "stable_release_tag")},
          "exe_sha256": executable_sha,
          "dll_sha256": {name: sha256_of(executable.parent / name) for name in binaries},
      },
      {
          **{key: state.get(key) for key in (
              "backend", "context_length", "parallel_slots", "layers_offloaded", "layers_total",
              "gpu_layers", "reasoning_format",
          )},
          "gpu": gpu,
          "model_alias": alias,
          "model_file": state["model_file"],
          "modelscope_id": source["model_id"],
          "modelscope_revision": source["revision"],
          "model_sha256": model_sha,
          "chat_template_sha256": hashlib.sha256(props["chat_template"].encode("utf-8")).hexdigest(),
          "launch_arguments_sha256": hashlib.sha256(json.dumps(arguments).encode("utf-8")).hexdigest(),
      },
      {"pid": state["pid"], "started_utc": state["started_utc"]},
  )
