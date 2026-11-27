"""Hold the shared Windows GPU lease for a managed llama-server process."""

import argparse
import json
from pathlib import Path
import subprocess

from .gpu_lease import physical_gpu
from .windows_job import job_process


def write_ack(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_bytes())
    ack = args.request.with_suffix(".ack.json")
    binary = Path(request["binary"]).resolve(strict=True)
    if binary.name.casefold() != "llama-server.exe":
        parser.error("managed GPU executable must be llama-server.exe")
    try:
        with physical_gpu(mission_id=request["mission_id"], lease_owner="windows-managed-llama-server",
                          runtime_session=args.request.stem) as lease:
            with (Path(request["stdout"]).open("wb") as stdout,
                  Path(request["stderr"]).open("wb") as stderr,
                  job_process([str(binary), *request["arguments"]], cwd=binary.parent,
                              stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW) as process):
                write_ack(ack, {"status": "PASS", "server_pid": process.pid, "lease": lease})
                return process.wait()
    except (OSError, ValueError, RuntimeError) as error:
        if not ack.exists():
            write_ack(ack, {"status": "BLOCKED", "reason": type(error).__name__})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
