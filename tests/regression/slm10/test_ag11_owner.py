"""Independent software controls for AG-11 PID lifetime replay."""

from copy import deepcopy

import pytest


def source():
    rows = []

    def life(pid, sequence, start, end, *, parent=None, image="python.exe"):
        rows.extend((
            {"type": "start", "pid": pid, "sequence": sequence, "created": start,
             "parent": parent, "elevated": False, "image": image},
            {"type": "stop", "pid": pid, "sequence": sequence, "created": start, "ended": end},
        ))

    def flow(pid, instant, family, address, port):
        rows.append({"type": "send", "pid": pid, "time": instant, "family": family,
                     "remote": address, "port": port})

    def controls(pid, instant):
        targets = {"tcp4": ["127.0.0.1", 34001], "tcp6": ["::1", 34002],
                   "udp4": ["127.0.0.1", 34003], "udp6": ["::1", 34004]}
        for kind, (address, port) in targets.items():
            flow(pid, instant, kind, address, port)
        return targets

    life(100, 10, 100, 400)
    life(110, 11, 140, 350, parent=10, image="llama-server.exe")
    life(120, 12, 200, 300, parent=10, image="localharness.exe")
    flow(120, 240, "tcp4", "127.0.0.1", 37115)  # SDK to its ephemeral local provider adapter.
    flow(100, 245, "tcp4", "127.0.0.1", 18754)  # Adapter to the specific local model server.
    life(120, 20, 410, 450)
    flow(120, 420, "udp4", "192.0.2.5", 40000)  # PID reuse by a different process.
    life(201, 21, 30, 90)
    life(202, 22, 460, 490)
    controls_before = controls(201, 50)
    controls_after = controls(202, 470)
    capture = {"start": 10, "stop": 500, "events_lost": 0, "log_buffers_lost": 0,
               "realtime_buffers_lost": 0, "trace_complete": True}
    run = {"pid": 100, "created": 100, "port": 18754, "success": True,
           "controls": [{"pid": 201, "created": 30, "targets": controls_before},
                        {"pid": 202, "created": 460, "targets": controls_after}]}
    return rows, run, capture


def assess(rows, run, capture):
    from scripts.tools.ag11_owner import assess_observation

    return assess_observation(rows, run, capture)


def test_matches_short_lived_descendants_and_ignores_reused_pid():
    rows, run, capture = source()
    proof = assess(rows, run, capture)
    assert proof["observation_status"] == "PASS"
    assert proof["ag11_status"] == "BLOCKED"
    assert proof["descendants"] == 2
    assert proof["non_loopback"] == 0
    assert proof["controls_passed"] == 2


def test_replayed_non_loopback_send_fails_without_disclosing_target():
    rows, run, capture = source()
    rows.append({"type": "send", "pid": 120, "time": 250, "family": "udp6",
                 "remote": "2001:db8::5", "port": 6200})
    proof = assess(rows, run, capture)
    assert proof["observation_status"] == "FAIL" and proof["non_loopback"] == 1
    assert "2001:db8" not in str(proof) and "6200" not in str(proof)


@pytest.mark.parametrize("defect", ["loss", "missing_exit", "missing_family", "ambiguous", "elevated", "unattributed",
                                   "missing_model_route", "missing_sdk_route"])
def test_missing_trustworthy_evidence_stays_blocked(defect):
    rows, run, capture = deepcopy(source())
    if defect == "loss":
        capture["events_lost"] = 1
    if defect == "missing_exit":
        rows[:] = [row for row in rows if (row["type"], row.get("sequence")) != ("stop", 12)]
    if defect == "missing_family":
        rows[:] = [row for row in rows if not (row["pid"] == 202 and row.get("family") == "udp6")]
    if defect == "ambiguous":
        next(row for row in rows if row.get("sequence") == 20 and row["type"] == "start")["created"] = 260
    if defect == "elevated":
        next(row for row in rows if row.get("sequence") == 12 and row["type"] == "start")["elevated"] = True
    if defect == "unattributed":
        rows.append({"type": "unattributed", "time": 246, "pid": 0})
    if defect in {"missing_model_route", "missing_sdk_route"}:
        port = 18754 if defect == "missing_model_route" else 37115
        rows[:] = [row for row in rows if row.get("port") != port]
    assert assess(rows, run, capture)["observation_status"] == "BLOCKED"
