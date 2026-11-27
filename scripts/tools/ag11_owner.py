"""Normal-token controls and redacted offline review for owner-assisted AG-11."""

import argparse
from collections import defaultdict
import ctypes
from hashlib import file_digest
from ipaddress import ip_address
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
FAMILIES = {"tcp4", "tcp6", "udp4", "udp6"}
LOSS_KEYS = ("events_lost", "log_buffers_lost", "realtime_buffers_lost")
RUN_ID = re.compile(r"[a-f0-9]{32}")


def assess_observation(rows, run, capture):
    """Apply the fixed disposition to normalized, privately retained ETW events."""
    result = {"ag11_status": "BLOCKED", "observation_status": "BLOCKED", "descendants": 0,
              "controls_passed": 0, "non_loopback": 0, "loopback": {key: 0 for key in sorted(FAMILIES)}}

    def report(reason):
        return result | {"reason": reason}

    if (capture.get("trace_complete") is not True or run.get("success") is not True
            or any(type(capture.get(key)) is not int or capture[key] != 0 for key in LOSS_KEYS)):
        return report("CAPTURE_OR_COUNTERS_INCOMPLETE")
    try:
        start, stop = capture["start"], capture["stop"]
        starts, ends, sends, unknown = {}, {}, [], []
        by_pid = defaultdict(list)
        for row in rows:
            kind = row["type"]
            if kind in ("start", "stop"):
                records = starts if kind == "start" else ends
                if row["sequence"] in records:
                    return report("DUPLICATE_PROCESS_IDENTITY")
                records[row["sequence"]] = row
                if kind == "start":
                    by_pid[row["pid"]].append(row)
            elif kind == "send":
                sends.append(row)
            elif kind == "unattributed":
                unknown.append(row["time"])
            else:
                return report("UNSUPPORTED_EVENT")

        def identify(marker):
            matches = [row for row in by_pid[marker["pid"]] if row["created"] == marker["created"]]
            if len(matches) != 1:
                raise ValueError
            return matches[0]["sequence"]

        root = identify(run)
        children = defaultdict(list)
        for row in starts.values():
            children[row["parent"]].append(row["sequence"])
        subjects, pending = set(), [root]
        while pending:
            sequence = pending.pop()
            if sequence in subjects:
                return report("AMBIGUOUS_TREE")
            subjects.add(sequence)
            pending.extend(children[sequence])
        subject_by_pid = defaultdict(list)
        for sequence in subjects:
            subject_by_pid[starts[sequence]["pid"]].append(sequence)
        for row in starts.values():
            for candidate in subject_by_pid[row.get("parent_pid")]:
                if (starts[candidate]["created"] < row["created"] < ends[candidate]["ended"]
                        and row["parent"] != candidate):
                    return report("AMBIGUOUS_PARENT_IDENTITY")

        markers = run["controls"]
        if len(markers) != 2:
            return report("CONTROL_WINDOWS_INCOMPLETE")
        controls = [identify(marker) for marker in markers]
        if len(set(controls)) != 2 or set(controls) & subjects:
            return report("CONTROL_NOT_INDEPENDENT")
        tracked = subjects | set(controls)
        for sequence in tracked:
            created, ended = starts[sequence], ends[sequence]
            if (created["elevated"] is not False or ended["pid"] != created["pid"]
                    or ended["created"] != created["created"] or not start < created["created"] < ended["ended"] < stop):
                return report("INVALID_TOKEN_OR_LIFETIME")
            parent = created["parent"]
            if parent in subjects and not starts[parent]["created"] < created["created"] < ends[parent]["ended"]:
                return report("INVALID_PARENT_LIFETIME")
        first, last = starts[root]["created"], max(ends[sequence]["ended"] for sequence in subjects)
        if not ends[controls[0]]["ended"] < first <= last < starts[controls[1]]["created"]:
            return report("CONTROL_WINDOWS_INCOMPLETE")
        if any(start <= instant <= stop for instant in unknown):
            return report("UNATTRIBUTED_OR_UNSUPPORTED_EVENT")
        images = {starts[sequence]["image"].lower() for sequence in subjects - {root}}
        if "localharness.exe" not in images or "llama-server.exe" not in images:
            return report("EXPECTED_SDK_AND_MODEL_CHILDREN_MISSING")

        tracked_pids = {starts[sequence]["pid"] for sequence in tracked}
        for pid in tracked_pids:
            lifetimes = sorted(by_pid[pid], key=lambda row: row["created"])
            if any(ends[earlier["sequence"]]["ended"] >= later["created"]
                   for earlier, later in zip(lifetimes, lifetimes[1:])):
                return report("AMBIGUOUS_NETWORK_PID_LIFETIME")
        observed = defaultdict(set)
        sdk_traffic, model_traffic = False, False
        for flow in sends:
            pid, instant = flow["pid"], flow["time"]
            if pid not in tracked_pids:
                continue
            possible = [row["sequence"] for row in by_pid[pid] if row["created"] <= instant
                        and instant < ends.get(row["sequence"], {}).get("ended", stop)]
            if len(possible) != 1:
                return report("AMBIGUOUS_NETWORK_PID_LIFETIME")
            sequence = possible[0]
            if sequence not in tracked:
                continue
            family, address, port = flow["family"], ip_address(flow["remote"]), flow["port"]
            if family not in FAMILIES or address.version != int(family[-1]) or not 0 < port <= 65535:
                return report("UNSUPPORTED_NETWORK_EVENT")
            mapped = getattr(address, "ipv4_mapped", None)
            is_loopback = address.is_loopback or (mapped is not None and mapped.is_loopback)
            if sequence in controls:
                observed[sequence].add((family, str(address), port))
            elif not is_loopback:
                result["non_loopback"] += 1
            else:
                result["loopback"][family] += 1
                if family.startswith("tcp"):
                    image = starts[sequence]["image"].lower()
                    sdk_traffic |= image == "localharness.exe"
                    model_traffic |= image == "python.exe" and port == run["port"]
        result["descendants"] = len(subjects) - 1
        for sequence, marker in zip(controls, markers, strict=True):
            targets = marker["targets"]
            if targets.keys() == FAMILIES and all((family, *target) in observed[sequence] for family, target in targets.items()):
                result["controls_passed"] += 1
        if result["non_loopback"]:
            result["observation_status"] = "FAIL"
            return report("OBSERVED_NON_LOOPBACK_EGRESS")
        if result["controls_passed"] != 2 or not sdk_traffic or not model_traffic:
            return report("CONTROL_OR_SDK_LOOPBACK_NOT_OBSERVED")
        result["observation_status"] = "PASS"
        return report("TCP_UDP_OBSERVATION_READY_FOR_INDEPENDENT_REVIEW")
    except (KeyError, TypeError, ValueError):
        return report("MISSING_OR_INVALID_IDENTITY_EVIDENCE")


