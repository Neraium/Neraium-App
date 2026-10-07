"""Report presentation tests. Fixtures are transport evidence, not engine validation."""
from copy import deepcopy

import pytest

from backend.workbench.report import project, render
from backend.workbench.authority import SUPPORTED_COMMIT


def fixture():
    relationships = [dict(display_relationship=f'Flow / Power {i}', evidence_refs=[{'column': 'flow'}, {'column': f'power{i}'}],
                          baseline_correlation=-0.989991, recent_correlation=-0.672799,
                          signed_correlation_delta=0.317192, change_type='weakened', confidence_level='high',
                          baseline_sample_size=8640, recent_sample_size=8640) for i in range(4)]
    findings = [dict(source_tags=['flow', f'power{i}'], confidence='limited', persistence={'persistent': False},
                     persistence_duration='Compared 8640 baseline samples with 8640 recent samples.',
                     certainty_limit='Persistence is not established.',
                     recommended_action='Inspect the equipment.',
                     measurable_consequence={'status': 'not_quantifiable', 'cumulative_amount': 999, 'cumulative_unit': 'kWh'}) for i in range(4)]
    return dict(id='run', evaluation=dict(id='eval', system='WWTP', customer='Test', facility='Plant'),
                input=dict(mode='paired', rows=[{'timestamp': '2026-05-01 00:00:00'}, {'timestamp': '2026-07-29 23:45:00'}],
                           reference={'rows': [{'timestamp': '2026-01-01 00:00:00'}, {'timestamp': '2026-03-31 23:45:00'}]}),
                source={'filename': 'comparison.csv', 'sha256': 'b'*64}, reference_source={'filename': 'baseline.csv', 'sha256': 'a'*64},
                input_sha256='c'*64, result_sha256='d'*64,
                mapping={'signals': [{'column': 'energy_total_kwh', 'include': False}]},
                response={'identity': {'commit': SUPPORTED_COMMIT, 'callable': 'internal.module.path'}, 'result': {
                    'findings': findings, 'relationship_analysis': {'top_relationship_changes': relationships},
                    'supplied_reference': {'timestamp_mode': 'naive_historical_source_clock', 'source_timezone': {'status': 'timezone_not_supplied'}},
                    'processing_trace': {'debug': 'SECRET DEBUG'}, 'analysis_result': {'conditions': []}}})


def test_customer_projection_is_bounded_exact_and_immutable():
    run = fixture(); original = deepcopy(run)
    view = project(run['response']['result'])
    html = render(run, {'reviewer': 'Internal operator', 'created_at': 'review-time', 'evidence_reviewed': True})
    main, appendix = html.split('<section class="appendix">')
    assert len(view['relationships']) == 3
    assert view['relationships'][0]['baseline'] == -0.989991
    assert view['relationships'][0]['comparison'] == -0.672799
    assert view['relationships'][0]['delta'] == 0.317192
    assert 'persistent relationship change is not established' in main
    assert 'Change-detection evidence is high; overall finding confidence is limited.' in main
    assert 'Onset is not established' in main
    assert 'Not quantifiable from the available evidence.' in main
    assert 'Observations (baseline / comparison)' in main and 'Persistence duration' not in main
    for hidden in ('energy_total_kwh', 'internal.module.path', 'SECRET DEBUG', 'Inspect the equipment', '/analysis_result', '/processing_trace', '<pre>', 'Internal operator', '—', 'Flow / Power 3', '999 kWh'):
        assert hidden not in main
    assert 'Internal operator' not in appendix
    assert 'energy_total_kwh' in appendix and SUPPORTED_COMMIT in appendix
    assert 'naive_historical_source_clock' in appendix and 'timezone_not_supplied' in appendix
    assert 'a'*64 in appendix and 'b'*64 in appendix
    assert 'Scope and evidence review recorded at review-time' in appendix
    assert run == original


def test_persistence_and_onset_are_scoped_not_inferred_from_window():
    run = fixture(); result = run['response']['result']
    f = result['findings'][0]
    f.update(persistence={'persistent': True}, persistence_duration='Supported for 7200 seconds.', change_onset='2026-06-01 00:00:00')
    result['temporal_analysis'] = {'lead_time_estimate': {'timestamp': '2026-05-31 23:00:00', 'confidence': 'low'}}
    result['persistence_analysis'] = {'adaptive_persistence': {'details': [
        {'column': 'power0', 'longest_continuous_support_seconds': 7200},
        {'column': 'unrelated', 'longest_continuous_support_seconds': 99999}]}}
    html = render(run, None)
    assert 'Persistent relationship change was observed' in html
    assert 'Persistence duration' in html and 'Supported for 7200 seconds.' in html
    assert 'Finding onset' in html and '2026-06-01 00:00:00' in html
    assert 'Evaluation onset estimate' in html and '2026-05-31 23:00:00' in html and 'heuristic' in html
    assert 'longest continuous signal support 7200 seconds' in html
    assert '99999' not in html
    assert 'No confirmed scope and evidence review' in html


