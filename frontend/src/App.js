import { useEffect, useState } from 'react';
import { get, post, upload, download } from './api';
import { suggestedMapping, mappingIssues, classificationIssues } from './intake';
import './workbench.css';
import EvaluationResult from './EvaluationResult';
const Json = ({ value }) => <pre>{JSON.stringify(value, null, 2)}</pre>;
function RawEvidence({ run }) {
  const [open, setOpen] = useState(false);
  return <details onToggle={event => setOpen(event.currentTarget.open)}><summary>Raw structured evidence and processing trace</summary>{open && <Json value={run} />}</details>;
}
const isVerification = item => /^(?:browser )?deployment check \(synthetic\)$/i.test((item.customer || '').trim().replace(/\s+/g, ' '));
const title = item => item.label || [item.customer, item.system].filter(Boolean).join(' · ') || `Evaluation · ${item.created_at?.slice(0, 19) || item.id}`;
const message = e => typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message;
export default function App() {
  const [items, setItems] = useState([]), [evaluation, setEvaluation] = useState(null), [authority, setAuthority] = useState(null);
  const [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [checking, setChecking] = useState(false), [preparedKey, setPreparedKey] = useState('');
  const [checkAttempt, setCheckAttempt] = useState(0), [autoPrepare, setAutoPrepare] = useState(false);
  const [mapping, setMapping] = useState({ signals: [], context: '' });
  const [timeIssues, setTimeIssues] = useState({}), [times, setTimes] = useState({});
  const [classifications, setClassifications] = useState([]), [classesConfirmed, setClassesConfirmed] = useState(false);
  const [run, setRun] = useState(null), [review, setReview] = useState(null);
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
  function clearResult() { setRun(null); setReview(null); setClassifications([]); setClassesConfirmed(false); }
  async function prepare(id) {
    setTimeIssues({});
    let item = await refresh(id);
    const issues = {}, detectedTimes = {};
    for (const role of item.mode === 'paired' ? ['reference', 'comparison'] : ['comparison']) {
      const source = role === 'reference' ? item.reference_source : item.source;
      const quality = role === 'reference' ? item.reference_validation : item.validation;
      if (source && !quality) {
        setBusy(`Validating ${role === 'reference' ? 'baseline' : 'comparison'} dataset`);
        try { await post(`/evaluations/${id}/validate?role=${role}`, {}); }
        catch (e) {
          const choices = e.response?.data?.timestamp_review;
          if (choices || message(e).startsWith('Timestamp needs review')) {
            issues[role] = { message: message(e), ...choices };
            detectedTimes[role] = { timestamp_column: '', timestamp_mode: '', ...choices };
          } else { throw e; }
        }
      }
    }
    item = await refresh(id);
    setMapping(suggestedMapping(item)); setTimeIssues(issues); setTimes(detectedTimes);
  }
  async function select(id) { setAutoPrepare(false); clearResult(); setTimes({}); await prepare(id); }
  async function receive(file, role) {
    clearResult();
    let id = evaluation?.id;
    if (!id) { const item = await post('/evaluations', { mode: 'paired' }); id = item.id; await refresh(id); }
    await upload(id, file, role);
    setAutoPrepare(true);
    await prepare(id);
  }
  function editSignal(index, field, value) {
    setAutoPrepare(true);
    setMapping({ ...mapping, signals: mapping.signals.map((s, i) => i === index ? { ...s, [field]: value } : s) });
    setClassifications([]); setClassesConfirmed(false);
  }
  const successful = run && ['complete', 'limited'].includes(run.status);
  const paired = !evaluation || evaluation.mode === 'paired';
  const both = evaluation?.source && (!paired || evaluation.reference_source);
  const valid = evaluation?.validation?.eligible_timestamps && (!paired || evaluation.reference_validation?.eligible_timestamps);
  const schemaMismatch = valid && paired && JSON.stringify(evaluation.validation.signals.map(s => s.column).sort()) !== JSON.stringify(evaluation.reference_validation.signals.map(s => s.column).sort());
  const issues = evaluation ? mappingIssues(mapping, evaluation) : [];
  const count = mapping.signals.filter(s => s.include).length;
  const timestampMismatch = valid && paired && (evaluation.validation.timestamp_mode === "naive_historical_source_clock") !== (evaluation.reference_validation.timestamp_mode === "naive_historical_source_clock");
  const compatible = valid && !timestampMismatch && !schemaMismatch && !issues.length && count > 0 && count <= 24;
  const mappingKey = JSON.stringify([evaluation?.id, evaluation?.reference_source?.id, evaluation?.source?.id, mapping]);
  useEffect(() => {
    if (!autoPrepare || !compatible || busy || authority?.available !== true || preparedKey === mappingKey) return;
    let active = true;
    setChecking(true); setError('');
    post(`/evaluations/${evaluation.id}/mapping-preview`, { ...mapping, pair_confirmed: paired })
      .then(preview => {
        if (!active) return;
        const resolved = preview.mapping || mapping;
        setMapping(resolved);
        setEvaluation(current => ({ ...current, preview }));
        setClassifications(classificationIssues(preview, resolved));
        setClassesConfirmed(false);
        setPreparedKey(JSON.stringify([evaluation.id, evaluation.reference_source?.id, evaluation.source?.id, resolved]));
      })
      .catch(e => { if (active) setError(message(e)); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; setChecking(false); };
    // mappingKey captures the full mapping and both source identities.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mappingKey, compatible, busy, authority?.available, preparedKey, checkAttempt, autoPrepare]);
  const ready = compatible && (!autoPrepare || preparedKey === mappingKey) && (!classifications.length || classesConfirmed);
  const action = (label, fn, disabled = false) => <button disabled={!!busy || checking || disabled} onClick={() => act(label, fn)}>{label}</button>;
  const operatorItems = items.filter(item => !isVerification(item));
  const signalEditor = (s, i) => <div className="signal-editor" key={s.column}><strong>{s.column}</strong><label><input type="checkbox" checked={s.include} onChange={e => editSignal(i, 'include', e.target.checked)} />Include {s.column}</label>{(s.include ? [...(s.meaning !== s.column ? ['meaning'] : []), 'unit'] : ['reason']).map(f => <label key={f}>{f === 'reason' ? 'Exclusion reason' : f === 'unit' ? 'Matching unit' : 'Signal meaning'}<input aria-label={`${s.column} ${f}`} maxLength={f === 'unit' ? 40 : f === 'meaning' ? 160 : 500} value={s[f]} onChange={e => editSignal(i, f, e.target.value)} /></label>)}</div>;
  return <div className="workbench">
    <header><h1>Historical Evaluation</h1></header>
    {error && <div className="error" role="alert">{error}</div>}{(busy || checking) && <p role="status" className="notice">{busy || 'Checking datasets'}…</p>}
    {authority?.available === false && <p className="error" role="alert">Evaluation unavailable: {authority.reason}</p>}
    <fieldset disabled={!!busy || checking}><div className="layout"><main>
    {!successful && <>
    <div className="uploads">{(paired ? ['reference', 'comparison'] : ['comparison']).map(role => {
      const name = role === 'reference' ? 'Baseline dataset' : 'Comparison dataset';
      const source = role === 'reference' ? evaluation?.reference_source : evaluation?.source;
      const quality = role === 'reference' ? evaluation?.reference_validation : evaluation?.validation;
      const time = times[role] || { timestamp_column: '', timestamp_mode: '' };
      return <section className="panel" key={role}><h2>{name}</h2><label><input aria-label={name} type="file" accept=".csv,.tsv,.json" onChange={e => { const file = e.target.files[0]; e.target.value = ''; if (file) act(`Uploading ${name.toLowerCase()}`, () => receive(file, role)); }} /></label>
      {source && <><p className="file-status">{source.filename}{quality?.eligible_timestamps && <> · {quality.row_count} rows · Validated</>}</p><details><summary>File provenance and validation</summary><p>SHA-256 <code>{source.sha256}</code></p><p>Uploaded {source.received_at}</p>{action('Download original', () => download(`/sources/${source.id}/original`, source.filename))}{quality && <Json value={quality} />}</details></>}
      {timeIssues[role] && <details className="timestamp-review" open><summary>Timestamp needs review</summary><p role="alert">{timeIssues[role].message}</p><div className="timestamp-controls">
        {!timeIssues[role].timestamp_column && <label>Timestamp column<select aria-label="Timestamp column" value={time.timestamp_column} onChange={e => setTimes({ ...times, [role]: { ...time, timestamp_column: e.target.value } })}><option value="">Choose…</option>{source?.columns.map(c => <option key={c}>{c}</option>)}</select></label>}
        {!timeIssues[role].timestamp_mode && <label>Timestamp format<select aria-label="Timestamp format" value={time.timestamp_mode} onChange={e => setTimes({ ...times, [role]: { ...time, timestamp_mode: e.target.value } })}><option value="">Choose…</option><option value="iso">ISO with timezone</option>{paired && <option value="naive_historical_source_clock">YYYY-MM-DD HH:MM:SS (timezone not supplied)</option>}<option value="epoch_seconds">Unix seconds</option><option value="epoch_milliseconds">Unix milliseconds</option></select></label>}
        {action('Apply timestamp', async () => { await post(`/evaluations/${evaluation.id}/validate?role=${role}`, time); await prepare(evaluation.id); }, !time.timestamp_column || !time.timestamp_mode)}
      </div></details>}
      {quality && !quality.eligible_timestamps && <div role="alert"><p>Replace this file to resolve timestamp errors.</p>{quality.warnings.map(w => <p key={w}>{w}</p>)}</div>}
      </section>;
    })}</div>
    {timestampMismatch && <p role="alert" className="error">Paired timestamp modes must match. Upload both periods using source-clock timestamps or both using timezone-aware timestamps.</p>}
    {schemaMismatch && <p role="alert" className="error">Signal columns differ between files. Upload matching signal schemas; automatic renaming is not supported.</p>}
    {valid && !schemaMismatch && <>
      {!!issues.length && <section className="panel"><h2>Mapping needs attention</h2>{issues.map(({ index, problems }) => <div key={mapping.signals[index].column}><p>{problems.join(' ')}</p>{signalEditor(mapping.signals[index], index)}</div>)}</section>}
      {(count === 0 || count > 24) && <p role="alert">Include 1–24 signals using Dataset settings below.</p>}
    </>}
    {!!classifications.length && <section className="panel"><h2>Classification needs attention</h2>{classifications.map(c => <div key={c.column}><h3>{c.column}</h3><p>{c.reason}</p></div>)}<p>Revise the signal meaning or exclusion in Dataset settings, or confirm the supplied classification and its limits.</p><label><input type="checkbox" checked={classesConfirmed} onChange={e => setClassesConfirmed(e.target.checked)} />I reviewed the unresolved classifications and treatment limits.</label></section>}
    {compatible && error && !checking && preparedKey !== mappingKey && <button onClick={() => setCheckAttempt(n => n + 1)}>Retry dataset check</button>}
    {both && <section className="run-action">{action('Run Evaluation', async () => {
      clearResult();
      const root = `/evaluations/${evaluation.id}`;
      setBusy('Checking datasets');
      const preview = await post(`${root}/mapping-preview`, { ...mapping, pair_confirmed: paired });
      const resolvedMapping = preview.mapping || mapping;
      setMapping(resolvedMapping);
      setEvaluation(current => ({ ...current, preview }));
      const pending = classificationIssues(preview, resolvedMapping);
      if (pending.length && (!classesConfirmed || JSON.stringify(pending) !== JSON.stringify(classifications))) { setClassifications(pending); return; }
      await post(`${root}/approve-mapping`, { preview_id: preview.id, confirmed: true });
      setBusy('Running evaluation');
      const r = await post(`${root}/runs`);
      const saved = await get(`/runs/${r.id}`); setRun(saved); setReview(saved.reviews?.[0] || null);
      await refresh(evaluation.id);
    }, !ready || authority?.available !== true)}</section>}
    {valid && !schemaMismatch && <>
      <details><summary>Dataset settings</summary><p>Shared mapping for both full periods. Missing values remain missing; no unit conversion.</p>{mapping.signals.map((s, i) => <div key={s.column}><p><strong>{s.column}</strong> · {s.include ? s.unit || 'Unit needs review' : s.reason}</p><details><summary>Adjust mapping for {s.column}</summary>{signalEditor(s, i)}</details></div>)}<label>Context and known limitations (optional)<textarea maxLength={2000} value={mapping.context} onChange={e => { setAutoPrepare(true); setMapping({ ...mapping, context: e.target.value }); setClassesConfirmed(false); }} /></label></details>
    </>}
    {!!(run ? run.evaluation?.preview?.exclusions : evaluation?.preview?.exclusions)?.length && <details className="mapping-provenance"><summary>Automatic paired exclusions</summary><p>Excluded from paired analysis. Original columns and values remain in both uploaded files; no counter values were transformed or analyzed.</p><Json value={run ? run.evaluation.preview.exclusions : evaluation.preview.exclusions} /></details>}
    {(run ? run.evaluation?.preview : evaluation?.preview) && <details className="classification-provenance"><summary>Evaluation provenance</summary><Json value={run ? run.evaluation.preview : evaluation.preview} /></details>}
    {evaluation && authority?.available && <details className="provenance"><summary>Provenance · Neraium-1.0</summary><Json value={authority.identity} /></details>}
    </>}
    {successful && <>
      <EvaluationResult run={run} />
      <section className="report-export"><h2>Export report</h2><p>{review ? 'Evidence review recorded. Export uses the existing review.' : 'Not yet reviewed. Export report records your confirmation that you have inspected this run’s scope and evidence, under “Internal operator”. It does not certify a diagnosis.'}</p>
        {action('Export report', async () => {
          let record = review;
          if (!record) { record = await post(`/runs/${run.id}/reviews`, { reviewer: 'Internal operator', evidence_reviewed: true }); setReview(record); }
          await download(`/reviews/${record.id}/report`, `neraium-report-${run.id}.html`);
        })}<p>Printable HTML. Include the evidence JSON for the complete record.</p>
      </section>
    </>}
    {run && !successful && <section className="panel"><h2>Evaluation {run.status}</h2>{run.error && <p className="error">{run.error}</p>}{run.status === 'running' && <p>No terminal result stored. If the server was interrupted, start a new run; this record is not usable evidence.</p>}</section>}
    {run && <details className="technical-details" key={run.id}><summary>Technical details</summary>
      <h3>Source files and hashes</h3>{[run.reference_source, run.source].filter(Boolean).map((source, i) => <div key={i}><p>{source === run.reference_source ? 'Baseline' : 'Comparison'}: {source.filename} · SHA-256 <code>{source.sha256}</code></p>{action(`Download original ${source === run.reference_source ? 'baseline' : 'comparison'}`, () => download(`/sources/${source.id}/original`, source.filename))}</div>)}
      <h3>Dataset settings and provenance</h3><Json value={{ mapping: run.mapping, validation: run.validation, reference_validation: run.reference_validation, authority: run.response?.identity }} />
      <details className="mapping-provenance"><summary>Automatic paired exclusions</summary><Json value={run.evaluation?.preview?.exclusions || []} /></details>
      <details className="classification-provenance"><summary>Evaluation provenance</summary><Json value={run.evaluation?.preview} /></details>
      <h3>Human review</h3><Json value={review || { evidence_reviewed: false }} />
      {action('Download evidence JSON', () => download(`/runs/${run.id}/evidence`, `neraium-evidence-${run.id}.json`))}
      <RawEvidence key={run.id} run={run} />
    </details>}


    </main><aside><details className="history"><summary>History</summary><label>Select evaluation<select value={operatorItems.some(item => item.id === evaluation?.id) ? evaluation.id : ''} onChange={e => e.target.value && act('Loading evaluation', () => select(e.target.value))}><option value="">Choose…</option>{operatorItems.map(item => <option key={item.id} value={item.id}>{title(item)}</option>)}</select></label><button onClick={() => { setAutoPrepare(false); setPreparedKey(''); setEvaluation(null); setMapping({ signals: [], context: '' }); setTimeIssues({}); setTimes({}); setError(''); clearResult(); }}>New Evaluation</button>
    {evaluation && <><h3>{title(evaluation)}</h3>{[evaluation.facility, evaluation.scope].filter(Boolean).map((s, i) => <p key={i}>{s}</p>)}<h3>Preserved runs</h3>{evaluation.runs?.map(r => <div key={r.id}>{action(`${r.status} · ${r.created_at.slice(0, 19)}`, async () => { const saved = await get(`/runs/${r.id}`); setRun(saved); setReview(saved.reviews?.[0] || null); })}</div>)}</>}
    </details></aside></div></fieldset>
  </div>;
}
