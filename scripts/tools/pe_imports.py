#!/usr/bin/env python3
"""List the imported DLLs of a Windows PE file and where each one resolves.

Used to record the runtime dependencies of a llama.cpp build and to explain a
backend DLL that refuses to load. Only headers are read, so it also works on
the multi-gigabyte ``ggml-hip.dll`` of the ROCm release.

Usage:
    python scripts/tools/pe_imports.py FILE [FILE ...] [--json OUT]
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import re
import struct
import sys
import winreg

PAGE_SIZE = 4096


class PeFile:
  def __init__(self, path: pathlib.Path):
    self.path = path
    self._handle = path.open("rb")
    handle = self._handle
    handle.seek(0x3C)
    pe_offset = struct.unpack("<I", handle.read(4))[0]
    handle.seek(pe_offset)
    assert handle.read(4) == b"PE\0\0", "not a PE file"
    machine, section_count, _, _, _, optional_size, _ = struct.unpack("<HHIIIHH", handle.read(20))
    optional = handle.read(optional_size)
    assert struct.unpack_from("<H", optional, 0)[0] == 0x20B, "only PE32+ is supported"
    self.number_of_rva_and_sizes = struct.unpack_from("<I", optional, 108)[0]
    directory_offset = 112
    self.directories = [
        struct.unpack_from("<II", optional, directory_offset + 8 * i)
        for i in range(self.number_of_rva_and_sizes)
    ]
    self.sections = []
    for _ in range(section_count):
      name, virtual_size, virtual_address, raw_size, raw_offset = struct.unpack(
          "<8sIIII", handle.read(24)
      )
      rest = handle.read(16)
      characteristics = struct.unpack_from("<I", rest, 12)[0]
      self.sections.append((name.rstrip(b"\0").decode(errors="replace"), virtual_size, virtual_address, raw_size, raw_offset, characteristics))

  def offset_of(self, rva: int) -> int:
    for _, virtual_size, virtual_address, raw_size, raw_offset, characteristics in self.sections:
      span = max(virtual_size, raw_size)
      if virtual_address <= rva < virtual_address + span:
        if characteristics & 0x200:  # IMAGE_SCN_MEM_DISCARDABLE or uninitialised
          pass
        delta = rva - virtual_address
        return raw_offset + delta if delta < raw_size else -1
    return -1

  def read(self, rva: int, size: int) -> bytes:
    offset = self.offset_of(rva)
    if offset < 0:
      return b"\0" * size
    self._handle.seek(offset)
    return self._handle.read(size)

  def cstring(self, rva: int) -> str:
    offset = self.offset_of(rva)
    self._handle.seek(offset)
    out = bytearray()
    while True:
      char = self._handle.read(1)
      if char in (b"\0", b""):
        break
      out += char
    return out.decode(errors="replace")

  def imports(self) -> list[str]:
    if len(self.directories) < 2 or self.directories[1][0] == 0:
      return []
    rva = self.directories[1][0]
    names = []
    while True:
      descriptor = self.read(rva, 20)
      if descriptor == b"\0" * 20:
        break
      name_rva = struct.unpack_from("<I", descriptor, 12)[0]
      names.append(self.cstring(name_rva))
      rva += 20
    return names

  def close(self) -> None:
    self._handle.close()


def system_directories() -> list[str]:
  with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
    path = winreg.QueryValueEx(key, "Path")[0]
  system_root = os.environ.get("SystemRoot", r"C:\Windows")
  dirs = [os.path.join(system_root, "System32"), os.path.join(system_root), system_root]
  dirs += [p for p in path.split(";") if p]
  return [os.path.expandvars(p) for p in dirs]


def redact(text: str) -> str:
  """Replaces the user directory in a path with a placeholder."""
  return re.sub(
      r"(?i)Users[\\/]+" + re.escape(getpass.getuser()) + r"(?=[\\/]|$)",
      lambda m: m.group(0)[: m.group(0).lower().index("users") + 5] + "<REDACTED>",
      text,
  )


def describe(path: pathlib.Path, search_dirs: list[str]) -> dict:
  pe = PeFile(path)
  try:
    imports = pe.imports()
    sections = [
        {"name": n, "virtual_size": v, "raw_size": r}
        for n, v, _, r, _, _ in pe.sections
    ]
  finally:
    pe.close()
  resolved = []
  for name in imports:
    # API sets (api-ms-win-*, ext-ms-*) are virtual DLLs that the Windows
    # loader maps onto system DLLs; they never exist as files.
    if name.lower().startswith(("api-ms-", "ext-ms-")):
      resolved.append({"dll": name, "found_in": "api-set"})
      continue
    candidates = [path.parent] + [pathlib.Path(d) for d in search_dirs]
    found = next((d / name for d in candidates if (d / name).is_file()), None)
    resolved.append({"dll": name, "found_in": redact(str(found)) if found else None})
  return {
      "file": path.name,
      "size": path.stat().st_size,
      "sections": sections,
      "imports": resolved,
      "missing": [r["dll"] for r in resolved if r["found_in"] is None],
  }


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("files", nargs="+")
  parser.add_argument("--json", help="write the full result to this file")
  args = parser.parse_args()

  search_dirs = system_directories()
  results = []
  for item in args.files:
    path = pathlib.Path(item).resolve()
    result = describe(path, search_dirs)
    results.append(result)
    print(f"{path.name}: {result['size']:,} bytes, {len(result['imports'])} imported DLLs")
    for section in result["sections"]:
      if section["virtual_size"] >= 64 * 1024 * 1024 or section["raw_size"] >= 64 * 1024 * 1024:
        print(f"  large section {section['name']}: raw {section['raw_size'] / 1e9:.2f} GB, virtual {section['virtual_size'] / 1e9:.2f} GB")
    for entry in result["imports"]:
      location = entry["found_in"] or "NOT FOUND"
      print(f"  {entry['dll']:<28} {location}")
  if args.json:
    pathlib.Path(args.json).write_text(
        json.dumps({"files": results}, indent=2) + "\n", encoding="utf-8"
    )
  return 0 if all(not r["missing"] for r in results) else 1


if __name__ == "__main__":
  sys.exit(main())
