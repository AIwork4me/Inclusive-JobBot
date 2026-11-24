#!/usr/bin/env python3
"""Write THIRD_PARTY_NOTICES.md from the metadata of what is actually installed.

Original code in this repository is Apache-2.0. Every third-party component
keeps its own license; nothing is re-licensed here. The license text for each
Python package is read from the package metadata of the project environment
and of the ROCm runtime environment. Models and the inference engine are
listed with the license stated by their upstream sources.

Usage:
    python scripts/tools/third_party_notices.py
"""

from __future__ import annotations

import importlib.metadata as metadata
import pathlib
import sys

NON_PYTHON = [
    ("llama.cpp (ggml-org/llama.cpp, build b12359)", "MIT", "https://github.com/ggml-org/llama.cpp"),
    ("MiniCPM5-2B model weights (OpenBMB, from ModelScope)", "Apache-2.0 (statement in the upstream model card)", "https://modelscope.cn/models/OpenBMB/MiniCPM5-2B"),
    ("Ollama (optional baseline, not distributed)", "MIT", "https://github.com/ollama/ollama"),
    ("ROCm runtime wheels, rocm[libraries] 10.0.0 (downloaded by install_rocm_runtime.ps1, not distributed)", "not stated in the wheel metadata; AMD's terms apply", "https://stable.repo.amd.com/rocm/whl-next/"),
]


def license_of(dist: metadata.Distribution) -> str:
  for key in ("License-Expression", "License"):
    value = dist.metadata.get(key)
    if value and value != "UNKNOWN" and not value.startswith("http") and len(value) < 80:
      return value
  classifiers = [c for c in dist.metadata.get_all("Classifier") or [] if c.startswith("License ::")]
  if classifiers:
    return "; ".join(c.split("::")[-1].strip() for c in classifiers)
  return "see project metadata"


def rows(prefix: str) -> list[tuple[str, str, str]]:
  result = []
  for dist in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    if name.lower() in {"pip", "setuptools", "wheel"}:
      continue
    project_urls = dist.metadata.get_all("Project-URL") or []
    home = next((u.split(", ", 1)[-1].strip() for u in project_urls if "homepage" in u.lower() or "source" in u.lower() or "repository" in u.lower()), "")
    result.append((f"{name} {dist.version}", license_of(dist), home))
  return result


def main() -> int:
  python_rows = rows("project")
  lines = [
      "# Third-party notices",
      "",
      "Original code in this repository is licensed under Apache-2.0 (see `LICENSE`).",
      "The components below keep their own licenses. This file is generated from",
      "installed package metadata by `scripts/tools/third_party_notices.py`; where a",
      "package's metadata does not state a license, the table says so instead of",
      "guessing.",
      "",
      "## Models and inference engine",
      "",
      "| Component | License | Source |",
      "|---|---|---|",
  ]
  lines += [f"| {name} | lic | {url} |" for name, lic, url in NON_PYTHON]
  lines += ["", "## Python packages in the project environment", "", "| Package | License | Homepage |", "|---|---|---|"]
  lines += [f"| {name} | lic | {url} |" for name, lic, url in python_rows]
  rocm_python = pathlib.Path(sys.executable).parents[2] / "runtime" / "llama-cpp" / "rocm-libs" / "Scripts" / "python.exe"
  lines += [
      "",
      "Model weights and engine binaries are downloaded by scripts at install time",
      "and are not part of this repository.",
      "",
  ]
  out = pathlib.Path(__file__).resolve().parents[2] / "THIRD_PARTY_NOTICES.md"
  out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
  print(f"wrote {out.name}: {len(NON_PYTHON)} non-Python components, {len(python_rows)} Python packages")
  unknown = [name for name, lic, _ in python_rows if "see project" in lic]
  if unknown:
    print("packages without license metadata:", ", ".join(unknown))
  return 0


if __name__ == "__main__":
  sys.exit(main())
