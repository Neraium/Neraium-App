/**
 * SettingsView — customer accounts + telemetry-ingest plug-in.
 *
 * Lets an operator:
 *   - register a new customer (auto-mints an API key)
 *   - copy their personalised ingest URL + cURL snippet
 *   - see system count + frames ingested
 *   - revoke a customer (deletes the API key, stops ingest)
 *
 * The ingest URL the customer uses is `${REACT_APP_BACKEND_URL}/api/ingest/<api_key>`.
 */
import { useEffect, useState, useCallback } from "react";
import { Customers, ingestUrlFor } from "@/api";
import {
  Settings as SettingsIcon, KeyRound, Plus, Copy, Check, Trash2, Link as LinkIcon, RefreshCw,
} from "lucide-react";

export default function SettingsView() {
  const [items, setItems] = useState([]);
  const [name, setName]     = useState("");
  const [email, setEmail]   = useState("");
  const [sourceUrl, setSrc] = useState("");
  const [notes, setNotes]   = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const r = await Customers.list();
      setItems(r.items || []);
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true); setError(null);
    try {
      await Customers.create({ name, email, source_url: sourceUrl, notes });
      setName(""); setEmail(""); setSrc(""); setNotes("");
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally { setCreating(false); }
  };

  const remove = async (id) => {
    await Customers.remove(id);
    refresh();
  };

  return (
    <div data-testid="settings-view" className="space-y-5 animate-fade-in">
      <header className="flex items-center gap-2 px-1">
        <SettingsIcon className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
        <h2 className="font-mono text-[12px] tracking-[0.25em] uppercase text-zinc-300">
          Settings · customer accounts
        </h2>
        <button data-testid="settings-refresh" onClick={refresh}
          className="ml-auto text-zinc-500 hover:text-zinc-200 px-1">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </header>

      {/* ============= Create customer ============= */}
      <section data-testid="new-customer-form" className="grain border border-zinc-900 bg-[#0A0A0A]">
        <div className="px-5 py-3 border-b border-zinc-900 flex items-center gap-2">
          <Plus className="w-3.5 h-3.5 text-emerald-400" strokeWidth={1.5} />
          <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-zinc-400">
            Onboard a new customer
          </span>
        </div>
        <form onSubmit={submit} className="px-5 py-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Customer name" required>
            <input data-testid="new-customer-name" value={name} onChange={e => setName(e.target.value)}
              placeholder="Acme Industrial" className={INPUT_CLS} />
          </Field>
          <Field label="Contact email">
            <input data-testid="new-customer-email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="ops@acme.com" type="email" className={INPUT_CLS} />
          </Field>
          <Field label="Source telemetry URL (optional)">
            <input data-testid="new-customer-source" value={sourceUrl} onChange={e => setSrc(e.target.value)}
              placeholder="https://acme.com/telemetry" className={INPUT_CLS} />
          </Field>
          <Field label="Notes">
            <input data-testid="new-customer-notes" value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="primary stack · 6 systems" className={INPUT_CLS} />
          </Field>
          <div className="md:col-span-2 flex items-center gap-3 pt-1">
            <button data-testid="create-customer-btn" type="submit" disabled={creating || !name.trim()}
              className="inline-flex items-center gap-2 bg-emerald-500/15 border border-emerald-500/40 text-emerald-300
                         disabled:opacity-50 hover:bg-emerald-500/25 px-4 py-2 font-mono text-[11px] tracking-wider uppercase transition-colors">
              <KeyRound className="w-3.5 h-3.5" />
              {creating ? "Creating…" : "Create customer + mint API key"}
            </button>
            {error && <span data-testid="settings-error" className="font-mono text-[11px] text-red-400">{error}</span>}
          </div>
        </form>
      </section>

      {/* ============= Customer list ============= */}
      {!items.length ? (
        <div data-testid="customers-empty" className="border border-zinc-900 bg-[#0A0A0A] p-10 text-center">
          <span className="font-mono text-xs text-zinc-500">No customers onboarded yet.</span>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(c => <CustomerCard key={c.id} customer={c} onDelete={() => remove(c.id)} />)}
        </div>
      )}
    </div>
  );
}

const INPUT_CLS = "w-full bg-[#0E0E0E] border border-zinc-800 focus:border-zinc-600 focus:outline-none px-3 py-2 font-mono text-[12px] text-zinc-100 placeholder-zinc-700";

