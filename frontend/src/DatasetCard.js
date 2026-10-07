import { useRef, useState } from 'react';
import { Check, FileText, UploadCloud } from 'lucide-react';

export const formatBytes = value => {
  if (!Number.isFinite(value)) return null;
  if (value < 1024) return `${value} B`;
  const unit = value < 1024 * 1024 ? 'KiB' : 'MiB';
  return `${(value / (unit === 'KiB' ? 1024 : 1024 * 1024)).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
};
export function transferProgress(event) {
  const loaded = Math.max(0, event.loaded || 0);
  const total = event.lengthComputable && event.total > 0 ? event.total : null;
  return { loaded, total, percent: total === null ? null : Math.min(100, Math.floor(loaded / total * 100)) };
}
export function datasetState({ transfer, source, quality, timeIssue, evaluating, complete }) {
  if (transfer?.phase === 'preparing') return 'Preparing upload';
  if (transfer?.phase === 'uploading') return 'Uploading';
  if (transfer?.phase === 'failed') return 'Failed';
  if (transfer?.phase === 'validating') return 'Validating';
  if (transfer?.phase === 'uploaded') return 'Uploaded';
  if (!source) return transfer?.phase === 'uploaded' ? 'Uploaded' : 'No dataset';
  if (complete) return 'Complete';
  if (evaluating) return 'Evaluating';
  if (timeIssue) return 'Needs review';
  if (quality && !quality.eligible_timestamps) return 'Validation failed';
  if (quality?.eligible_timestamps) return 'Ready';
  return 'Uploaded';
}

export default function DatasetCard({ role, source, quality, transfer, timeIssue, evaluating, complete, disabled, onSelect, children }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const baseline = role === 'reference';
  const name = baseline ? 'Baseline dataset' : 'Comparison dataset';
  const state = datasetState({ transfer, source, quality, timeIssue, evaluating, complete });
  const uploading = state === 'Uploading';
  const metadataPending = ['preparing', 'uploaded'].includes(transfer?.phase);
  const attempted = transfer && ['preparing', 'uploading', 'failed', 'uploaded', 'validating'].includes(transfer.phase);
  const filename = attempted ? transfer.filename || source?.filename : source?.filename;
  const bytes = attempted ? transfer.size ?? source?.bytes : source?.bytes;
  const select = file => { if (file && !disabled) onSelect(file, role); };
  return <section className={`panel dataset-card ${dragging ? 'is-dragging' : ''}`} aria-label={baseline ? 'Baseline period' : 'Comparison period'} data-dataset={role}
    onDragOver={event => { event.preventDefault(); if (!disabled) setDragging(true); }}
    onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
    onDrop={event => { event.preventDefault(); setDragging(false); select(event.dataTransfer.files?.[0]); }}>
    <div className="dataset-heading"><div><span className="eyebrow">{baseline ? 'BASELINE PERIOD' : 'COMPARISON PERIOD'}</span><h2>{baseline ? 'Reference operating history' : 'Period evaluated against the baseline'}</h2></div><span className={`state-badge ${['Ready', 'Complete'].includes(state) ? 'state-ready' : /failed|Failed|review/.test(state) ? 'state-attention' : ''}`}><span className="state-dot" />{state}</span></div>
    <div className={`file-picker ${filename ? 'has-file' : ''}`}>
      <span className="file-icon" aria-hidden="true">{filename ? <FileText size={20} /> : <UploadCloud size={22} />}</span>
      <div className="file-description">{filename ? <><strong>{filename}</strong><span>{formatBytes(bytes)}{transfer?.phase === 'failed' ? transfer.failureStage === 'validation' ? ' · Validation request failed' : ' · Upload attempt failed' : source && !uploading && transfer?.phase !== 'preparing' ? ' · Stored dataset' : ''}</span></> : <><strong>Select operating history</strong><span>Drop a CSV, TSV or JSON file here</span></>}</div>
      <button type="button" className="secondary file-select" disabled={disabled} onClick={() => input.current.click()}>{filename ? 'Replace file' : 'Select file'}</button>
      <input ref={input} className="native-file-input" aria-label={name} type="file" accept=".csv,.tsv,.json" disabled={disabled}
        onChange={event => { const file = event.target.files[0]; event.target.value = ''; select(file); }} />
    </div>
    {uploading && <div className="upload-progress" aria-live="polite">
      <div className="progress-label"><span>Uploading</span><strong>{transfer.percent === null ? 'Total unavailable' : `${transfer.percent}%`}</strong></div>
      <progress aria-label={`${name} upload progress`} max="100" value={transfer.percent === null ? undefined : transfer.percent} />
      <div className="progress-bytes">{formatBytes(transfer.loaded)} / {transfer.total === null ? 'total unavailable' : formatBytes(transfer.total)}<span>{transfer.loaded.toLocaleString()} / {transfer.total === null ? 'unknown' : transfer.total.toLocaleString()} bytes</span></div>
      {transfer.percent === 100 && <p className="transfer-note">Transfer sent. Waiting for the server to accept the upload.</p>}
    </div>}
    {transfer?.phase === 'failed' && <p className="dataset-error">{transfer.error}{source && transfer.failureStage !== 'validation' && <span> The previously stored dataset is retained below.</span>}</p>}
    {source && !uploading && !metadataPending && <>
      {transfer?.phase === 'failed' && <p className="retained-source">Stored: {source.filename}</p>}
      <dl className="dataset-facts">
        <div><dt>Validation</dt><dd>{timeIssue ? 'Timestamp review required' : quality ? quality.eligible_timestamps ? <><Check size={13} aria-hidden="true" /> Validated</> : 'Failed' : state === 'Validating' ? 'In progress' : 'Not yet validated'}</dd></div>
        {Number.isFinite(quality?.row_count) && <div><dt>Observations</dt><dd>{quality.row_count.toLocaleString()}</dd></div>}
        {quality?.signals && <div><dt>Signals</dt><dd>{quality.signals.length}</dd></div>}
        {!quality && source.columns && <div><dt>Columns</dt><dd>{source.columns.length}</dd></div>}
        {quality?.start && <div className="dataset-range"><dt>Timestamp range</dt><dd><span>{quality.start}</span>{quality.end && <span className="range-end">to {quality.end}</span>}</dd></div>}
      </dl>
    </>}
    {children}
  </section>;
}