@pytest.mark.parametrize('amount,unit,status,shown', [(-5, 'gal', 'quantified', True), (0, 'kWh', 'quantified', True),
    (None, 'kWh', 'quantified', False), (5, '', 'quantified', False), (5, 'dimensionless', 'quantified', False),
    (5, 'kWh', 'not_quantifiable', False), (float('nan'), 'kWh', 'quantified', False)])
def test_quantification_requires_authority_status_finite_amount_and_units(amount, unit, status, shown):
    run = fixture()
    c = dict(status=status, cumulative_amount=amount, cumulative_unit=unit, support_level='high', statement='Measured excess volume.', limitations=['Coverage is incomplete.'])
    run['response']['result']['analysis_result']['conditions'] = [{'measurable_consequence': c}]
    html = render(run, None)
    assert ('Measured amount' in html) is shown
    assert ('Not quantifiable from the available evidence.' in html) is not shown
    if shown:
        assert f'{amount} {unit}' in html and 'Coverage is incomplete.' in html


def test_empty_evidence_and_unconfirmed_review_are_truthful_and_escaped():
    run = fixture(); run['response']['result'] = {}; run['evaluation']['system'] = '<script>bad()</script>'
    html = render(run, {'reviewer': 'Someone', 'created_at': 'now', 'evidence_reviewed': False})
    assert 'Insufficient evidence remains a valid outcome.' in html
    assert 'This does not establish stable behavior.' in html
    assert '&lt;script&gt;bad()&lt;/script&gt;' in html and '<script>' not in html
    assert 'No confirmed scope and evidence review' in html


def test_grouped_findings_match_signal_pairs_not_reused_ids():
    result = fixture()['response']['result']
    result['findings'] = [{'id': 'unrelated', 'source_tags': ['flow', 'power0', 'power1'], 'confidence': 'limited',
                           'persistence': {'persistent': False}, 'contributing_relationships': [
                               {'columns': ['flow', 'power0']}, {'columns': ['flow', 'power1']}]}]
    assert [r['finding_confidence'] for r in project(result)['relationships']] == ['limited', 'limited', 'not supplied']


def governed_finding():
    return dict(id='scoped-finding', title='Scoped flow / power change', source_tags=['flow', 'power0'],
                relationship_evidence_ref='assessment-1', relationship_source_ref='source-1',
                relationship_assessment_binding='binding-1',
                classification={'type': 'unexplained_systemic_change', 'label': 'Unexplained systemic change', 'confidence': 'high'},
                confidence='high', what_changed='The authority observed a scoped relationship shift.',
                persistence={'persistent': True, 'scope': 'relationship', 'summary': 'The exact assessment establishes persistence.'},
                relationship_evidence={'baseline_sample_size': 12000, 'recent_sample_size': 12000},
                source_time_ranges=[{'baseline_start': '2026-10-05', 'current_start': '2026-10-10'}],
                certainty_limit='This does not diagnose cause — or predict a failure.')


def test_governed_finding_reaches_report_even_without_top_relationships():
    import json
    from html import unescape
    run = fixture(); finding = governed_finding()
    run['response']['result'] = {'analysis_result': {'relationship_findings': [finding]}}
    before = deepcopy(run)
    view = project(run['response']['result'])
    assert view['governed_findings'][0] is finding
    html = render(run, None)
    assert 'Unexplained systemic change' in html
    assert '<dt>Relationship persistence</dt><dd>Confirmed</dd>' in html
    assert finding['persistence']['summary'] in html
    assert finding['certainty_limit'] in html
    assert 'Persistent relationship change was observed' in html
    assert 'does not establish a persistent relationship change' not in html
    assert json.loads(unescape(html.split('<pre>')[1].split('</pre>')[0])) == finding
    assert run == before


def test_governed_duplicate_uses_exact_identity_and_preserves_legacy_scope():
    run = fixture(); result = run['response']['result']; finding = governed_finding()
    result['analysis_result']['relationship_findings'] = [finding, deepcopy(finding)]
    result['findings'][0] = {**finding, 'confidence': 'limited'}
    result['relationship_analysis']['top_relationship_changes'][0].update(
        relationship_evidence_ref='assessment-1', relationship_source_ref='source-1', relationship_assessment_binding='binding-1')
    view = project(result)
    assert view['relationships'][0]['persistent'] is True
    assert view['relationships'][0]['finding_confidence'] == 'high'
    html = render(run, None)
    main = html.split('<section class="appendix">')[0]
    assert main.count('<h3>Scoped flow / power change</h3>') == 1
    assert '<h3>Flow / Power 0</h3>' not in main
    assert '<h3>Flow / Power 1</h3>' in main
    other = {**finding, 'id': 'another-scope', 'relationship_assessment_binding': 'binding-2'}
    result['analysis_result']['relationship_findings'].append(other)
    assert len(project(result)['governed_findings']) == 2