def _atomic_json(path, value):
    partial = path.with_suffix(path.suffix + ".partial")
    with partial.open("x", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True)
    partial.replace(path)


def _file_hash(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def _process_birth(handle):
    times = [ctypes.c_uint64() for _ in range(4)]
    get_times = ctypes.windll.kernel32.GetProcessTimes
    get_times.argtypes = (ctypes.c_void_p, *(ctypes.POINTER(ctypes.c_uint64),) * 4)
    if not get_times(handle, *(ctypes.byref(value) for value in times)):
        raise OSError("process creation time unavailable")
    return times[0].value


def _loopback_control():
    targets = {}
    for version, family, address in ((4, socket.AF_INET, "127.0.0.1"), (6, socket.AF_INET6, "::1")):
        for protocol, socktype in (("tcp", socket.SOCK_STREAM), ("udp", socket.SOCK_DGRAM)):
            with socket.socket(family, socktype) as receiver, socket.socket(family, socktype) as client:
                receiver.settimeout(3)
                client.settimeout(3)
                receiver.bind((address, 0))
                endpoint = receiver.getsockname()
                payload = b"ag11-loopback-control"
                if protocol == "tcp":
                    receiver.listen(1)
                    client.connect(endpoint)
                    client.sendall(payload)
                    peer, _ = receiver.accept()
                    with peer, peer.makefile("rb") as reader:
                        observed = reader.read(len(payload))
                else:
                    client.sendto(payload, endpoint)
                    observed, _ = receiver.recvfrom(1024)
                if observed != payload:
                    raise ValueError("loopback canary payload mismatch")
                targets[f"{protocol}{version}"] = [address, endpoint[1]]
    return targets


def run_normal(root, assets, candidate, port):
    if os.name != "nt" or ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError("the SDK runner requires an ordinary Windows token")
    from benchmarks.slm10.sdk_adapter_development import require_idle_controller

    require_idle_controller()
    if not 1 <= port <= 65535:
        raise ValueError("the local diagnostic requires a valid dedicated port")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check:
        check.bind(("127.0.0.1", port))
    ready = json.loads((root / "ready.json").read_bytes())
    now = time.time_ns() // 100 + 116444736000000000
    if ready["run_id"] != root.name or not ready["start"] < now < ready["deadline"] or (root / "collector.json").exists():
        raise ValueError("the private collector window is not active")
    if (root / "run.json").exists():
        raise ValueError("the capture already has a normal-token run")
    with (root / "normal.claim").open("x", encoding="ascii"):
        pass
    record = {"success": False, "candidate": candidate, "port": port, "controls": []}

    def control():
        with subprocess.Popen([sys.executable, "-m", __spec__.name, "control"], cwd=ROOT,
                              stdout=subprocess.PIPE) as process:
            born = _process_birth(int(process._handle))
            raw, _ = process.communicate()
            if process.returncode:
                raise ValueError("loopback control failed")
            return {"pid": process.pid, "created": born, "targets": json.loads(raw)}

    try:
        record["controls"].append(control())
        diag = root / "sdk"
        command = [sys.executable, "-m", "benchmarks.slm10.native_diagnostics", candidate, "--profile", "native-on",
                   "--assets", str(assets.resolve(strict=True)), "--output", str(diag), "--port", str(port)]
        with (root / "sdk-private.log").open("xb") as log:
            with subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT) as process:
                record.update(pid=process.pid, created=_process_birth(int(process._handle)))
                return_code = process.wait()
        record["controls"].append(control())
        if return_code == 0:
            report = diag / "report.json"
            sdk = json.loads(report.read_bytes())
            record.update(
                success=(sdk["gpu_execution"] == "PASS" and sdk["cases"]["AG-04"]["status"] == "PASS"),
                sdk_report_sha256=_file_hash(report),
            )
    finally:
        _atomic_json(root / "run.json", record)
    return 0 if record["success"] else 1


