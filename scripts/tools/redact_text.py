#!/usr/bin/env python3
"""Redacts local identities from a text stream (stdin -> stdout).

Replaces the current user's directory path, the Windows principal form
HOST\\user, the host name, and the domain when it differs from the host. The
same rules are used by scripts/windows/common.ps1.

The replacement in `grep` on some Git Bash installations is not reliable for
backslash path patterns, so evidence that is produced by shell pipelines goes
through this tool instead.

Usage:
    cat server.log | python scripts/tools/redact_text.py > evidence.log
"""

from __future__ import annotations

import getpass
import os
import re
import socket
import sys

BOUNDARY_START = r"(?i)(?<![A-Za-z0-9_.\-])"


def patterns() -> list[tuple[re.Pattern, str]]:
  user = getpass.getuser()
  host = socket.gethostname()
  domain = os.environ.get("USERDOMAIN", "")
  rules: list[tuple[re.Pattern, str]] = []
  if user:
    escaped = re.escape(user)
    rules.append(
        (re.compile(r"(?i)(Users[\\/]+)" + escaped + r"(?=[\\/\"'\s]|$)"), r"\1<REDACTED>")
    )
    principals = [re.escape(p) for p in {domain, host} if p]
    if principals:
      rules.append(
          (re.compile(BOUNDARY_START + "(?:" + "|".join(principals) + r")\\{1,2}" + escaped + r"(?![A-Za-z0-9_.\-])"), "<REDACTED>")
      )
  if host:
    rules.append((re.compile(BOUNDARY_START + re.escape(host) + r"(?![A-Za-z0-9_.\-])"), "<HOST>"))
  if domain and domain != host:
    rules.append((re.compile(BOUNDARY_START + re.escape(domain) + r"(?![A-Za-z0-9_.\-])"), "<DOMAIN>"))
  return rules


def redact(text: str) -> str:
  for pattern, replacement in patterns():
    text = pattern.sub(replacement, text)
  return text


if __name__ == "__main__":
  data = sys.stdin.buffer.read().decode("utf-8", errors="replace")
  sys.stdout.buffer.write(redact(data).encode("utf-8"))
