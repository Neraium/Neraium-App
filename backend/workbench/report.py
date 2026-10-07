"""Evidence projection and escaped, printable report; no authored diagnosis."""
from html import escape
import json
import math
import re


def distinct_findings(findings):
    """Select existing objects by authority identity; never merge by signal names."""
    selected = []
    identities = set()
    for finding in findings:
        identity = finding.get('id') or (
            (finding['relationship_evidence_ref'], finding.get('relationship_source_ref'),
             finding.get('relationship_assessment_binding')) if finding.get('relationship_evidence_ref') else None)
        if (identity is not None and identity in identities) or (identity is None and finding in selected):
            continue
        selected.append(finding)
        if identity is not None:
            identities.add(identity)
    return selected


def evidence_sections(result):
    drift = result.get("signal_drift") or {}
    relationships = result.get("relationship_analysis") or {}
    return {
        **({"Governed relationship findings · /analysis_result/relationship_findings": result['analysis_result']['relationship_findings']}
           if 'relationship_findings' in (result.get('analysis_result') or {}) else {}),
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



MAX_RELATIONSHIPS = 3


def scalar(value):
    return value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def prose(value):
    """Only readable observational prose, never arbitrary serialized evidence."""
    value = scalar(value)
    if not isinstance(value, str) or not value.strip():
        return None
    if re.search(r"[{}]|/(?:analysis_result|temporal_analysis|processing_trace)|\b(?:cause|diagnos\w*|recommend\w*|inspect|corrective|predict\w*|instrumentation|internal operator|adapter|schema|module|runner|authenticated_scope)\b", value, re.I):
        return None
    return value.replace("—", "; ")


def confidence(value):
    return value if value in ("high", "moderate", "medium", "low", "limited", "unknown", "strong", "insufficient") else "not supplied"


def columns(item):
    return set(item.get("columns") or [e.get("column") for e in item.get("evidence_refs", []) if isinstance(e, dict)]) - {None}


def linked_finding(relationship, findings):
    reference = relationship.get('relationship_evidence_ref')
    if reference:
        exact = next((f for f in findings if f.get('relationship_evidence_ref') == reference
                      and all(not relationship.get(k) or f.get(k) == relationship[k]
                              for k in ('relationship_source_ref', 'relationship_assessment_binding'))), None)
        if exact is not None:
            return exact
    keys = columns(relationship)
    if not keys:
        return {}
    # Group IDs are not relationship IDs. Match exact contributing signal pairs.
    return next((f for f in findings if not f.get('relationship_evidence_ref') and (
                 any(columns(c) == keys for c in f.get("contributing_relationships", []))
                 or set(f.get("source_tags", [])) == keys)), {})


def project(result):
    """Presentation only. Retain authority order, values and scope without mutating evidence."""
    analysis = result.get("analysis_result") or {}
    governed = distinct_findings(analysis.get('relationship_findings') or [])
    findings = distinct_findings([*governed, *(result.get("findings") or analysis.get("insights") or [])])
    selected = []
    seen = set()
    for relationship in (result.get("relationship_analysis") or {}).get("top_relationship_changes", []):
        title = scalar(relationship.get("display_relationship")) or scalar(relationship.get("relationship"))
        if not title or title in seen:
            continue
        seen.add(title)
        finding = linked_finding(relationship, findings)
        persistence = finding.get("persistence") or {}
        selected.append({
            "title": title.replace(" <-> ", " / ").replace("<->", " / ").replace("—", "; "),
            "change": {"weakened": "The relationship weakened.", "strengthened": "The relationship strengthened.",
                       "reversed": "The relationship reversed direction.", "sign_flip": "The relationship reversed direction."}.get(relationship.get("change_type"), "A relationship change was observed."),
            "baseline": relationship.get("baseline_correlation"), "comparison": relationship.get("recent_correlation"),
            "delta": relationship.get("signed_correlation_delta"),
            "detection": confidence(relationship.get("confidence_level")),
            "finding_confidence": confidence(finding.get("confidence")),
            "persistent": persistence.get("persistent"),
            "governed": finding in governed,
            "duration": prose(finding.get("persistence_duration")),
            "onset": scalar(finding.get("change_onset")),
            "elapsed": [(d.get("column"), d.get("longest_continuous_support_seconds"))
                for d in (result.get("persistence_analysis") or {}).get("adaptive_persistence", {}).get("details", [])
                if d.get("column") in columns(relationship) and number(d.get("longest_continuous_support_seconds"))],
            "baseline_samples": relationship.get("baseline_sample_size"),
            "comparison_samples": relationship.get("recent_sample_size"),
            "window": relationship.get("time_window") or {},
            "limits": list(dict.fromkeys(filter(None, [prose(finding.get("certainty_limit")),
                *[prose(v) for v in (relationship.get("data_confidence") or {}).get("reasons", [])],
                *[prose(v) for v in (relationship.get("operating_mode") or {}).get("reasons", []) if "matched across" not in v]]))),
        })
        if len(selected) == MAX_RELATIONSHIPS:
            break
    all_persistence = [(f.get("persistence") or {}).get("persistent") for f in findings
                       if f in governed or f.get("contributing_relationships") or len(f.get("source_tags", [])) >= 2]
    if True in all_persistence:
        summary = "Persistent relationship change was observed in the supplied evidence."
    elif selected:
        summary = "Relationship changes were observed, but persistent relationship change is not established by the available evidence."
    else:
        summary = "The available evidence does not establish a persistent relationship change."
    if selected:
        levels = list(dict.fromkeys(item["detection"] for item in selected))
        finding_levels = list(dict.fromkeys(item["finding_confidence"] for item in selected))
        summary += f" Change-detection evidence is {' / '.join(levels)}; overall finding confidence is {' / '.join(finding_levels)}."
    else:
        summary += " Insufficient evidence remains a valid outcome."
    consequences = []
    seen = set()
    for f in [*findings, *analysis.get("conditions", [])]:
        c = f.get("measurable_consequence") or {}
        unit = scalar(c.get("cumulative_unit"))
        if c.get("status") != "quantified" or not number(c.get("cumulative_amount")) or not isinstance(unit, str) or not unit or unit.lower() in ("unknown", "dimensionless", "not supplied"):
            continue
        # The same consequence may be carried by both a finding and a condition.
        key = (c.get("analysis_run_id"), c.get("finding_id") or f.get("id"), c["cumulative_amount"], unit)
        if key in seen:
            continue
        seen.add(key)
        consequences.append({"amount": c["cumulative_amount"], "unit": unit,
            "statement": prose(c.get("statement")), "support": confidence(c.get("support_level")),
            "limits": list(filter(None, (prose(v) for v in c.get("limitations", []))))})
    if consequences:
        summary += " A measurable consequence is quantified in the supplied evidence."
    uncertainty = result.get("uncertainty") or {}
    supplied = result.get("supplied_reference") or {}
    limits = list(filter(None, [*[prose(v) for v in (uncertainty.get("data_confidence") or {}).get("reasons", [])],
        *[prose(v) for v in uncertainty.get("limitations", []) if not any(word in v for word in ("Units ", "Persistent behavioral", "Multiscale", "Covariance", "Elapsed persistence", "Temporal lead-time", "timezone_not_supplied"))]]))
    if supplied.get("source_timezone", {}).get("status") == "timezone_not_supplied":
        limits.append("Times use the supplied source clock. Timezone, UTC offset and daylight-saving interpretation are not established.")
    if any(item["elapsed"] for item in selected) and any("terminal-sample" in v for v in supplied.get("limitations", [])):
        limits.append("Signal support durations include one median sampling interval for the final sample.")
    if supplied.get("signal_units"):
        limits.append("Physical units are supplied with the data and have not been independently verified.")
    return {"summary": summary, "relationships": selected, "governed_findings": governed, "consequences": consequences,
            "limits": list(dict.fromkeys([*[v for item in selected for v in item["limits"]], *limits])), "onset": scalar(analysis.get("change_onset")),
            "temporal": (result.get("temporal_analysis") or {}).get("lead_time_estimate") or {}}


def render(run: dict, review: dict) -> str:
    evaluation, payload = run["evaluation"], run["input"]
    result = run["response"]["result"]
    view = project(result)
    esc = lambda value: escape(str(value).replace("—", "; "), quote=True)
    def paragraph(value, verbatim=False):
        return f"<p>{escape(str(value), quote=True) if verbatim else esc(value)}</p>" if value is not None and value != "" else ""
    def facts(values, verbatim=False):
        return '<dl>' + ''.join(f'<div><dt>{esc(label)}</dt><dd>{escape(str(value), quote=True) if verbatim else esc(value)}</dd></div>'
            for label, value in values if value is not None and value != '') + '</dl>'
    def period(rows):
        return f"{rows[0]['timestamp']} to {rows[-1]['timestamp']}" if rows else "Not supplied"
    def section(title, content, cls=""):
        return f'<section class="{cls}"><h2>{title}</h2>{content}</section>'
    name = evaluation.get("label") or evaluation.get("system") or evaluation.get("customer") or "Supplied historical system"
    periods = []
    if payload.get("mode") == "paired":
        periods.append(("Baseline / reference", period(payload.get("reference", {}).get("rows", []))))
        periods.append(("Comparison", period(payload.get("rows", []))))
    else:
        periods.append(("Evaluation period", period(payload.get("rows", []))))
    findings_html = ''
    for finding in view['governed_findings']:
        classification = finding.get('classification') or {}
        persistence = finding.get('persistence') or {}
        persistent = persistence.get('persistent')
        findings_html += '<article><h3>' + escape(str(finding.get('title') or 'Relationship finding'), quote=True) + '</h3>'
        findings_html += facts([('Authority classification', classification.get('label') or classification.get('type')),
            ('Finding confidence', finding.get('confidence')),
            ('Relationship persistence', 'Confirmed' if persistent is True else 'Not established' if persistent is False else None)], verbatim=True)
        # These are governed statements, rendered verbatim with HTML escaping.
        for statement in dict.fromkeys(filter(None, [finding.get('what_changed'), finding.get('interpretation'),
                persistence.get('summary'), *finding.get('supporting_evidence', []), finding.get('certainty_limit')])):
            findings_html += paragraph(statement, verbatim=True)
        findings_html += '</article>'
    for item in view["relationships"]:
        if item['governed']:
            continue  # The exact finding has already been shown above.
        state = "Confirmed" if item["persistent"] is True else "Not established"
        # A sample-window description is not a duration of persistent change.
        duration_label = "Persistence duration" if item["persistent"] is True else "Observation coverage"
        duration = item['duration'] if not (item['duration'] or '').startswith('Compared ') else None
        if item['persistent'] is True and not duration:
            duration = 'Elapsed duration not supplied.'
        findings_html += '<article><h3>' + esc(item['title']) + '</h3>' + paragraph(item['change']) + facts([
            ("Change-detection evidence", item['detection']), ("Finding confidence", item['finding_confidence']),
            ("Persistence", state), (duration_label, duration), ("Finding onset", item['onset'])])
        if number(item['baseline']) and number(item['comparison']):
            findings_html += paragraph(f"Correlation: {item['baseline']} to {item['comparison']}.")
        for column, seconds in item['elapsed']:
            findings_html += paragraph(f"{column}: longest continuous signal support {seconds} seconds. Signal support does not establish persistence of the whole relationship.")
        findings_html += '</article>'
    if not findings_html:
        findings_html = paragraph("No supported relationship-change entries were supplied. This does not establish stable behavior.")
    temporal = view['temporal']
    timing = facts([("Evaluation change onset", view['onset']), ("Evaluation onset estimate", scalar(temporal.get('timestamp'))),
                    ("Estimate confidence", confidence(temporal.get('confidence')) if temporal.get('timestamp') else None)])
    if not view['onset'] and not temporal.get('timestamp'):
        timing += paragraph("Onset is not established by the available evidence.")
    if temporal.get('timestamp'):
        timing += paragraph("The evaluation-level onset estimate is heuristic. It is not a verified event time or an onset for each relationship.")
    findings_html += '<div class="timing">' + timing + '</div>'
    consequence_html = ''
    for c in view['consequences']:
        consequence_html += '<article>' + paragraph(c['statement']) + facts([("Measured amount", f"{c['amount']} {c['unit']}"), ("Evidence support", c['support'])]) + ''.join(paragraph(v) for v in c['limits']) + '</article>'
    consequence_html = consequence_html or paragraph("Not quantifiable from the available evidence.")
    evidence_html = ''
    headers = ['Relationship', 'Baseline correlation', 'Comparison correlation', 'Signed change', 'Observations (baseline / comparison)']
    for item in view['relationships']:
        samples = f"{item['baseline_samples'] if item['baseline_samples'] is not None else 'Not supplied'} / {item['comparison_samples'] if item['comparison_samples'] is not None else 'Not supplied'}"
        values = [item['title'], item['baseline'], item['comparison'], item['delta'], samples]
        evidence_html += '<tr>' + ''.join(f'<td data-label="{esc(label)}">{esc(value if value is not None else "Not supplied")}</td>' for label, value in zip(headers, values)) + '</tr>'
    if evidence_html:
        evidence_html = paragraph('Strongest supplied relationship changes, in evidence order. Correlation describes association, not physical-unit change.') + '<table><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in headers) + '</tr></thead><tbody>' + evidence_html + '</tbody></table>'
        # Show differing evidence bounds without repeating the same periods per row.
        windows = []
        for item in view['relationships']:
            window = item['window']
            if isinstance(window, dict):
                for label, start, end in [('Baseline evidence period', 'baseline_start', 'baseline_end'), ('Comparison evidence period', 'current_start', 'current_end')]:
                    if window.get(start) and window.get(end):
                        value = f"{window[start]} to {window[end]}"
                        if value not in [p[1] for p in periods]:
                            windows.append((item['title'] + ' · ' + label, value))
            elif scalar(window):
                windows.append((item['title'] + ' · Evidence period', window))
        evidence_html += facts(windows) if windows else ''
    else:
        evidence_html = paragraph('No relationship comparison values were supplied.')
    appendix = ''
    for label, source in [("Baseline source", run.get('reference_source')), ("Comparison source" if payload.get('mode') == 'paired' else "Source", run.get('source'))]:
        if source:
            appendix += facts([(label, source['filename']), ('SHA-256', source['sha256'])])
    identity = run['response']['identity']
    supplied = result.get('supplied_reference') or {}
    appendix += facts([('Authority', f"Neraium-1.0 · {identity.get('commit', 'Version not supplied')}"),
                       ('Source clock', supplied.get('timestamp_mode')), ('Timezone provenance', supplied.get('source_timezone', {}).get('status')),
                       ('Run', run['id'])])
    excluded = [s['column'] for s in run.get('mapping', {}).get('signals', []) if not s.get('include', True)]
    if excluded:
        appendix += paragraph('Excluded signals: ' + ', '.join(excluded) + '. Exclusion reasons are retained in the structured evidence.')
    appendix += paragraph('Source files, evidence periods above, input and result hashes, and full structured evidence remain retained with this read-only run.')
    for finding in view['governed_findings']:
        appendix += '<details><summary>Finding evidence and provenance</summary><pre>' + esc(
            json.dumps(finding, allow_nan=False, indent=2)) + '</pre></details>'
    if review and review.get('evidence_reviewed') is True:
        appendix += paragraph(f"Scope and evidence review recorded at {review['created_at']}. Human review remains authoritative; this confirmation does not certify a diagnosis.")
    else:
        appendix += paragraph('No confirmed scope and evidence review is recorded for this rendering.')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NERAIUM | Historical Evaluation | {esc(name)}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f3;color:#172d36;font:15px/1.55 system-ui,-apple-system,sans-serif}}main{{max-width:960px;margin:32px auto;background:white;padding:48px 56px;border-top:5px solid #247c78}}header{{border-bottom:1px solid #cfdddf;padding-bottom:24px}}.brand{{font-size:18px;letter-spacing:.24em;font-weight:750;color:#226b68}}h1{{font-size:34px;line-height:1.15;margin:12px 0 24px;letter-spacing:-.025em}}h2{{overflow-wrap:anywhere;font-size:21px;margin:0 0 14px}}h3{{font-size:16px;margin:0 0 8px}}p{{margin:8px 0;overflow-wrap:anywhere}}section{{margin-top:30px}}.summary{{background:#f0f7f6;border-left:3px solid #247c78;padding:22px}}.summary p{{font-size:17px}}article{{padding:16px 0;border-bottom:1px solid #dce5e6}}dl{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin:12px 0}}dl div{{min-width:0}}dt{{font-size:12px;color:#51666e}}dd{{margin:2px 0 0;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}}table{{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}}th,td{{text-align:left;padding:10px 8px;border-bottom:1px solid #dce5e6;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}}th{{font-size:11px;color:#51666e}}th:first-child{{width:28%}}.timing{{margin-top:16px}}.appendix{{border-top:2px solid #cfdddf;padding-top:20px;font-size:12px;color:#51666e}}.appendix h2{{font-size:17px}}.appendix dl{{gap:6px 20px}}.appendix dt{{font-size:11px}}@media(max-width:600px){{main{{margin:0;padding:28px 20px}}h1{{font-size:30px}}dl{{grid-template-columns:1fr}}.summary{{padding:16px}}thead{{display:none}}tr,td{{display:block}}tr{{padding:12px 0;border-bottom:1px solid #dce5e6}}td{{border:0;padding:5px 0}}td::before{{content:attr(data-label);display:block;font-size:11px;color:#51666e}}}}@page{{size:A4;margin:16mm}}@media print{{body{{background:white;font-size:10pt;line-height:1.4}}header{{padding-bottom:12px}}header h1{{margin:10px 0 12px}}.findings dl{{grid-template-columns:repeat(3,minmax(0,1fr));margin:8px 0;gap:6px 16px}}main{{margin:0;padding:0;max-width:none;border:0}}h1{{font-size:25pt}}h2{{font-size:15pt}}h3{{font-size:11pt}}section{{margin-top:14px}}.summary{{background:white;padding:12px 16px}}.summary p{{font-size:11pt}}h2,h3,dt{{break-after:avoid}}article,.timing,dl div,tr{{break-inside:avoid}}table{{font-size:9pt}}thead{{display:table-header-group}}tr{{display:table-row}}td{{display:table-cell}}td::before{{display:none}}article{{padding:10px 0}}.appendix{{font-size:8pt}}dl{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style></head><body><main>
<header><div class="brand">NERAIUM</div><h1>Historical Evaluation</h1><h2>{esc(name)}</h2>
{paragraph(' · '.join(str(evaluation[k]) for k in ('customer', 'facility', 'system') if evaluation.get(k)))}{facts(periods)}</header>
{section('Executive Summary', paragraph(view['summary']), 'summary')}
{section('Key Findings', findings_html, 'findings')}
{section('Measurable Consequence', consequence_html)}
{section('Evidence', evidence_html)}
{section('Limitations', ''.join(paragraph(v) for v in view['limits']) or paragraph('Interpretation is limited to the supplied periods and evidence shown above.'))}
{section('Technical Appendix', appendix, 'appendix')}
</main></body></html>"""
