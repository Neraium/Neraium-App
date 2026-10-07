// Presentation-only projection of the stored authority contract. No inferred evidence.
const text = value => typeof value === 'string' || typeof value === 'number' ? value : null;
const present = value => text(value) !== null && value !== '';
const list = value => Array.isArray(value) ? value : [];
// Identity-based projection only; equal signal names do not imply equal scope.
const findingIdentity = f => f.id || (f.relationship_evidence_ref && JSON.stringify([
  f.relationship_evidence_ref, f.relationship_source_ref, f.relationship_assessment_binding]));
export function distinctFindings(findings) {
  return findings.filter((f, i) => !findings.slice(0, i).some(previous => {
    const key = findingIdentity(f), previousKey = findingIdentity(previous);
    return key && previousKey ? key === previousKey : JSON.stringify(f) === JSON.stringify(previous);
  }));
}
export function projectedFindings(result) {
  return distinctFindings([...list(result.analysis_result?.relationship_findings),
    ...(list(result.findings).length ? result.findings : list(result.analysis_result?.insights))]);
}
const Paragraphs = ({ values }) => [...new Set(values.filter(present))].map((value, i) => <p key={i}>{value}</p>);
const Facts = ({ values }) => <dl className="evidence-facts">{values.filter(([, value]) => present(value)).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
const period = rows => rows?.length ? `${rows[0].timestamp} → ${rows[rows.length - 1].timestamp}` : null;
const findingName = (finding, i) => finding.title || list(finding.source_tags).filter(present).join(' / ') || `Finding ${i + 1}`;
export default function EvaluationResult({ run }) {
  const result = run.response?.result || {};
  const findings = projectedFindings(result);
  const governed = list(result.analysis_result?.relationship_findings);
  const relationships = list(result.relationship_analysis?.top_relationship_changes);
  const temporal = result.temporal_analysis || {};
  const persistence = result.persistence_analysis?.adaptive_persistence || {};
  const uncertainty = result.uncertainty || {};
  const consequenceEvidence = distinctFindings([...findings, ...list(result.analysis_result?.conditions)]);
  const consequences = consequenceEvidence.map((finding, i) => ({ name: findingName(finding, i), value: finding.measurable_consequence })).filter(({ value }) => value?.status === 'quantified');
  return <div className="evidence-view">
    <section className="result-status"><h2>Evaluation complete</h2>{run.status === 'limited' && <p>Limited evidence returned.</p>}<p>Execution status is not equipment health. No finding does not mean stable.</p>
      <Facts values={[[`Baseline · ${run.reference_source?.filename || 'reference'}`, period(run.input?.reference?.rows)], [`Comparison · ${run.source?.filename || 'dataset'}`, period(run.input?.rows)]]} />
    </section>
    <section className="panel"><h2>Findings / evidence summary</h2>{findings.length ? findings.map((finding, i) => <article className="evidence-entry" key={finding.id || i}><h3>{findingName(finding, i)}</h3><Paragraphs values={[finding.what_changed || finding.what_happened || finding.explanation, finding.confidence_rationale || finding.certainty_limit]} /><Facts values={[["Finding confidence", finding.confidence]]} />
      {governed.includes(finding) && <>
        <Facts values={[["Authority classification", finding.classification?.label || finding.classification?.type],
          ["Relationship persistence", typeof finding.persistence?.persistent === 'boolean' ? (finding.persistence.persistent ? 'Confirmed' : 'Not established') : null]]} />
        <Paragraphs values={[finding.interpretation, finding.persistence?.summary, ...list(finding.supporting_evidence)]} />
        <details><summary>Finding evidence and provenance</summary><pre>{JSON.stringify(finding, null, 2)}</pre></details>
      </>}
    </article>) : <p>No material findings supplied. This does not establish stable behavior.</p>}</section>
    {!!relationships.length && <section className="panel"><h2>Strongest relationship changes</h2>{relationships.map((relationship, i) => <article className="evidence-entry" key={i}><h3>{text(relationship.display_relationship) || text(relationship.relationship)}</h3><Facts values={[["Change", relationship.change_type], ["Baseline correlation", relationship.baseline_correlation], ["Comparison correlation", relationship.recent_correlation], ["Evidence confidence", relationship.confidence_level], ["Baseline samples", relationship.baseline_sample_size], ["Comparison samples", relationship.recent_sample_size]]} /><Paragraphs values={[relationship.data_confidence?.summary, ...list(relationship.operating_mode?.reasons)]} /></article>)}</section>}
    <section className="panel"><h2>Timing / persistence</h2><Facts values={[["Change onset", result.analysis_result?.change_onset], ["Temporal estimate timestamp", temporal.lead_time_estimate?.timestamp], ["Estimate confidence", temporal.lead_time_estimate?.confidence], ["Seconds since comparison start", temporal.lead_time_estimate?.seconds_since_comparison_start], ["Seconds to comparison end", temporal.lead_time_estimate?.seconds_to_comparison_end]]} />
      {temporal.lead_time_estimate && !temporal.lead_time_estimate.timestamp && <p>No onset timestamp supplied by the temporal estimate.</p>}
      <Paragraphs values={findings.flatMap(f => [f.persistence_duration, f.persistence?.summary])} />
      {list(persistence.details).map((detail, i) => <article className="evidence-entry" key={i}><h3>{text(detail.column)}</h3><Facts values={[["Persistence confirmed", typeof detail.persistent === 'boolean' ? (detail.persistent ? 'Yes' : 'No') : null], ["Observed duration (seconds)", detail.observed_duration_seconds], ["Supporting duration (seconds)", detail.supporting_duration_seconds], ["Longest continuous support (seconds)", detail.longest_continuous_support_seconds], ["Required continuous support (seconds)", detail.required_continuous_support_seconds], ["Supporting observations", detail.supporting_observations], ["Required observations", detail.required_observations]]} /></article>)}
      <Paragraphs values={list(persistence.limitations)} />
    </section>
    <section className="panel"><h2>Uncertainty / evidence limits</h2><Paragraphs values={[uncertainty.interpretation, uncertainty.data_confidence?.summary, temporal.uncertainty_summary?.summary, ...findings.map(f => f.certainty_limit), ...list(result.supplied_reference?.limitations).filter(limit => /^(Units |Elapsed persistence |Temporal lead-time |timezone_not_supplied:)/.test(limit)), run.input?.context]} />
      <Facts values={Object.entries(uncertainty.components || {}).map(([key, value]) => [key.replaceAll('_', ' '), value.status])} />
      <Paragraphs values={consequenceEvidence.map(f => f.measurable_consequence?.status !== 'quantified' ? f.measurable_consequence?.statement : null)} />
    </section>
    {!!consequences.length && <section className="panel"><h2>Measurable consequence</h2>{consequences.map(({ name, value }, i) => <article className="evidence-entry" key={i}><h3>{name}</h3><Paragraphs values={[value.statement, ...list(value.limitations)]} /><Facts values={[["Cumulative amount", value.cumulative_amount], ["Unit", value.cumulative_unit], ["Support", value.support_level], ["Observations", value.observation_count]]} /></article>)}</section>}
  </div>;
}
