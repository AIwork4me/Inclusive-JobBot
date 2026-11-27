import pytest

from benchmarks.slm10.tc_priority_milestone import metric_cell


def test_metric_denominators_keep_applicability_and_missing_evidence_distinct():
    cell = metric_cell([(True, 'PASS'), (True, 'FAIL'), (True, 'BLOCKED'),
                        (True, 'NOT_RUN'), (False, 'BLOCKED')])
    assert {key: cell[key] for key in ('full', 'applicable', 'observed', 'PASS', 'FAIL',
                                        'BLOCKED', 'NOT_RUN', 'N/A')} == {
        'full': 5, 'applicable': 4, 'observed': 2, 'PASS': 1, 'FAIL': 1,
        'BLOCKED': 1, 'NOT_RUN': 1, 'N/A': 1,
    }
    assert cell['rate'] == 0.5
    assert cell['wilson_95'][0] < 0.5 < cell['wilson_95'][1]
    assert metric_cell([(True, 'BLOCKED')])['rate'] is None
    with pytest.raises(ValueError):
        metric_cell([(True, 'INDETERMINATE')])
