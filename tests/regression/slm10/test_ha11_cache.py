import pytest

from benchmarks.slm10.ha11_cache import FACTORS, cache_flags, classify_unknown, same_numerics


def test_cache_factors_change_one_flag_at_a_time():
    flags = {key: cache_flags(*setting) for key, setting in FACTORS.items()}
    assert "--cache-ram" not in flags["default"] and "--ctx-checkpoints" not in flags["default"]
    assert "--cache-ram" in flags["cache_off"] and "--ctx-checkpoints" not in flags["cache_off"]
    assert "--cache-ram" not in flags["checkpoints_off"] and "--ctx-checkpoints" in flags["checkpoints_off"]
    assert "--cache-ram" in flags["both_off"] and "--ctx-checkpoints" in flags["both_off"]


def sample(token, logprob):
    return {"prefix": [1, 2], "tokens": [token], "logprobs": [[(token, logprob)]]}


def test_same_top_token_alone_does_not_establish_same_route():
    assert not same_numerics(sample(12, -0.3), sample(12, -0.4))


@pytest.mark.parametrize(("unknown", "expected"), [(12, "SCALE_ZERO"), (13, "SCALE_ONE"), (14, "OTHER")])
def test_unknown_route_is_compared_to_both_explicit_scales(unknown, expected):
    assert classify_unknown([sample(unknown, -0.3)], [sample(12, -0.3)], [sample(13, -0.3)]) == expected


def test_indistinguishable_scales_are_not_classified_as_scale_zero():
    probes = [sample(12, -0.3)]
    assert classify_unknown(probes, probes, probes) == "INDETERMINATE"