def stop_own_session(name):
    if os.name != "nt" or not ctypes.windll.shell32.IsUserAnAdmin() or not re.fullmatch(r"JobbotAG11-[a-f0-9]{32}", name):
        raise ValueError("owned elevated trace name required")

    class Wnode(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint32), ("provider", ctypes.c_uint32), ("context", ctypes.c_uint64),
                    ("stamp", ctypes.c_int64), ("guid", ctypes.c_byte * 16), ("client_context", ctypes.c_uint32),
                    ("flags", ctypes.c_uint32)]

    class Properties(ctypes.Structure):
        _fields_ = [("node", Wnode)] + [(name, ctypes.c_uint32) for name in (
            "buffer_size", "minimum_buffers", "maximum_buffers", "maximum_file_size", "log_file_mode", "flush_timer",
            "enable_flags", "age_limit", "number_of_buffers", "free_buffers", "events_lost", "buffers_written",
            "log_buffers_lost", "realtime_buffers_lost")] + [("thread", ctypes.c_void_p),
            ("log_file_name_offset", ctypes.c_uint32), ("logger_name_offset", ctypes.c_uint32)]

    control = ctypes.WinDLL("advapi32").ControlTraceW
    control.argtypes = (ctypes.c_uint64, ctypes.c_wchar_p, ctypes.POINTER(Properties), ctypes.c_uint32)
    control.restype = ctypes.c_uint32

    def counters(operation):
        memory = ctypes.create_string_buffer(ctypes.sizeof(Properties) + 4096)
        props = Properties.from_buffer(memory)
        props.node.size = len(memory)
        props.node.flags = 0x00020000  # WNODE_FLAG_TRACED_GUID
        props.logger_name_offset = ctypes.sizeof(Properties)
        props.log_file_name_offset = props.logger_name_offset + 2048
        status = control(0, name, ctypes.byref(props), operation)
        return status, {key: getattr(props, key) for key in (*LOSS_KEYS, "buffers_written")}

    queried, before = counters(0)  # EVENT_TRACE_CONTROL_QUERY
    stopped, after = counters(1)  # EVENT_TRACE_CONTROL_STOP
    valid = queried == stopped == 0 and all(after[key] >= before[key] for key in before)
    return {"query_status": queried, "stop_status": stopped,
            **{key: after[key] if valid else None for key in after}}


