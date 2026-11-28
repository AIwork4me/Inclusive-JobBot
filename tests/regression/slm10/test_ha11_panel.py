from collections import Counter

from benchmarks.slm10.ha11_panel import plan


def test_transfer_panel_preserves_480_and_adds_240_with_balanced_first_positions():
    batches, metadata = plan("transfer")
    rows = [row for batch in batches for row in batch]
    assert metadata["planned"] == len(rows) == len({row["slot_id"] for row in rows}) == 720
    assert Counter(row["profile"] for row in rows) == {
        "DIRECT": 240, "ORIGINAL_SDK": 240, "SDK_MATCHED_CONTEXT_PhaseAware": 240,
    }
    assert len({row["case_id"] for row in rows}) == 60
    for batch in batches:
        assert Counter(row["profile"] for row in batch[::3]) == {
            "DIRECT": 5, "ORIGINAL_SDK": 5, "SDK_MATCHED_CONTEXT_PhaseAware": 5,
        }
    for start in range(0, len(batches), 4):
        assert len({batch[0]["weight"] for batch in batches[start:start + 4]}) == 4


def test_full_panel_uses_new_matched_original_and_all_frozen_repeats():
    batches, metadata = plan("tc-extension")
    rows = [row for batch in batches for row in batch]
    assert metadata["planned"] == len(rows) == len({row["slot_id"] for row in rows}) == 6600
    for weight in ("Original", "HA-O", "HA-P", "HA-H"):
        actual = [row for row in rows if row["weight"] == weight]
        assert Counter(row["track"] for row in actual) == {
            "direct_first": 500, "sdk_first": 500, "sdk_streaming": 500, "sdk_repeat": 150,
        }
        assert Counter(row["seed"] for row in actual if row["track"] == "sdk_repeat") == {101: 50, 211: 50, 307: 50}
