import { useEffect, useState } from 'react';
import { get, post, upload, download } from './api';
import { suggestedMapping, mappingIssues, classificationIssues } from './intake';
import './workbench.css';
const Json = ({ value }) => <pre>{JSON.stringify(value, null, 2)}</pre>;
const isVerification = item => /^(?:browser )?deployment check \(synthetic\)$/i.test((item.customer || '').trim().replace(/\s+/g, ' '));
const title = item => item.label || [item.customer, item.system].filter(Boolean).join(' · ') || `Evaluation · ${item.created_at?.slice(0, 19) || item.id}`;
const message = e => typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message;
export default function App() {
  const [items, setItems] = useState([]), [evaluation, setEvaluation] = useState(null), [authority, setAuthority] = useState(null);
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [label, setLabel] = useState('');
  const [mapping, setMapping] = useState({ signals: [], context: '' });
  const [timeIssues, setTimeIssues] = useState({}), [times, setTimes] = useState({});
  const [classifications, setClassifications] = useState([]), [classesConfirmed, setClassesConfirmed] = useState(false);
  const [run, setRun] = useState(null), [review, setReview] = useState(null), [reviewer, setReviewer] = useState(''), [reviewed, setReviewed] = useState(false);
  useEffect(() => {
    let active = true;
    setBusy('Loading evaluations');
    Promise.all([get('/evaluations'), get('/authority')])
      .then(([list, state]) => { if (active) { setItems(list); setAuthority(state); } })
      .catch(e => { if (active) setError(message(e)); })
      .finally(() => { if (active) setBusy(''); });
    return () => { active = false; };
  }, []);
  async function act(label, fn) {
    setBusy(label); setError('');
    try { await fn(); } catch(e) { setError(message(e)); }
    finally { setBusy(''); }
  }
  async function refresh(id) {
    const [list, item] = await Promise.all([get('/evaluations'), get(`/evaluations/${id}`)]);
    setItems(list); setEvaluation(item); return item;
  }
  function clearResult() { setRun(null); setReview(null); setReviewed(false); setClassifications([]); setClassesConfirmed(false); }
  async function prepare(id) {
    let item = await refresh(id);
    const issues = {};
    for (const role of item.mode === 'paired' ? ['reference', 'comparison'] : ['comparison']) {
      const source = role === 'reference' ? item.reference_source : item.source;
      const quality = role === 'reference' ? item.reference_validation : item.validation;
      if (source && !quality) {
        setBusy(`Validating ${role === 'reference' ? 'baseline' : 'comparison'} dataset`);
        try { await post(`/evaluations/${id}/validate?role=${role}`, {}); }
        catch (e) { issues[role] = message(e); }
      }
    }
    item = await refresh(id);
    setMapping(suggestedMapping(item)); setTimeIssues(issues);
  }
  async function select(id) { clearResult(); setTimes({}); await prepare(id); }
  async function receive(file, role) {
    clearResult();
    let id = evaluation?.id;
    if (!id) { const item = await post('/evaluations', { mode: 'paired', label }); id = item.id; await refresh(id); }
    await upload(id, file, role);
    await prepare(id);
  }
  function editSignal(index, field, value) {
    setMapping({ ...mapping, signals: mapping.signals.map((s, i) => i === index ? { ...s, [field]: value } : s) });
    setClassifications([]); setClassesConfirmed(false);
  }
  const paired = !evaluation || evaluation.mode === 'paired';
  const both = evaluation?.source && (!paired || evaluation.reference_source);
  const valid = evaluation?.validation?.eligible_timestamps && (!paired || evaluation.reference_validation?.eligible_timestamps);
  const schemaMismatch = valid && paired && JSON.stringify(evaluation.validation.signals.map(s => s.column).sort()) !== JSON.stringify(evaluation.reference_validation.signals.map(s => s.column).sort());
  const issues = evaluation ? mappingIssues(mapping, evaluation) : [];
  const count = mapping.signals.filter(s => s.include).length;
  const ready = valid && !schemaMismatch && !issues.length && count > 0 && count <= 24 && (!classifications.length || classesConfirmed);
  const action = (label, fn, disabled = false) => <button disabled={!!busy || disabled} onClick={() => act(label, fn)}>{label}</button>;
  const operatorItems = items.filter(item => !isVerification(item));
  const signalEditor = (s, i) => <div className="signal-editor" key={s.column}><strong>{s.column}</strong><label><input type="checkbox" checked={s.include} onChange={e => editSignal(i, 'include', e.target.checked)} />Include {s.column}</label>{(s.include ? ['meaning', 'unit'] : ['reason']).map(f => <label key={f}>{f === 'reason' ? 'Exclusion reason' : f === 'unit' ? 'Matching unit' : 'Signal meaning'}<input aria-label={`${s.column} ${f}`} maxLength={f === 'unit' ? 40 : f === 'meaning' ? 160 : 500} value={s[f]} onChange={e => editSignal(i, f, e.target.value)} /></label>)}</div>;
  return <div className="workbench">
    <header><span className="eyebrow">NERAIUM · INTERNAL</span><h1>Historical Evaluation</h1><p>Upload two historical datasets, run evaluation, and review evidence.</p></header>
    <p>Read-only analysis. Evidence limits and uncertainty remain explicit. No control actions.</p>
    {error && <div className="error" role="alert">{error}</div>}{busy && <p role="status" className="notice">{busy}…</p>}
    {authority?.available === false && <p className="error" role="alert">Authority: {authority.reason}</p>}
    <fieldset disabled={!!busy}><div className="layout"><main>
    {!evaluation ? <label className="evaluation-label">Evaluation name (optional)<input maxLength={200} value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. September comparison" /></label> : <h2>{title(evaluation)}</h2>}
    <p className="upload-help">Same physical system and signal identities in both files. UTF-8 CSV, TSV or JSON · 10 MiB, 10,000 rows, 64 columns per file. Units in headers such as pressure [bar] are mapped automatically.</p>
    <div className="uploads">{(paired ? ['reference', 'comparison'] : ['comparison']).map(role => {
      const name = role === 'reference' ? 'Baseline dataset' : 'Comparison dataset';
      const source = role === 'reference' ? evaluation?.reference_source : evaluation?.source;
      const quality = role === 'reference' ? evaluation?.reference_validation : evaluation?.validation;
      const time = times[role] || { timestamp_column: '', timestamp_mode: 'iso' };
      return <section className="panel" key={role}><h2>{name}</h2><label>{source ? 'Replace file' : 'Upload file'}<input aria-label={name} type="file" accept=".csv,.tsv,.json" onChange={e => { const file = e.target.files[0]; e.target.value = ''; if (file) act(`Uploading ${name.toLowerCase()}`, () => receive(file, role)); }} /></label>
      {source && <><p>{source.filename}</p>{quality?.eligible_timestamps && <p>{quality.row_count} rows · Validated</p>}<details><summary>File provenance and validation</summary><p>SHA-256 <code>{source.sha256}</code></p><p>Uploaded {source.received_at}</p>{action('Download original', () => download(`/sources/${source.id}/original`, source.filename))}{quality && <Json value={quality} />}</details></>}
      {timeIssues[role] && <div><p role="alert">{timeIssues[role]}</p><label>Timestamp column<select value={time.timestamp_column} onChange={e => setTimes({ ...times, [role]: { ...time, timestamp_column: e.target.value } })}><option value="">Choose…</option>{source?.columns.map(c => <option key={c}>{c}</option>)}</select></label><label>Timestamp format<select value={time.timestamp_mode} onChange={e => setTimes({ ...times, [role]: { ...time, timestamp_mode: e.target.value } })}><option value="iso">ISO with timezone</option><option value="epoch_seconds">Unix seconds</option><option value="epoch_milliseconds">Unix milliseconds</option></select></label>{action('Apply timestamp', async () => { await post(`/evaluations/${evaluation.id}/validate?role=${role}`, time); await prepare(evaluation.id); }, !time.timestamp_column)}</div>}
      {quality && !quality.eligible_timestamps && <div role="alert"><p>Replace this file to resolve timestamp errors.</p>{quality.warnings.map(w => <p key={w}>{w}</p>)}</div>}
      </section>;
    })}</div>
    {schemaMismatch && <p role="alert" className="error">Signal columns differ between files. Upload matching signal schemas; automatic renaming is not supported.</p>}
    {valid && !schemaMismatch && <>
      {!!issues.length && <section className="panel"><h2>Mapping needs attention</h2>{issues.map(({ index, problems }) => <div key={mapping.signals[index].column}><p>{problems.join(' ')}</p>{signalEditor(mapping.signals[index], index)}</div>)}</section>}
      {(count === 0 || count > 24) && <p role="alert">Include 1–24 signals using Signal mapping below.</p>}
      <details><summary>Signal mapping and optional context</summary><p>Shared mapping for both full periods. Missing values remain missing; no unit conversion.</p>{mapping.signals.map(signalEditor)}<label>Context and known limitations (optional)<textarea maxLength={2000} value={mapping.context} onChange={e => { setMapping({ ...mapping, context: e.target.value }); setClassesConfirmed(false); }} /></label></details>
    </>}
    {!!classifications.length && <section className="panel"><h2>Classification needs attention</h2>{classifications.map(c => <div key={c.column}><h3>{c.column}</h3><Json value={c} /></div>)}<p>Revise the signal meaning or exclusion in Signal mapping, or confirm the supplied classification and its limits.</p><label><input type="checkbox" checked={classesConfirmed} onChange={e => setClassesConfirmed(e.target.checked)} />I reviewed these classifications and limits.</label></section>}
    {both && <section className="panel run-action"><p>By running, you confirm these files describe the same physical system with matching signal identities and units. The shared mapping excludes outcome labels.</p>{action('Run Evaluation', async () => {
      clearResult();
      const root = `/evaluations/${evaluation.id}`;
      setBusy('Checking signal mapping');
      const preview = await post(`${root}/mapping-preview`, { ...mapping, pair_confirmed: paired });
      const pending = classificationIssues(preview, mapping);
      if (pending.length && !classesConfirmed) { setClassifications(pending); return; }
      await post(`${root}/approve-mapping`, { preview_id: preview.id, confirmed: true });
      setBusy('Running evaluation — up to 120 seconds');
      const r = await post(`${root}/runs`);
      const saved = await get(`/runs/${r.id}`); setRun(saved); setReview(saved.reviews?.[0] || null);
      await refresh(evaluation.id);
    }, !ready || authority?.available !== true)}<p>A completed run may contain limited evidence or no findings.</p></section>}
    {run && <section className="panel"><h2>Review evidence</h2><p>Run <code>{run.id}</code> · <strong>{run.status}</strong> · source {run.source.filename}</p>{run.reference_source && <><p>Reference: {run.reference_source.filename} · {run.reference_validation.start} → {run.reference_validation.end} · SHA-256 <code>{run.reference_source.sha256}</code></p><p>Comparison SHA-256 <code>{run.source.sha256}</code></p></>}{run.error && <p className="error">{run.error}</p>}{run.status === 'running' && <p>No terminal result stored. If the server was interrupted, start a new run; this record is not usable evidence.</p>}
    {run.response && <><p>Execution status is not equipment health. No finding does not mean stable.</p><p>Window: {run.input.rows[0].timestamp} → {run.input.rows[run.input.rows.length - 1].timestamp}</p>{Object.entries(run.evidence_sections).map(([label, v]) => <details key={label}><summary>{label}</summary>{Array.isArray(v) && !v.length ? <p>No entries supplied by the authoritative engine.</p> : <Json value={v} />}</details>)}<details><summary>Full authoritative result and module limitations</summary><Json value={run.response.result} /></details></>}
    {action('Download evidence JSON', () => download(`/runs/${run.id}/evidence`, `neraium-evidence-${run.id}.json`))}
    {['complete', 'limited'].includes(run.status) && <><h3>Record evidence review</h3><label>Reviewer name<input value={reviewer} onChange={e => setReviewer(e.target.value)} /></label><label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed this run's scope, source, mapping, results and evidence limitations.</label>{action('Record review', async () => { setReview(await post(`/runs/${run.id}/reviews`, { reviewer, evidence_reviewed: true })); await refresh(evaluation.id); }, !reviewed || !reviewer.trim())}
    {review && <><h2>Export report</h2>{action('Export report', () => download(`/reviews/${review.id}/report`, `neraium-report-${run.id}.html`))}<p>Open the HTML to print/save as PDF. Deliver with evidence JSON. The report uses engine evidence only, without generated diagnosis or consequence estimates.</p></>}</>}
    </section>}

    </main><aside><details className="panel history"><summary>Evaluations and history</summary><label>Select evaluation<select value={operatorItems.some(item => item.id === evaluation?.id) ? evaluation.id : ''} onChange={e => e.target.value && act('Loading evaluation', () => select(e.target.value))}><option value="">Choose…</option>{operatorItems.map(item => <option key={item.id} value={item.id}>{title(item)}</option>)}</select></label><button onClick={() => { setEvaluation(null); setLabel(''); setMapping({ signals: [], context: '' }); setTimeIssues({}); setTimes({}); setError(''); clearResult(); }}>New Evaluation</button>
    {evaluation && <><h3>{title(evaluation)}</h3>{[evaluation.facility, evaluation.scope].filter(Boolean).map((s, i) => <p key={i}>{s}</p>)}<h3>Preserved runs</h3>{evaluation.runs?.map(r => <div key={r.id}>{action(`${r.status} · ${r.created_at.slice(0, 19)}`, async () => { const saved = await get(`/runs/${r.id}`); setRun(saved); setReview(saved.reviews?.[0] || null); setReviewed(false); })}</div>)}</>}
    </details></aside></div></fieldset>
    {authority?.available && <details className="provenance"><summary>Provenance · Neraium-1.0</summary><Json value={authority.identity} /></details>}
  </div>;
}
