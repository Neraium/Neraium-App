import { Cpu, Activity, Pause, Play, Gauge, FlaskConical, ScrollText, Grid3x3 } from "lucide-react";

export default function Header({
  view, setView, playback, onStart, onStop, onSpeedChange, validation,
}) {
  const running = playback?.running;
  return (
    <header data-testid="app-header" className="fixed top-0 inset-x-0 z-40 bg-[#050505]/95 backdrop-blur border-b border-zinc-900">
      {/* Brand bar */}
      <div className="h-12 px-5 flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <Cpu className="w-4 h-4 text-zinc-400" strokeWidth={1.5} />
          <span className="font-mono text-sm font-semibold tracking-tight text-zinc-100">NERAIUM</span>
          <span className="font-mono text-[10px] text-zinc-500 tracking-[0.2em]">SII PLATFORM</span>
        </div>

        <div className="h-3 w-px bg-zinc-800" />

        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 ${running ? "text-emerald-400" : "text-zinc-500"}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${running ? "bg-emerald-400 animate-pulse-soft" : "bg-zinc-600"}`} />
            <span data-testid="pb-status-text" className="font-mono text-[10px] tracking-wider uppercase">
              {running ? `INTELLIGIZING · ${playback.system_count} systems` : "IDLE"}
            </span>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Speed selector */}
          <div className="flex border border-zinc-800 rounded-sm overflow-hidden" title="Playback speed">
            {["slow", "normal", "fast"].map(s => (
              <button key={s} data-testid={`speed-${s}-btn`} onClick={() => onSpeedChange(s)}
                title={`Set playback to ${s}`} aria-label={`Set playback speed to ${s}`}
                className={`px-2 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  playback?.speed === s ? "bg-zinc-200 text-zinc-900" : "bg-transparent text-zinc-500 hover:text-zinc-200 hover:bg-zinc-900"}`}>
                {s[0]}
              </button>
            ))}
          </div>

          {!running ? (
            <button data-testid="start-btn" onClick={onStart}
              className="flex items-center gap-1.5 bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors">
              <Play className="w-3 h-3" /><span>START</span>
            </button>
          ) : (
            <button data-testid="stop-btn" onClick={onStop}
              className="flex items-center gap-1.5 bg-red-500/15 text-red-300 border border-red-500/40 hover:bg-red-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors">
              <Pause className="w-3 h-3" /><span>STOP</span>
            </button>
          )}
        </div>
      </div>

      {/* View bar */}
      <div className="h-9 px-5 border-t border-zinc-900 flex items-stretch">
        <ViewTab id="grid"      icon={Grid3x3}       label="Decisions"   active={view === "grid"} onClick={() => setView("grid")} />
        <ViewTab id="audit"     icon={ScrollText}    label="Audit Trail" active={view === "audit"} onClick={() => setView("audit")} />
        <ViewTab id="validation" icon={FlaskConical} label="Validation Mode (FD004)" active={view === "validation"} onClick={() => setView("validation")} testid="view-validation" />
        <div className="ml-auto flex items-center gap-2 text-zinc-600">
          <Gauge className="w-3.5 h-3.5" />
          <span className="font-mono text-[10px] uppercase tracking-wider">SII engine canonical</span>
        </div>
      </div>
    </header>
  );
}

function ViewTab({ id, icon: Icon, label, active, onClick, testid }) {
  return (
    <button data-testid={testid || `view-${id}`} onClick={onClick}
      className={`flex items-center gap-2 px-4 font-mono text-[11px] uppercase tracking-[0.18em] border-b-2 transition-colors ${
        active ? "text-zinc-100 border-zinc-100" : "text-zinc-500 border-transparent hover:text-zinc-300 hover:border-zinc-700"}`}>
      <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
      <span>{label}</span>
    </button>
  );
}
