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
const Facts = ({ values, periods = false }) => {
  const supplied = values.filter(([, value]) => present(value));
  return supplied.length ? <dl className="evidence-facts">{supplied.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{periods ? String(value).split(' → ').map((bound, i) => <span key={i}>{i > 0 && ' → '}<span className="period-bound">{bound}</span></span>) : value}</dd></div>)}</dl> : null;
};
const period = rows => rows?.length ? `${rows[0].timestamp} → ${rows[rows.length - 1].timestamp}` : null;
const findingName = (finding, i) => finding.title || list(finding.source_tags).filter(present).join(' / ') || `Finding ${i + 1}`;
const label = key => key.replaceAll('_', ' ');
const supplied = value => value != null && value !== '' && (typeof value !== 'object' || Object.keys(value).length > 0);
// Show supplied nested fields without interpreting or shortening their contents.
const Fields = ({ value }) => {
  if (!supplied(value)) return null;
  if (Array.isArray(value)) return <ul className="structured-list">{value.map((item, i) => <li key={i}><Fields value={item} /></li>)}</ul>;
  if (typeof value === 'object') return <dl className="structured-fields">{Object.entries(value).filter(([, item]) => supplied(item)).map(([key, item]) => <div key={key}><dt>{label(key)}</dt><dd><Fields value={item} /></dd></div>)}</dl>;
  return <span>{String(value)}</span>;
};
const Disclosure = ({ title, children, className = '' }) => <details className={`result-disclosure ${className}`}><summary>{title}</summary><div className="disclosure-content">{children}</div></details>;
// Limitations and warnings must remain outside disclosure, including nested evidence.
const materialNotes = value => {
  if (!value || typeof value !== 'object') return [];
  return Object.entries(value).flatMap(([key, item]) => {
    if (['warnings', 'limitations', 'certainty_limit'].includes(key)) return Array.isArray(item) ? item.filter(present) : present(item) ? [item] : materialNotes(item);
    return materialNotes(item);
  });
};
// Qualification fields are displayed verbatim, even when their structure varies.
const qualificationFields = value => {
  if (!value || typeof value !== 'object') return [];
  return Object.entries(value).flatMap(([key, item]) => /qualification|qualified|veto/.test(key)
    ? supplied(item) ? [{ [key]: item }] : [] : qualificationFields(item));
};
function FindingCard({ finding, index, governed }) {
  const evidence = finding.relationship_evidence || {};
  const confidence = finding.finding_confidence_v1 || finding.classification?.finding_confidence_v1 || {};
  const mode = finding.operating_mode || {};
  const persistence = finding.persistence || {};
  const signals = list(finding.source_tags).filter(present).join(' / ');
  const title = findingName(finding, index);
  const limits = [...new Set([
    finding.confidence_rationale, ...materialNotes(finding), ...list(finding.classification?.reasons),
    ...list(mode.reasons), confidence.operating_context?.reason,
    ...(persistence.persistent === false ? [persistence.summary, ...list(persistence.reasons)] : []),
    ...list(finding.data_confidence?.reasons)
  ].filter(present))];
  const qualification = qualificationFields(finding);
  return <article className="finding-card evidence-entry" aria-labelledby={`finding-${index}`}>
    <header>
      {present(finding.classification?.label || finding.classification?.type) && <div className="finding-classification">{finding.classification.label || finding.classification.type}</div>}
      <h3 id={`finding-${index}`}>{signals || title}</h3>
      {signals && title !== signals && <p className="finding-title">{title}</p>}
      <div className="finding-change"><Paragraphs values={[finding.what_changed || finding.what_happened || finding.explanation]} /></div>
      <Facts values={[
        ['Relationship persistence', typeof persistence.persistent === 'boolean' ? (persistence.persistent ? 'Confirmed' : 'Not established') : text(persistence.status)],
        ['Finding confidence', finding.confidence], ['Change detection', confidence.change_detection?.level],
        ['Evidence quality', confidence.evidence_quality?.level || finding.data_confidence?.rating]
      ]} />
    </header>
    {(limits.length > 0 || qualification.length > 0) && <div className="finding-limits"><span className="detail-label">Interpretation / evidence limits</span><Paragraphs values={limits} />{qualification.map((value, i) => <Fields key={i} value={value} />)}</div>}
    <div className="finding-details">
      <Disclosure title="Evidence">
        <Paragraphs values={[finding.interpretation, ...list(finding.supporting_evidence), finding.data_confidence?.summary, confidence.change_detection?.reason, confidence.evidence_quality?.reason]} />
        <Facts values={[["Evidence type", evidence.evidence_type], ["Evidence confidence score", evidence.confidence_score]]} />
        {supplied(evidence.evidence_refs) && <Disclosure title="Source observations"><Fields value={evidence.evidence_refs} /></Disclosure>}
      </Disclosure>
      {supplied(mode) && <Disclosure title="Operating context"><Fields value={mode} /></Disclosure>}
      {(supplied(persistence) || present(finding.persistence_duration)) && <Disclosure title="Timing / persistence"><Paragraphs values={[finding.persistence_duration, persistence.summary]} /><Fields value={persistence} /></Disclosure>}
      {(supplied(evidence) || supplied(finding.source_time_ranges) || supplied(finding.time_window)) && <Disclosure title="Reference vs comparison">
        <Facts values={[["Baseline correlation", evidence.baseline_correlation], ["Comparison correlation", evidence.recent_correlation], ["Baseline observations", evidence.baseline_sample_size], ["Comparison observations", evidence.recent_sample_size]]} />
        <Fields value={confidence.relationship_comparison} />
        <Fields value={finding.source_time_ranges || finding.time_window || evidence.time_window} />
        {supplied(evidence.supporting_metric_pairs) && <Disclosure title="Supporting metric pairs"><Fields value={evidence.supporting_metric_pairs} /></Disclosure>}
      </Disclosure>}
      {governed && <Disclosure title="Provenance / technical details" className="finding-provenance"><pre>{JSON.stringify(finding, null, 2)}</pre></Disclosure>}
    </div>
  </article>;
}
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
  const classifications = distinctFindings(governed).reduce((counts, finding) => {
    const classification = text(finding.classification?.label) || text(finding.classification?.type);
    if (present(classification)) counts.set(classification, (counts.get(classification) || 0) + 1);
    return counts;
  }, new Map());
  const limits = [...new Set([
    uncertainty.interpretation, temporal.uncertainty_summary?.summary, ...materialNotes(uncertainty),
    ...materialNotes(temporal), ...materialNotes(persistence), ...materialNotes(result.supplied_reference),
    ...materialNotes(result.data_conditions), ...list(result.analysis_result?.warnings), ...list(result.analysis_result?.errors),
    ...list(result.warnings), ...relationships.flatMap(r => [...materialNotes(r), ...list(r.operating_mode?.reasons), ...list(r.data_confidence?.reasons)]),
    ...consequenceEvidence.flatMap(f => [...materialNotes(f.measurable_consequence), f.measurable_consequence?.status !== 'quantified' ? f.measurable_consequence?.statement : null]),
    run.input?.context
  ].filter(present))];
  return <div className="evidence-view">
    <section className="result-status" aria-labelledby="result-summary">
      <div className="result-summary-heading"><div><span className="eyebrow">RESULTS</span><h2 id="result-summary">Evaluation complete</h2></div><a className="report-link" href="#report-export">Review &amp; export report <span aria-hidden="true">↗</span></a></div>
      {run.status === 'limited' && <p className="completion-limit">Limited evidence returned.</p>}
      <div className="classification-counts"><span className="governed-count"><strong>{distinctFindings(governed).length}</strong> governed findings</span>{[...classifications].map(([classification, count]) => <span key={classification}><strong>{count}</strong> {classification}</span>)}</div>
      <p>Execution status is not equipment health. No finding does not mean stable.</p>
      <Facts periods values={[[`Baseline · ${run.reference_source?.filename || 'reference'}`, period(run.input?.reference?.rows)], [`Comparison · ${run.source?.filename || 'dataset'}`, period(run.input?.rows)]]} />
    </section>
    <section className="findings-section" aria-labelledby="findings-heading"><div className="section-heading"><h2 id="findings-heading">Findings / evidence summary</h2><span>Expand a section to inspect evidence</span></div>
      {findings.length ? <div className="finding-grid">{findings.map((finding, i) => <FindingCard finding={finding} index={i} governed={governed.includes(finding)} key={finding.id || i} />)}</div> : <p>No material findings supplied. This does not establish stable behavior.</p>}
    </section>
    {!!limits.length && <section className="material-limits" aria-labelledby="material-limits-heading"><h2 id="material-limits-heading">Material limitations</h2><Paragraphs values={limits} /></section>}
    <div className="secondary-evidence">
      {!!relationships.length && <Disclosure title="Strongest relationship changes">{relationships.map((relationship, i) => <article className="evidence-entry" key={i}><h3>{text(relationship.display_relationship) || text(relationship.relationship)}</h3><Facts values={[["Change", relationship.change_type], ["Baseline correlation", relationship.baseline_correlation], ["Comparison correlation", relationship.recent_correlation], ["Evidence confidence", relationship.confidence_level], ["Baseline samples", relationship.baseline_sample_size], ["Comparison samples", relationship.recent_sample_size]]} /><Paragraphs values={[relationship.data_confidence?.summary, ...list(relationship.operating_mode?.reasons)]} /></article>)}</Disclosure>}
      <Disclosure title="Timing / persistence"><Facts values={[["Change onset", result.analysis_result?.change_onset], ["Temporal estimate timestamp", temporal.lead_time_estimate?.timestamp], ["Estimate confidence", temporal.lead_time_estimate?.confidence], ["Seconds since comparison start", temporal.lead_time_estimate?.seconds_since_comparison_start], ["Seconds to comparison end", temporal.lead_time_estimate?.seconds_to_comparison_end]]} />
        {temporal.lead_time_estimate && !temporal.lead_time_estimate.timestamp && <p>No onset timestamp supplied by the temporal estimate.</p>}
        <Paragraphs values={findings.flatMap(f => [f.persistence_duration, f.persistence?.summary])} />
        {list(persistence.details).map((detail, i) => <article className="evidence-entry" key={i}><h3>{text(detail.column)}</h3><Facts values={[["Persistence confirmed", typeof detail.persistent === 'boolean' ? (detail.persistent ? 'Yes' : 'No') : null], ["Observed duration (seconds)", detail.observed_duration_seconds], ["Supporting duration (seconds)", detail.supporting_duration_seconds], ["Longest continuous support (seconds)", detail.longest_continuous_support_seconds], ["Required continuous support (seconds)", detail.required_continuous_support_seconds], ["Supporting observations", detail.supporting_observations], ["Required observations", detail.required_observations]]} /></article>)}
        <Paragraphs values={list(persistence.limitations)} />
      </Disclosure>
      <Disclosure title="Uncertainty / evidence limits"><Paragraphs values={[uncertainty.interpretation, uncertainty.data_confidence?.summary, temporal.uncertainty_summary?.summary, ...findings.map(f => f.certainty_limit), ...list(result.supplied_reference?.limitations), run.input?.context]} />
        <Facts values={Object.entries(uncertainty.components || {}).map(([key, value]) => [label(key), value.status])} />
        <Paragraphs values={consequenceEvidence.map(f => f.measurable_consequence?.status !== 'quantified' ? f.measurable_consequence?.statement : null)} />
      </Disclosure>
    </div>
    {!!consequences.length && <section className="panel"><h2>Measurable consequence</h2>{consequences.map(({ name, value }, i) => <article className="evidence-entry" key={i}><h3>{name}</h3><Paragraphs values={[value.statement, ...list(value.limitations)]} /><Facts values={[["Cumulative amount", value.cumulative_amount], ["Unit", value.cumulative_unit], ["Support", value.support_level], ["Observations", value.observation_count]]} /></article>)}</section>}
  </div>;
}
