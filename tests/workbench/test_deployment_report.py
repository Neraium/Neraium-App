"""Deployment report verification accepts current evidence and rejects provenance loss."""
from copy import deepcopy
from html import escape

import pytest

from backend.workbench.report import render
from deploy.production.verify import verify_report
from test_report import fixture, governed_finding


@pytest.mark.parametrize('governed', [False, True])
def test_verifier_accepts_current_paired_report_with_or_without_governed_findings(governed):
    run = fixture()
    if governed:
        run['response']['result'] = {'analysis_result': {'relationship_findings': [governed_finding()]}}
    # Parsed facts must handle escaped filenames and keep each role's own hash.
    run['reference_source']['filename'] = 'baseline & <reference>.csv'
    run['source']['filename'] = 'comparison & <current>.csv'
    before = deepcopy(run)
    report = render(run, None)
    assert 'Reference period/data' not in report and 'Comparison period/data' not in report
    verify_report(report, run)
    assert run == before


@pytest.mark.parametrize('role', ['reference', 'comparison'])
@pytest.mark.parametrize('damage', ['period', 'filename', 'hash', 'missing_source', 'swapped_period', 'swapped_hash'])
def test_verifier_rejects_missing_altered_or_swapped_paired_evidence(role, damage):
    run = fixture()
    run['response']['result'] = {'analysis_result': {'relationship_findings': [governed_finding()]}}
    report = render(run, None)
    source = run['reference_source' if role == 'reference' else 'source']
    other = run['source' if role == 'reference' else 'reference_source']
    rows = run['input']['reference']['rows'] if role == 'reference' else run['input']['rows']
    other_rows = run['input']['rows'] if role == 'reference' else run['input']['reference']['rows']
    if damage in ('period', 'swapped_period'):
        value = f"{rows[0]['timestamp']} to {rows[-1]['timestamp']}"
        changed = 'Not supplied' if damage == 'period' else f"{other_rows[0]['timestamp']} to {other_rows[-1]['timestamp']}"
    elif damage == 'filename':
        value, changed = source['filename'], 'wrong.csv'
    elif damage in ('hash', 'swapped_hash'):
        value, changed = source['sha256'], '0' * 64 if damage == 'hash' else other['sha256']
    else:
        label = 'Baseline source' if role == 'reference' else 'Comparison source'
        value, changed = f'<dt>{label}</dt><dd>{source["filename"]}</dd>', ''
    assert escape(value) in report if damage != 'missing_source' else value in report
    report = report.replace(escape(value) if damage != 'missing_source' else value, escape(changed))
    # Old headings and correct data in unrelated prose cannot mask missing facts.
    report += f'<p>Reference period/data Comparison period/data {escape(value)}</p>'
    with pytest.raises(AssertionError):
        verify_report(report, run)
