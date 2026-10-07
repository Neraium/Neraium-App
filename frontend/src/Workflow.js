export default function Workflow({ hasData, valid, ready, successful, evaluating, validating }) {
  const current = successful ? 3 : evaluating || ready ? 2 : hasData || validating ? 1 : 0;
  const done = [hasData, valid, successful, false];
  return <nav className="workflow" aria-label="Evaluation workflow"><ol>{['Data', 'Validate', 'Evaluate', 'Findings'].map((label, i) =>
    <li key={label} aria-current={i === current ? 'step' : undefined} className={i === current ? 'current' : done[i] ? 'done' : ''}>
      <span className="step-number" aria-hidden="true">{done[i] && i !== current ? '✓' : `0${i + 1}`}</span><span>{label}</span><span className="sr-only">{i === current ? ' · Current step' : done[i] ? ' · Complete' : ' · Pending'}</span>
    </li>)}</ol></nav>;
}
