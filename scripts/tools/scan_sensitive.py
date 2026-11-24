#!/usr/bin/env python3
"""Refuses to let sensitive or non-portable content into the repository.

Checks every file git would commit:

* local identities: user directory paths, the current account as a path
  component or Windows principal, the host name;
* credential-shaped strings: GitHub, Google, AWS, Slack, private key blocks;
* non-ASCII characters in ``scripts/windows/*.ps1``, which Windows PowerShell
  5.1 mis-decodes in BOM-less files;
* model weights and engine binaries, which must never be committed.

Exit status is non-zero when any finding is reported. Paths that are not
tracked and not staged are ignored, so local scratch files do not trigger.

Usage:
    python scripts/tools/scan_sensitive.py [--staged] [--root DIR]
"""

from __future__ import annotations

import argparse
import getpass
import os
import pathlib
import re
import socket
import subprocess
import sys

CREDENTIAL_PATTERNS = {
    "github_token": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"),
    "bearer_token_value": re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._\-]{20,}"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic_secret_assignment": re.compile(
        r"(?i)\b(api[_\-]?key|secret|password|token)\s*[:=]\s*[\"'][A-Za-z0-9/+_\-]{16,}[\"']\s*$"
    ),
}
BINARY_SUFFIXES = {".gguf", ".safetensors", ".pt", ".pth", ".onnx", ".bin", ".dll", ".exe", ".zip", ".part"}
TEXT_SUFFIXES = {
    "", ".py", ".ps1", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".log",
    ".csv", ".jsonl", ".jinja", ".gitignore", ".gitattributes", ".cfg", ".ini",
    ".ts", ".tsx", ".js", ".html", ".css", ".sh", ".ini",
}
SKIP_DIRECTORIES = {
    ".git", ".venv", ".tools", ".runtime", ".scratch", "node_modules",
    "__pycache__", ".pytest_cache", "models", "runtime",
}


def git_files(root: pathlib.Path, staged_only: bool) -> list[str]:
  command = ["git", "-C", str(root), "ls-files", "-z"]
  if staged_only:
    command.append("--cached")
  else:
    command += ["--cached", "--others", "--exclude-standard"]
  output = subprocess.run(command, capture_output=True, check=True).stdout.decode("utf-8")
  seen: list[str] = []
  for name in output.split("\0"):
    if name and name not in seen:
      seen.append(name)
  return seen


def identity_patterns() -> dict[str, re.Pattern]:
  patterns = {}
  user = getpass.getuser()
  host = socket.gethostname()
  if user:
    escaped = re.escape(user)
    patterns["user_path"] = re.compile(rf"(?i)users[\\/]+{escaped}(?=[\\/\"'\s]|$)")
    patterns["bash_user_path"] = re.compile(rf"(?i)/c/users/{escaped}(?=[/\"'\s]|$)")
    # Two backslashes cover the escaped form inside JSON and log text.
    patterns["principal"] = re.compile(rf"(?i)(?<![A-Za-z0-9_.\-])(?:{re.escape(os.environ.get('USERDOMAIN', host))}|{re.escape(host)})\\{{1,2}}{escaped}(?![A-Za-z0-9_.\-])")
  if host:
    patterns["host_name"] = re.compile(rf"(?i)(?<![A-Za-z0-9_.\-]){re.escape(host)}(?![A-Za-z0-9_.\-])")
  return patterns


def scan(root: pathlib.Path, names: list[str]) -> list[str]:
  findings = []
  identities = identity_patterns()
  for name in names:
    path = root / name
    suffix = path.suffix.lower()
    if suffix in BINARY_SUFFIXES and not name.startswith("scripts/"):
      findings.append(f"{name}: binary artifact must not be committed")
      continue
    if any(part in SKIP_DIRECTORIES for part in pathlib.PurePosixPath(name).parts) and suffix not in TEXT_SUFFIXES:
      continue
    if suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", "NOTICE", "AGENTS.md"}:
      continue
    try:
      text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
      findings.append(f"{name}: not UTF-8 text; review before committing")
      continue
    if name.startswith("scripts/windows/") and suffix == ".ps1":
      bad = [i + 1 for i, line in enumerate(text.splitlines()) if any(ord(c) > 127 for c in line)]
      if bad:
        findings.append(f"{name}: non-ASCII characters at line(s) {bad[:8]}; Windows PowerShell 5.1 cannot read them")
    for label, pattern in identities.items():
      for match in pattern.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        findings.append(f"{name}:{line}: local identity ({label})")
        break
    for label, pattern in CREDENTIAL_PATTERNS.items():
      match = pattern.search(text)
      if match:
        line = text.count("\n", 0, match.start()) + 1
        findings.append(f"{name}:{line}: credential-shaped string ({label})")
  return findings


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("--root", default=".")
  parser.add_argument("--staged", action="store_true", help="check only staged files")
  args = parser.parse_args()
  root = pathlib.Path(args.root).resolve()
  if not (root / ".git").exists():
    # Before the first commit there is no index; scan the working tree instead.
    names = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and not any(part in SKIP_DIRECTORIES for part in p.relative_to(root).parts)
    ]
  else:
    names = git_files(root, args.staged)
  findings = scan(root, sorted(names))
  for finding in findings:
    print(finding)
  print(f"scanned {len(names)} file(s): {len(findings)} finding(s)")
  return 1 if findings else 0


if __name__ == "__main__":
  sys.exit(main())
