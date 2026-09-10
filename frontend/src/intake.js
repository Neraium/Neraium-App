// Explicit terminal tokens only. C matches the authority catalog's Celsius spelling;
// pH uses the paired contract's dimensionless representation. No value conversion.
const suffixUnits = { mgd: 'MGD', ft: 'ft', c: 'C', mgl: 'mg/L', scfm: 'scfm',
  kw: 'kW', kwh: 'kWh', ntu: 'NTU', in: 'in', ph: 'dimensionless' };
export function suffixUnit(column) {
  const match = column.match(/^.+_([a-z]+)$/i);
  return match && match[0] === column && Object.hasOwn(suffixUnits, match[1].toLowerCase()) ? suffixUnits[match[1].toLowerCase()] : '';
}
// Only copy supplied identities/units. Never infer units from a signal meaning.
export function suggestedMapping(item) {
  return item.mapping || { context: '', start: '', end: '', pair_confirmed: false,
    signals: (item.validation?.signals || []).map(s => {
      const match = s.column.match(/^(.+?)\s*\[([^\]]+)\]\s*$/);
      const nonNumeric = [s, ...(item.reference_validation?.signals || []).filter(q => q.column === s.column)].some(q => q.numeric_count === 0);
      const excluded = nonNumeric || /(?:^|[^a-z])(id|identifier|label|failure|fault|outcome|rul)(?:$|[^a-z])/i.test(s.column);
      return { column: s.column, include: !excluded, meaning: match ? match[1].trim() : s.column.trim(),
        unit: match ? (suffixUnit(match[1].trim()) && suffixUnit(match[1].trim()) !== match[2].trim() ? '' : match[2].trim()) : suffixUnit(s.column),
        reason: nonNumeric ? 'No numeric observations in one or both files; excluded from analysis.' : excluded ? 'Identifier or outcome label excluded from analysis.' : '' };
    }) };
}
export function mappingIssues(mapping, item) {
  const qualities = [...(item.validation?.signals || []), ...(item.reference_validation?.signals || [])];
  return mapping.signals.map((s, index) => {
    const problems = [];
    if (s.include) {
      if (!s.meaning.trim() || s.meaning.trim() === 'timestamp' || mapping.signals.some((other, j) => j !== index && other.include && other.meaning.trim() === s.meaning.trim())) problems.push('Supply a unique signal meaning.');
      if (item.mode === 'paired' && !s.unit.trim()) problems.push('Supply the matching unit used in both files.');
      if (qualities.some(q => q.column === s.column && q.invalid_count)) problems.push('Invalid numeric cells: exclude this signal or replace the file.');
    } else if (!s.reason.trim()) problems.push('Supply an exclusion reason.');
    return { index, problems };
  }).filter(s => s.problems.length);
}
// Reviewed against the pinned supplied-reference contract; unknown output fails closed.
const classificationKeys = new Set(['source_column', 'original_header', 'normalized_name', 'display_name',
  'engineering_units', 'inferred_telemetry_type', 'source_column_index', 'telemetry_category',
  'category', 'structural_class', 'structural_class_key', 'analysis_role', 'canonical_role',
  'telemetry_classification', 'is_primary_anomaly_candidate', 'operator_primary_eligible',
  'is_context_driver', 'is_state_signal', 'is_ignored', 'requires_derived_rate', 'reason', 'semantic_role']);
const canonical = value => JSON.stringify(value, (_, v) => v && typeof v === 'object' && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map(k => [k, v[k]])) : v);
const contextClasses = { weather_environment: 'Weather / Environmental',
  scheduled_load_context: 'Context / Demand Driver', setpoint: 'Setpoint' };
function resolvedClassification(c, nested = false) {
  if (!c || Object.keys(c).some(k => !classificationKeys.has(k))) return false;
  const category = nested ? c.category : c.telemetry_category;
  const context = Object.hasOwn(contextClasses, category);
  const structuralClass = context ? contextClasses[category] : 'Equipment Process Variable';
  if ((!context && category !== 'equipment_process') ||
      c.analysis_role !== (context ? 'supporting_context' : 'primary_signal') ||
      c.operator_primary_eligible !== !context || c.is_context_driver !== context ||
      ['is_ignored', 'is_state_signal', 'requires_derived_rate'].some(k => c[k] !== false)) return false;
  if ((context ? c.is_primary_anomaly_candidate !== false : c.is_primary_anomaly_candidate === false) ||
      ['category', 'structural_class_key'].some(k => k in c && c[k] !== category) ||
      ['structural_class', 'inferred_telemetry_type'].some(k => k in c && c[k] !== structuralClass)) return false;
  // Null semantic roles remain null. No interpretation of signal names or chemistry.
  if (/uncertain|ambiguous|conflict|unsupported|(?:human|manual|operator) review|review required|decision required|requires? (?:human |manual |operator )?(?:review|decision)|needs? (?:review|decision)/i.test(c.reason || '')) return false;
  if (c.telemetry_classification) {
    if (!resolvedClassification(c.telemetry_classification, true)) return false;
    if (Object.keys(c.telemetry_classification).some(k => k in c && canonical(c[k]) !== canonical(c.telemetry_classification[k]))) return false;
  }
  return true;
}
export function classificationIssues(preview, mapping) {
  const catalog = preview.catalog || {};
  const comp = catalog.comparison || catalog;
  const paired = mapping.pair_confirmed === true || !!catalog.reference;
  const supportedContract = preview.identity?.commit === 'b790479f0abcb90aa71f7677d10aa542222b55c8' &&
    preview.identity?.adapter_contract === 'neraium-workbench-authority.v1';
  return mapping.signals.filter(s => s.include).flatMap(s => {
    const c = comp[s.meaning.trim()], r = catalog.reference?.[s.meaning.trim()];
    const resolved = supportedContract && resolvedClassification(c) &&
      (!paired || (resolvedClassification(r) && canonical(r) === canonical(c)));
    return resolved ? [] : [{ column: s.column, comparison: c, reference: r,
      reason: 'Authority classification needs a decision: eligibility, treatment, or agreement is unresolved.' }];
  });
}
