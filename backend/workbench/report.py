"""Evidence projection and escaped, printable report; no authored diagnosis."""
from html import escape
import json


def evidence_sections(result):
    drift = result.get("signal_drift") or {}
    relationships = result.get("relationship_analysis") or {}
    return {
        **({"Governed analysis · /analysis_result": result["analysis_result"],
            "Supplied reference provenance and limitations · /supplied_reference": result["supplied_reference"],
            "Temporal evidence and onset · /temporal_analysis": result.get("temporal_analysis", {}),
            "Authority processing trace · /processing_trace": result.get("processing_trace", {})}
           if "supplied_reference" in result else {}),
        "Material findings · /findings": result.get("findings", []),
        "Engineering observations · /evidence_fusion/observations": (result.get("evidence_fusion") or {}).get("observations", []),
        "Relationship changes · /relationship_analysis/top_relationship_changes": relationships.get("top_relationship_changes", []),
        "Change timing and persistence · /persistence_analysis": result.get("persistence_analysis", {}),
        "Baseline/comparison · /signal_drift": {k: drift[k] for k in (
            "overall_assessment", "baseline_window_rows", "recent_window_rows", "adaptive_baseline", "warnings"
        ) if k in drift},
        "Uncertainty · /uncertainty": result.get("uncertainty", {}),
    }


def relationship_rows(result):
    """Select transport fields only; all values and classifications are engine-owned."""
    return [{k: item.get(k) for k in ("display_relationship", "change_type", "baseline_correlation",
            "recent_correlation", "time_window", "confidence_level", "evidence_refs")}
            for item in (result.get("relationship_analysis") or {}).get("top_relationship_changes", [])]


def render(run: dict, review: dict) -> str:
    evaluation = run["evaluation"]
    payload = run["input"]
    result = run["response"]["result"]
    esc = lambda value: escape(str(value), quote=True)
    pretty = lambda value: esc(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
    signals = "".join(f"<tr><td>{esc(s['column'])}</td><td>{esc(s['meaning'])}</td><td>{esc(s['unit'] or 'Unknown / not supplied')}</td></tr>" for s in payload["signals"])
    paired = payload.get("mode") == "paired"
    reference_scope = ""
    if paired:
        ref = payload["reference"]
        reference_scope = f"<h2>Reference period/data</h2><p>{esc(run['reference_source']['filename'])} · {len(ref['rows'])} analyzed rows<br>{esc(ref['rows'][0]['timestamp'])} through {esc(ref['rows'][-1]['timestamp'])}<br>SHA-256 {esc(run['reference_source']['sha256'])}</p><h2>Comparison period/data</h2>"
    window_policy = ("The full supplied reference and comparison are passed separately to authoritative SII. Governed findings, timing, persistence and limitations are retained as supplied. Neither role establishes equipment health."
                     if paired else "Baseline/comparison windows are selected by the authoritative engine within the approved historical interval.")
    sections = evidence_sections(result)
    relationship_table = "".join(
        "<tr>" + "".join(f"<td>{esc(item.get(key) if item.get(key) is not None else 'Not supplied')}</td>"
                         for key in ("display_relationship", "change_type", "baseline_correlation", "recent_correlation", "confidence_level", "time_window")) + "</tr>"
        for item in relationship_rows(result)
    )
    # Preserve supplied evidence and classifications even when sections are long.
    # In particular, timing and uncertainty fields must not disappear in print.
    excerpts = []
    for label, value in sections.items():
        text = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) if value else
                "No evidence entries supplied by the authoritative engine. This is not a claim of stable behavior.")
        excerpts.append(f"<h2>{esc(label)}</h2><pre>{esc(text)}</pre>")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Neraium historical evaluation — {esc(evaluation['customer'])}</title>
<style>body{{font:15px/1.5 system-ui;max-width:900px;margin:40px auto;padding:20px;color:#17242b}}h1{{font-size:28px}}h2{{font-size:18px;margin-top:28px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 monospace}}@media print{{body{{margin:0}}h2{{break-after:avoid}}}}</style>
<h1>Neraium historical evaluation</h1>
<p><b>{esc(evaluation['customer'])} · {esc(evaluation['facility'])} · {esc(evaluation['system'])}</b></p>
<p>{esc(evaluation['scope'])}</p>
<p>This evaluation is read-only and based on supplied historical data. Correlation does not establish causation.
No failure probability, remaining useful life, equipment control, or autonomous recommendation is provided.</p>
<h2>Dataset and scope</h2>{reference_scope}<p>{esc(run['source']['filename'])} · {len(payload['rows'])} analyzed rows<br>
{esc(payload['rows'][0]['timestamp'])} through {esc(payload['rows'][-1]['timestamp'])}</p>
<p>System context supplied by analyst: {esc(payload['context'])}</p>
<p>{esc(window_policy)}
No externally established healthy baseline is assumed. Cross-run behavioral memory and engineering priors are not configured.</p>
<table><tr><th>Source signal</th><th>Confirmed meaning</th><th>Supplied unit</th></tr>{signals}</table>
<h2>Quality, exclusions and transformations</h2><pre>{pretty({'warnings': run['validation']['warnings'], 'signals': [s for s in run['validation']['signals'] if s['missing_count'] or s['invalid_count'] or s['constant']]})}</pre>
<pre>{pretty({'excluded_signals': [s for s in run['mapping']['signals'] if not s['include']], 'transformations': payload['transformations'], 'reference_validation': run.get('reference_validation'), 'pair_confirmation': run['mapping'].get('pair_confirmed')})}</pre>
<h2>Analysis outcome</h2><p>Authoritative execution status: <b>{esc(result['status'])}</b>.
Completion is not a finding. Stable and insufficient-evidence outcomes remain valid.</p>
<h2>Observed relationship changes</h2>
<p>Evidence: /relationship_analysis/top_relationship_changes in the accompanying JSON package.</p>
<table><tr><th>Relationship</th><th>Change</th><th>Baseline correlation</th><th>Recent correlation</th><th>Evidence confidence</th><th>Window</th></tr>{relationship_table}</table>
<p>{'No relationship-change entries were supplied.' if not relationship_table else 'These are measured associations, not causal diagnoses.'}
An exact onset time is not inferred from the comparison window. Detailed elapsed-time support, when available, is retained in /persistence_analysis.</p>
{''.join(excerpts)}
<h2>Measurable consequence</h2><p>Any authority-supplied consequence evidence is retained in the governed analysis and full evidence package.
No cost, energy, failure, or causal consequence is inferred from relationship change.</p>
<h2>Review and provenance</h2><p>Reviewed by {esc(review['reviewer'])} at {esc(review['created_at'])}.
Review confirms scope and evidence inspection; it does not certify a diagnosis.</p>
<pre>{pretty({'run_id': run['id'], 'source_sha256': run['source']['sha256'], 'reference_source': run.get('reference_source'), 'input_sha256': run['input_sha256'], 'result_sha256': run['result_sha256'], 'authority': run['response']['identity']})}</pre>
<p>Deliver with the run's JSON evidence package for complete evidence, module limitations, input rows and runtime versions.</p></html>"""
