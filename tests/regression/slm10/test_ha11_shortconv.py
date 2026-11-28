from struct import pack, unpack

import pytest

from benchmarks.slm10.ha11_shortconv import compare_states, read_shortconv


def slot_state(*, row_bytes=8, value=1.0):
    return (pack("<5I", 0x67677371, 4, 2, 17, 32) + b"opaque attention blocks"
            + pack("<4I", 1, 1, 0, 0) + pack("<I", 3)
            + pack("<IQ2f", 0, row_bytes, value, 2.0) + pack("<IQ", 0, 0))


def test_shortconv_extracts_only_the_native_recurrent_row():
    rows, metadata = read_shortconv(slot_state(), state_layers=[1], block_count=3, width=2, prefix=[17])
    assert unpack("<2f", rows[1]) == (1.0, 2.0)
    assert metadata["token_count"] == 2
    assert metadata["position"] == 1


def test_shortconv_reads_packed_server_tokens_and_excludes_checkpoint_appendix():
    packed = pack("<3I", 0x67677371, 4, 6) + pack("<i5I", -1, 1, 2, 17, 32, 0)
    appendix = b"SCKP" + pack("<2IqiiQ", 1, 1, 1, 0, 0, 4) + b"fake" + pack("<2Q", 0, 0)
    rows, metadata = read_shortconv(packed + slot_state()[20:] + appendix, state_layers=[1],
                                    block_count=3, width=2, prefix=[17])
    assert unpack("<2f", rows[1]) == (1.0, 2.0)
    assert metadata["token_count"] == 2
    assert metadata["checkpoint_count"] == 1


@pytest.mark.parametrize("data,prefix", [
    (slot_state() + b"x", [17]),
    (slot_state(row_bytes=4), [17]),
    (slot_state(value=float("nan")), [17]),
    (slot_state(), [42]),
    (slot_state()[:-1], [17]),
])
def test_shortconv_rejects_unsupported_or_corrupt_snapshot(data, prefix):
    with pytest.raises(ValueError):
        read_shortconv(data, state_layers=[1], block_count=3, width=2, prefix=prefix)


def test_shortconv_state_reports_bit_and_numeric_differences_separately():
    original = {1: pack("<2f", 0.0, 1.0), 2: pack("<2f", 4.0, 2.0)}
    observed = {1: pack("<2f", -0.0, 1.0), 2: pack("<2f", 1.0, 1.0)}
    result = compare_states(original, observed)
    assert result["byte_identical_layers"] == 0
    assert result["layers"]["1"]["max_abs_delta"] == 0
    assert result["layers"]["2"]["max_abs_delta"] == 3
    assert result["layers"]["2"]["mean_abs_delta"] == 2