def test_scoped_persistence_is_never_borrowed_by_signal_pair_or_other_binding():
    result = fixture()['response']['result']; finding = governed_finding()
    result['analysis_result']['relationship_findings'] = [finding]
    result['relationship_analysis']['top_relationship_changes'][0].update(
        relationship_evidence_ref='assessment-1', relationship_assessment_binding='different-binding')
    assert project(result)['relationships'][0]['persistent'] is False


@pytest.mark.parametrize('persistent', [False, None])
def test_governed_insufficient_evidence_never_promotes_persistence(persistent):
    run = fixture(); finding = governed_finding()
    finding.update(classification={'type': 'insufficient_evidence', 'label': 'Insufficient evidence'},
                   persistence={'persistent': persistent, 'summary': 'Relationship persistence is not established.'})
    run['response']['result'] = {'analysis_result': {'relationship_findings': [finding]}}
    html = render(run, None)
    assert 'Insufficient evidence' in html
    assert 'Confirmed' not in html
    assert 'Persistent relationship change was observed' not in html
    assert 'does not establish a persistent relationship change' in html


def test_empty_governed_findings_leave_legacy_projection_unchanged():
    run = fixture(); expected = render(run, None)
    run['response']['result']['analysis_result']['relationship_findings'] = []
    assert render(run, None) == expected


def test_stored_wwtp_report_read_only():
    """Optional local representative check; never executes authority or records a review."""
    import hashlib
    import json
    import os
    from pathlib import Path
    import sqlite3

    db_path = os.getenv('NERAIUM_REPORT_REPRESENTATIVE_DB')
    run_id = os.getenv('NERAIUM_REPORT_REPRESENTATIVE_RUN')
    if not db_path or not run_id:
        pytest.skip('Set representative database and run for read-only WWTP verification')
    before = hashlib.sha256(Path(db_path).read_bytes()).hexdigest()
    with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as db:
        raw = db.execute('SELECT document FROM runs WHERE id=?', (run_id,)).fetchone()[0]
        run = __import__('json').loads(raw)
        review_row = db.execute('SELECT document FROM reviews WHERE run_id=? ORDER BY rowid DESC LIMIT 1', (run_id,)).fetchone()
        review = json.loads(review_row[0]) if review_row else None
        snapshot = deepcopy(run)
        html = render(run, review)
        result = run['response']['result']
        view = project(result)
        assert run['response']['identity']['commit'] == SUPPORTED_COMMIT
        assert len(run['input']['rows']) == len(run['input']['reference']['rows']) == 8640
        for catalog in run['response']['catalog'].values():
            assert sum(s['analysis_role'] == 'primary_signal' for s in catalog.values()) == 16
            assert sum(s['is_context_driver'] for s in catalog.values()) == 1
        assert [s['column'] for s in run['mapping']['signals'] if not s['include']] == ['energy_total_kwh']
        assert result['supplied_reference']['timestamp_mode'] == 'naive_historical_source_clock'
        assert result['supplied_reference']['source_timezone'] == {'status': 'timezone_not_supplied', 'value': None}
        for source in (run['source'], run['reference_source']):
            source_bytes = db.execute('SELECT raw FROM sources WHERE id=?', (source['id'],)).fetchone()[0]
            assert hashlib.sha256(source_bytes).hexdigest() == source['sha256']
        for value, key in [(run['input'], 'input_sha256'), (result, 'result_sha256')]:
            encoded = json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()
            assert hashlib.sha256(encoded).hexdigest() == run[key]
        for shown, stored in zip(view['relationships'], result['relationship_analysis']['top_relationship_changes']):
            for projected, field in [('baseline', 'baseline_correlation'), ('comparison', 'recent_correlation'), ('delta', 'signed_correlation_delta')]:
                assert shown[projected] == stored[field]
                assert str(stored[field]) in html
        assert 'Not quantifiable from the available evidence.' in html
        assert run == snapshot
        assert db.execute('SELECT document FROM runs WHERE id=?', (run_id,)).fetchone()[0] == raw
        if review_row:
            assert db.execute('SELECT document FROM reviews WHERE id=?', (review['id'],)).fetchone()[0] == review_row[0]
    assert hashlib.sha256(Path(db_path).read_bytes()).hexdigest() == before
