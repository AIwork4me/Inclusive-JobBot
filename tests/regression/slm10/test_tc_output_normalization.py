import pytest

from benchmarks.slm10.tc_output_normalization import extract_object


def test_normalization_preserves_exact_value_text_and_requires_a_trusted_terminal():
    raw = '```json\n{"amount":12.00,"uncertain":true,"extra":["kept"]}\n```'
    assert extract_object(raw, terminal_allowed=True) == '{"amount":12.00,"uncertain":true,"extra":["kept"]}'
    assert extract_object(raw, terminal_allowed=False) is None


@pytest.mark.parametrize("raw", [
    'prefix\n```json\n{"value":1}\n```',
    '```json\n{"value":1,"value":2}\n```',
    '```json\n[{"value":1}]\n```',
    '{"value":1}',
    "\ud800",
    '```json\n{"value":1}\n```\npostscript',
])
def test_normalization_refuses_ambiguous_and_already_native_formats(raw):
    assert extract_object(raw, terminal_allowed=True) is None