function Field({ label, required, children }) {
  return (
    <label className="block">
      <span className="font-mono text-[10px] tracking-[0.22em] uppercase text-zinc-500 block mb-1">
        {label}{required && <span className="text-emerald-400 ml-1">*</span>}
      </span>
      {children}
    </label>
  );
}

function CustomerCard({ customer, onDelete }) {
  const ingestUrl = ingestUrlFor(customer.api_key);
  const curlSnippet =
`curl -X POST "${ingestUrl}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "system_id": "<your-system-id>",
    "template":  "industrial",
    "sensor_values": {
      "pressure_kpa":   280.0,
      "temperature_c":   72.0,
      "vibration_g":      0.35,
      "rpm":           1750.0,
      "torque_nm":       48.0,
      "flow_rate_lpm":   22.0
    }
  }'`;
  return (
    <article data-testid={`customer-${customer.id}`}
      className="grain border border-zinc-900 bg-[#0A0A0A]"
      style={{ borderLeftWidth: 3, borderLeftColor: "#10B981" }}>
      <div className="px-5 py-4 flex items-start gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            <h3 className="font-mono text-base text-zinc-100 font-semibold">{customer.name}</h3>
            {customer.email && <span className="font-mono text-[11px] text-zinc-500">{customer.email}</span>}
          </div>
          <div className="flex items-center gap-3 mt-1 font-mono text-[10px] text-zinc-600 uppercase tracking-wider">
            <span>created {new Date(customer.created_at).toLocaleDateString()}</span>
            <span className="text-zinc-700">·</span>
            <span>{customer.systems_registered ?? 0} systems</span>
            <span className="text-zinc-700">·</span>
            <span>{customer.frames_ingested ?? 0} frames ingested</span>
          </div>
          {customer.source_url && (
            <div className="flex items-center gap-1.5 mt-1 font-mono text-[11px] text-zinc-500">
              <LinkIcon className="w-3 h-3" /> {customer.source_url}
            </div>
          )}
          {customer.notes && (
            <div className="font-mono text-[11px] text-zinc-400 mt-1">{customer.notes}</div>
          )}
        </div>
        <button data-testid={`customer-delete-${customer.id}`} onClick={onDelete}
          className="text-zinc-600 hover:text-red-400 p-1 transition-colors" title="Revoke API key + delete">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* API key + ingest URL */}
      <div className="border-t border-zinc-900 px-5 py-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <CopyRow testid={`copy-key-${customer.id}`}
          label="API key (keep secret)"
          value={customer.api_key}
          mono />
        <CopyRow testid={`copy-url-${customer.id}`}
          label="Ingest URL"
          value={ingestUrl}
          mono />
      </div>

      {/* cURL snippet */}
      <div className="border-t border-zinc-900">
        <div className="px-5 py-2 flex items-center gap-2">
          <span className="font-mono text-[10px] tracking-[0.22em] uppercase text-zinc-500">
            Plug in — push your first frame
          </span>
          <CopyButton testid={`copy-curl-${customer.id}`} value={curlSnippet} compact />
        </div>
        <pre data-testid={`curl-snippet-${customer.id}`}
          className="px-5 pb-4 overflow-x-auto font-mono text-[11px] leading-relaxed text-zinc-300 whitespace-pre">
{curlSnippet}
        </pre>
      </div>
    </article>
  );
}

function CopyRow({ label, value, testid, mono }) {
  return (
    <div className="space-y-1">
      <div className="font-mono text-[10px] tracking-[0.22em] uppercase text-zinc-500">{label}</div>
      <div className="flex items-center gap-2">
        <code className={`flex-1 min-w-0 truncate bg-[#0E0E0E] border border-zinc-800 px-2.5 py-1.5 ${mono ? "font-mono" : ""} text-[12px] text-zinc-100`}>
          {value}
        </code>
        <CopyButton testid={testid} value={value} />
      </div>
    </div>
  );
}

function CopyButton({ value, testid, compact }) {
  const [done, setDone] = useState(false);
  const click = async (e) => {
    e?.stopPropagation();
    try { await navigator.clipboard.writeText(value); setDone(true); setTimeout(() => setDone(false), 1500); }
    catch (_) {}
  };
  return (
    <button data-testid={testid} type="button" onClick={click}
      className={`inline-flex items-center gap-1.5 ${compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1.5 text-[11px]"}
                  border border-zinc-800 hover:border-zinc-700 text-zinc-300 hover:text-zinc-100 transition-colors font-mono`}>
      {done ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
      {done ? "Copied" : "Copy"}
    </button>
  );
}
