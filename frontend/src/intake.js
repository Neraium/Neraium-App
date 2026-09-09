// Only copy supplied identities/units. Never infer units from a signal meaning.
export function suggestedMapping(item) {
  return item.mapping || { context: '', start: '', end: '', pair_confirmed: false,
    signals: (item.validation?.signals || []).map(s => {
      const match = s.column.match(/^(.+?)\s*\[([^\]]+)\]\s*$/);
      const excluded = /(?:^|[^a-z])(id|identifier|label|failure|fault|outcome|rul)(?:$|[^a-z])/i.test(s.column);
      return { column: s.column, include: !excluded, meaning: match ? match[1].trim() : s.column.trim(),
        unit: match ? match[2].trim() : '', reason: excluded ? 'Identifier or outcome label excluded from analysis.' : '' };
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
export function classificationIssues(preview, mapping) {
  const comp = preview.catalog.comparison || preview.catalog;
  return mapping.signals.filter(s => s.include).flatMap(s => {
    const c = comp[s.meaning.trim()], r = preview.catalog.reference?.[s.meaning.trim()];
    const category = c?.telemetry_category;
    return !category || /unknown|unclassified|other|generic/i.test(category) || (preview.catalog.reference && r?.telemetry_category !== category)
      ? [{ column: s.column, comparison: c, reference: r }] : [];
  });
}
