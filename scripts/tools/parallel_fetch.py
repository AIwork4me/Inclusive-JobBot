#!/usr/bin/env python3
"""Parallel HTTP range downloader with mandatory SHA256 verification (stdlib only).

Some networks throttle every connection to a GitHub release asset to roughly
100 KB/s. This tool fetches one large file with many concurrent range requests
and refuses to keep the result unless its SHA256 matches the expected digest.

The expected digest must come from a trusted source, for example the release
asset digest returned by `gh api` or the project's published checksum file.
The download host itself is not trusted to deliver the right bytes.

Usage:
    python scripts/tools/parallel_fetch.py URL OUT --sha256 HEX [--workers 24]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import os
import sys
import threading
import time
import urllib.error
import urllib.request

USER_AGENT = "inclusive-jobbot-parallel-fetch"
DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024
DEFAULT_WORKERS = 24
DEFAULT_RETRIES = 8
TRANSFER_ERRORS = (OSError, http.client.HTTPException)


class ChunkFailure(Exception):
  """A single range could not be fetched within the retry budget."""


def open_range(url: str, byte_range: str):
  """Opens a GET with a Range header and returns the response."""
  request = urllib.request.Request(
      url, headers={"Range": byte_range, "User-Agent": USER_AGENT}
  )
  return urllib.request.urlopen(request, timeout=60)


def resolve_total_size(url: str) -> int:
  """Returns the total object size using a one-byte range probe."""
  with open_range(url, "bytes=0-0") as response:
    content_range = response.headers.get("Content-Range", "")
    if response.status != 206 or "/" not in content_range:
      raise RuntimeError(f"server does not honour range requests: {content_range!r}")
    return int(content_range.rsplit("/", 1)[1])


def fetch_chunk(url: str, path: str, index: int, start: int, end: int, retries: int) -> tuple[int, int]:
  """Downloads bytes [start, end] into ``path`` and returns (index, byte count)."""
  expected = end - start + 1
  last_error: Exception | None = None
  for attempt in range(1, retries + 1):
    try:
      with open_range(url, f"bytes={start}-{end}") as response:
        content_range = response.headers.get("Content-Range", "")
        if response.status != 206 or not content_range.startswith(f"bytes {start}-"):
          raise ChunkFailure(f"unexpected range reply {content_range!r}")
        received = 0
        with open(path, "r+b") as handle:
          handle.seek(start)
          while True:
            block = response.read(256 * 1024)
            if not block:
              break
            handle.write(block)
            received += len(block)
      if received != expected:
        raise ChunkFailure(f"short read {received} != {expected}")
      return index, received
    except TRANSFER_ERRORS as error:
      last_error = error
    time.sleep(min(2**attempt, 30))
  raise ChunkFailure(f"chunk {index} failed after {retries} attempts: {last_error}")


def sha256_of(path: str) -> str:
  digest = hashlib.sha256()
  with open(path, "rb") as handle:
    for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
      digest.update(block)
  return digest.hexdigest()


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
  parser.add_argument("url")
  parser.add_argument("out")
  parser.add_argument("--sha256", required=True, help="expected lowercase hex digest")
  parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
  parser.add_argument("--chunk-mb", type=int, default=DEFAULT_CHUNK_BYTES // (1024 * 1024))
  parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
  parser.add_argument("--rounds", type=int, default=6, help="re-queue rounds for failed chunks")
  args = parser.parse_args()

  expected = args.sha256.strip().lower()
  if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
    print("invalid --sha256 value", file=sys.stderr)
    return 2

  os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
  if os.path.isfile(args.out) and os.path.getsize(args.out) > 0:
    existing = sha256_of(args.out)
    if existing == expected:
      print(f"already present with matching sha256: {existing}")
      return 0
    print("existing file has a different sha256; it will be replaced", file=sys.stderr)
    os.remove(args.out)
  part_path = args.out + ".part"

  total = None
  for attempt in range(1, args.retries + 1):
    try:
      total = resolve_total_size(args.url)
      break
    except (*TRANSFER_ERRORS, RuntimeError) as error:
      print(f"size probe attempt {attempt} failed: {type(error).__name__}", flush=True)
      time.sleep(min(2**attempt, 30))
  if total is None:
    print("could not determine the object size", file=sys.stderr)
    return 1
  print(f"total bytes: {total:,}", flush=True)

  chunk = args.chunk_mb * 1024 * 1024
  pending = [
      (i, start, min(start + chunk, total) - 1)
      for i, start in enumerate(range(0, total, chunk))
  ]
  with open(part_path, "wb") as handle:
    handle.truncate(total)

  done_bytes = 0
  lock = threading.Lock()
  started = time.monotonic()
  # A chunk that exhausts its own retries is re-queued in the next round
  # instead of aborting the whole transfer.
  for round_number in range(1, args.rounds + 1):
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
      futures = {
          pool.submit(
              fetch_chunk, args.url, part_path, spec[0], spec[1], spec[2], args.retries
          ): spec
          for spec in pending
      }
      failed = []
      for future in concurrent.futures.as_completed(futures):
        spec = futures[future]
        try:
          _, count = future.result()
        except ChunkFailure as error:
          failed.append(spec)
          print(f"\nround {round_number}: {error}", file=sys.stderr, flush=True)
          continue
        with lock:
          done_bytes += count
          elapsed = max(time.monotonic() - started, 0.001)
          print(
              f"\r{done_bytes / total:6.1%}  {done_bytes / 1e6:8.1f}/{total / 1e6:.1f} MB"
              f"  {done_bytes / elapsed / 1e3:7.0f} KB/s   ",
              end="",
              flush=True,
          )
    if not failed:
      break
    pending = failed
    time.sleep(5)
  else:
    print(f"{len(pending)} chunks could not be fetched; kept {part_path}", file=sys.stderr)
    return 1
  print(flush=True)

  actual = sha256_of(part_path)
  if actual != expected:
    print(f"sha256 mismatch: expected {expected}, got {actual}", file=sys.stderr)
    print(f"the partial file was kept for inspection: {part_path}", file=sys.stderr)
    return 1
  os.replace(part_path, args.out)
  print(f"sha256 ok: {actual}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
