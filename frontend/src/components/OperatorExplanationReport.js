import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, GitBranch, Wrench } from "lucide-react";
import { Pronostia } from "@/api";

const ORDER = ["STABLE", "WATCH", "ALERT"];

function parseReport(content = "") {
  const sections = {};
  ORDER.forEach(label => {
    const match = content.match(new RegExp(`## ${label}\\n([\\s\\S]*?)(?=\\n## |$)`));
    if (match) sections[label] = match[1].trim();
  });
  return sections;
}

function linesAfter(section, heading) {
  const match = section.match(new RegExp(`### ${heading}\\n([\\s\\S]*?)(?=\\n### |$)`));
  if (!match) return [];
  return match[1]
    .split("\n")
    .map(line => line.trim())
    .filter(Boolean);
}

function detailValue(section, label) {
  const match = section.match(new RegExp(`- ${label}:\\s*(.*)`));
  return match ? match[1].trim() : "pending";
}

function statusTone(label) {
  if (label === "STABLE") return "border-teal-500/20 text-teal-200";
  if (label === "WATCH") return "border-amber-500/35 text-amber-200";
  return "border-orange-500/40 text-orange-200";
}

function SectionCard({ label, section }) {
  const drivers = linesAfter(section, "Primary Drivers");
  const subsystems = linesAfter(section, "Affected Subsystems");
  const relationships = linesAfter(section, "Relationship Breakdowns");
  const checks = linesAfter(section, "Operator Check");
  const context = linesAfter(section, "Validation Context");
  const cycle = detailValue(section, "Cycle");
  const confidence = detailValue(section, "Confidence");

  return (
    <section className={`border bg-zinc-950/40 ${statusTone(label)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-900 px-5 py-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-zinc-500">Cycle {cycle}</div>
          <h2 className="mt-1 font-mono text-2xl font-semibold tracking-wide text-zinc-100">{label}</h2>
        </div>
        <div className="max-w-xl text-right font-mono text-xs text-zinc-400">{confidence}</div>
      </div>

      <div className="grid gap-5 p-5 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-5">
          <ReportBlock icon={FileText} title="Primary Drivers" items={drivers} />
          <ReportBlock icon={GitBranch} title="Relationship Breakdown" items={relationships} />
        </div>
        <div className="space-y-5">
          <ReportBlock icon={AlertTriangle} title="Affected Subsystem" items={subsystems} />
          <ReportBlock icon={Wrench} title="Operator Check" items={checks} />
          <ReportBlock icon={CheckCircle2} title="Validation Lead Time" items={context} compact />
        </div>
      </div>
    </section>
  );
}

function ReportBlock({ icon: Icon, title, items, compact = false }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
        <Icon className="h-3.5 w-3.5" />
        <span>{title}</span>
      </div>
      <div className={`space-y-2 font-mono ${compact ? "text-[11px]" : "text-xs"} leading-relaxed text-zinc-300`}>
        {items.length ? items.map((item, index) => (
          <p key={`${title}-${index}`} className="border-l border-zinc-800 pl-3">{item.replace(/`/g, "")}</p>
        )) : (
          <p className="border-l border-zinc-800 pl-3 text-zinc-600">None shown.</p>
        )}
      </div>
    </div>
  );
}

export default function OperatorExplanationReport() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Pronostia.operatorReport()
      .then(data => {
        if (!cancelled) setReport(data);
      })
      .catch(err => {
        if (!cancelled) setError(err.message || "Unable to load report.");
      });
    return () => { cancelled = true; };
  }, []);

  const sections = useMemo(() => parseReport(report?.content || ""), [report]);

  if (error) {
    return <div className="border border-red-500/30 bg-red-500/10 p-5 font-mono text-sm text-red-200">{error}</div>;
  }

  if (!report) {
    return <div className="border border-zinc-900 bg-zinc-950/40 p-5 font-mono text-sm text-zinc-500">Loading operator explanation report...</div>;
  }

  if (!report.exists) {
    return (
      <div className="border border-amber-500/30 bg-amber-500/10 p-6 font-mono text-sm text-amber-100">
        <div className="text-lg text-zinc-100">Operator explanation report is not generated yet.</div>
        <div className="mt-3 text-zinc-400">Run this command from the repository root:</div>
        <pre className="mt-3 overflow-auto border border-zinc-800 bg-black/40 p-3 text-amber-200">{report.command}</pre>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="border border-zinc-900 bg-zinc-950/40 px-5 py-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-zinc-500">PRONOSTIA / FEMTO bearing degradation</div>
        <h1 className="mt-2 font-mono text-3xl font-semibold tracking-wide text-zinc-100">Operator Explanation</h1>
        <p className="mt-3 max-w-4xl font-mono text-sm leading-relaxed text-zinc-400">
          Why Neraium's detection matters: raw vibration-derived evidence, structural interpretation,
          validation lead time, and operator decision support in one view.
        </p>
        <p className="mt-3 inline-block border border-amber-500/30 bg-amber-500/10 px-3 py-2 font-mono text-xs text-amber-200">
          Validation context only. This was not used by the engine.
        </p>
      </div>

      <div className="grid grid-cols-3 border border-zinc-900 bg-zinc-950/30">
        {ORDER.map(label => (
          <div key={label} className={`border-r border-zinc-900 px-4 py-3 last:border-r-0 ${statusTone(label)}`}>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">{label}</div>
            <div className="mt-1 font-mono text-sm text-zinc-200">Cycle {detailValue(sections[label] || "", "Cycle")}</div>
          </div>
        ))}
      </div>

      {ORDER.map(label => (
        sections[label]
          ? <SectionCard key={label} label={label} section={sections[label]} />
          : <div key={label} className="border border-zinc-900 p-5 font-mono text-sm text-zinc-500">No {label} sample was emitted.</div>
      ))}
    </div>
  );
}