def replay(root):
    try:
        capture_record, run_record = root / "collector.json", root / "run.json"
        collector = json.loads(capture_record.read_bytes())
        run = json.loads(run_record.read_bytes())
        decoded = root / "events.ndjson"
        raw_hash = _file_hash(root / "scope.etl")
        if collector.get("raw_etl_sha256") != raw_hash:
            raise ValueError("raw ETW evidence digest differs from collector record")
        decode = json.loads((root / "decode.json").read_bytes())
        if decode != {"raw_etl_sha256": raw_hash, "normalized_sha256": _file_hash(decoded)}:
            raise ValueError("normalized ETW evidence differs from its decode record")
        sdk_hash = _file_hash(root / "sdk/report.json")
        if sdk_hash != run.get("sdk_report_sha256"):
            raise ValueError("SDK evidence differs from the normal-token run record")
        with decoded.open(encoding="utf-8-sig") as source:
            report = assess_observation((json.loads(line) for line in source), run, collector)
        report.update(raw_etl_sha256=raw_hash, normalized_sha256=decode["normalized_sha256"], sdk_report_sha256=sdk_hash,
                      collector_record_sha256=_file_hash(capture_record), run_record_sha256=_file_hash(run_record))
    except (OSError, KeyError, TypeError, ValueError):
        report = {"ag11_status": "BLOCKED", "observation_status": "BLOCKED", "reason": "EVIDENCE_CHAIN_UNAVAILABLE"}
    if root.is_dir():
        _atomic_json(root / "redacted-observation.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["observation_status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stop = commands.add_parser("stop-owned")
    stop.add_argument("session")
    commands.add_parser("control")
    for name in ("run", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--run-id", required=True)
        if name == "run":
            command.add_argument("--assets", required=True, type=Path)
            command.add_argument("--candidate", choices=("A", "B", "D"), required=True)
            command.add_argument("--port", type=int, default=18754)
    args = parser.parse_args()
    if args.command == "stop-owned":
        print(json.dumps(stop_own_session(args.session)))
        return 0
    if args.command == "control":
        print(json.dumps(_loopback_control()))
        return 0
    if not RUN_ID.fullmatch(args.run_id):
        parser.error("run ID requires 32 lowercase hexadecimal digits")
    root = ROOT / ".runtime/ag11" / args.run_id
    if args.command == "run":
        return run_normal(root, args.assets, args.candidate, args.port)
    return replay(root)


if __name__ == "__main__":
    raise SystemExit(main())
