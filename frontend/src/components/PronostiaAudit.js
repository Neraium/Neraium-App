import { useEffect, useState, useCallback } from "react";
import { ScrollText, RefreshCw, Trash2 } from "lucide-react";

export default function PronostiaAudit() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAudit = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia/audit`
      );
      if (!res.ok) throw new Error("Failed to load PRONOSTIA audit");
      const json = await res.json();
      setEvents(json.events || []);
      setError(null);
    } catch (e) {
      setError(e.message);
      console.error("Audit fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAudit();
    const interval = setInterval(fetchAudit, 3000);
    return () => clearInterval(interval);
  }, [fetchAudit]);

  const handleClear = async () => {
    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/audit?system_id=__demo_pronostia__`,
        { method: "DELETE" }
      );
      if (res.ok) {
        setEvents([]);
        await fetchAudit();
      }
    } catch (_) {}
  };

  if (loading && events.length === 0) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-zinc-500">Loading audit trail...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-red-500">Error: {error}</p>
      </div>
    );
  }

  return (
    <div data-testid="audit-view" className="border border-zinc-900 bg-[#0A0A0A]">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-900">
        <ScrollText className="w-3.5 h-3.5 text-zinc-500" strokeWidth={1.5} />
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">
          PRONOSTIA Audit Log
        </span>
        <span data-testid="audit-count" className="font-mono text-[10px] text-zinc-600 ml-auto">
          {events.length} events
        </span>
        <button
          data-testid="audit-refresh"
          onClick={fetchAudit}
          className="text-zinc-500 hover:text-zinc-200 px-1"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
        <button
          data-testid="audit-clear"
          onClick={handleClear}
          className="text-zinc-600 hover:text-red-400 px-1"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>

      {!events.length ? (
        <div data-testid="audit-empty" className="px-4 py-12 text-center">
          <span className="font-mono text-xs text-zinc-500">
            No events logged yet. Demo events will appear here.
          </span>
        </div>
      ) : (
        <div className="divide-y divide-zinc-900">
          {events.map((event, idx) => (
            <div
              key={idx}
              data-testid={`audit-row-${idx}`}
              className="px-4 py-3 flex items-start gap-3"
            >
              <div className="flex-1 min-w-0">
                <div
                  data-testid={`audit-headline-${idx}`}
                  className="font-mono text-sm text-zinc-100 leading-snug"
                >
                  {event.message}
                </div>
                <div className="flex items-center gap-2 mt-1 flex-wrap font-mono text-[10px] text-zinc-500">
                  <span className="font-semibold tracking-wider">EVENT</span>
                  <span className="text-zinc-600">cycle {event.cycle}</span>
                  <span className="text-zinc-600 ml-auto">
                    {new Date(event.timestamp * 1000).toLocaleTimeString('en-US', { hour12: false })}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
