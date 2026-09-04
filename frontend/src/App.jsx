import React, { useCallback, useEffect, useState } from "react";
import * as api from "./lib/api.js";
import { compactInr, inr, pct } from "./lib/format.js";
import MetricCard from "./components/MetricCard.jsx";
import EventTable from "./components/EventTable.jsx";
import GuardrailsCard from "./components/GuardrailsCard.jsx";
import BreakdownCard from "./components/BreakdownCard.jsx";
import ExceptionsCard from "./components/ExceptionsCard.jsx";
import EventDrawer from "./components/EventDrawer.jsx";
import LivePanel from "./components/LivePanel.jsx";

export default function App() {
  const [config, setConfig] = useState(null);
  const [records, setRecords] = useState([]);
  const [guardrails, setGuardrails] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ processed: 0, total: 0, recovered_paise: 0, recovered_count: 0 });
  const [liveStatus, setLiveStatus] = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [ticker, setTicker] = useState("");

  const loadAll = useCallback(async () => {
    const [cfg, recs, g] = await Promise.all([api.getConfig(), api.getEvents(), api.getGuardrails()]);
    setConfig(cfg);
    setRecords(recs);
    setGuardrails(g);
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const atRiskPaise = records.reduce((s, r) => s + r.event.amount_paise, 0);
  const recoveredPaise = metrics ? metrics.recovered_paise : progress.recovered_paise;
  const recoveredCount = metrics ? metrics.recovered_count : progress.recovered_count;

  const run = () => {
    if (running) return;
    setRunning(true);
    setMetrics(null);
    setLiveStatus({});
    setSelectedId(null);
    setProgress({ processed: 0, total: records.length, recovered_paise: 0, recovered_count: 0 });
    api.runStream({
      onEvent: (d) => {
        setLiveStatus((prev) => ({ ...prev, [d.event_id]: d.status }));
        setProgress({
          processed: d.processed, total: d.total,
          recovered_paise: d.recovered_paise_so_far, recovered_count: d.recovered_count_so_far,
        });
        setTicker(`#${d.processed}/${d.total}  ·  ${d.status.replace("_", " ").toUpperCase()}  ·  ${(d.root_cause || "").replace(/_/g, " ")}`);
      },
      onDone: async (summary) => {
        setMetrics(summary.metrics);
        setRecords(await api.getEvents());
        setRunning(false);
        setTicker("");
      },
      onError: () => setRunning(false),
    });
  };

  const saveGuardrails = async (g) => {
    setGuardrails(g);
    try { await api.putGuardrails(g); } catch { /* ignore */ }
  };

  const selected = records.find((r) => r.event.id === selectedId) || null;
  const pctDone = progress.total ? (progress.processed / progress.total) * 100 : 0;

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <div className="brand__mark">₹⟳</div>
          <div>
            <h1 className="brand__title">SALUS</h1>
            <div className="brand__sub">Autonomous Revenue Recovery · detect → diagnose → decide → recover → audit</div>
          </div>
        </div>
        <div className="header__right">
          {config && (
            <span className={"badge " + (config.razorpay_live ? "badge--live" : "badge--sim")}>
              {config.razorpay_live ? "Razorpay LIVE" : "Simulate"}
            </span>
          )}
          {config && <span className="badge">seed {config.seed}</span>}
          <button className="btn btn--go" onClick={run} disabled={running}>
            {running ? "Recovering…" : "▶ Run Recovery"}
          </button>
        </div>
      </header>

      <div className="hero">
        <MetricCard label="At Risk" accent="var(--pink)"
          value={compactInr(metrics ? metrics.at_risk_paise : atRiskPaise)}
          sub={`${records.length} events in batch`} />
        <MetricCard label="Recovered" accent="var(--green)" highlight pop={running}
          value={compactInr(recoveredPaise)}
          sub={`${recoveredCount} payments won back`} />
        <MetricCard label="Recovery Rate" accent="var(--cyan)"
          value={metrics ? pct(metrics.recovery_rate) : "—"}
          sub={metrics ? "of auto-addressable ₹" : "run to measure"} />
        <MetricCard label="Escalated → Human" accent="var(--orange)"
          value={metrics ? compactInr(metrics.escalated_paise) : "—"}
          sub={metrics ? `${metrics.escalated_count} routed safely` : "bounded by policy"} />
        <MetricCard label="Cost of Recovery" accent="var(--yellow)"
          value={metrics ? inr(metrics.cost_paise, 2) : "—"}
          sub={metrics ? `net ${compactInr(metrics.net_recovered_paise)}` : "near-zero marginal"} />
      </div>

      <div className="runbar">
        {running ? (
          <>
            <div className="progress">
              <div className="progress__fill animate" style={{ width: `${pctDone}%` }} />
              <div className="progress__label">{progress.processed} / {progress.total}</div>
            </div>
            <div className="ticker blink">{ticker}</div>
          </>
        ) : metrics ? (
          <div className="ticker">
            ✅ One pass complete — recovered <b>{compactInr(metrics.recovered_paise)}</b> across{" "}
            {metrics.recovered_count} payments
            {metrics.promise_count > 0 && <> · 🤝 {compactInr(metrics.promise_paise)} promise-to-pay ({metrics.promise_count})</>}
            {" "}· {metrics.actions_taken} actions · {metrics.actions_deferred} deferred ·{" "}
            {metrics.actions_blocked} blocked by guardrails · avg {metrics.avg_time_to_recover_hours}h to recover
          </div>
        ) : (
          <div className="ticker">Press <b>Run Recovery</b> to watch the agent work the batch, action by action.</div>
        )}
      </div>

      <div className="layout">
        <EventTable records={records} liveStatus={liveStatus} selectedId={selectedId} onSelect={setSelectedId} />
        <div className="stack">
          <LivePanel onChange={async () => setRecords(await api.getEvents())} />
          {guardrails && <GuardrailsCard guardrails={guardrails} onSave={saveGuardrails} disabled={running} />}
          <BreakdownCard byRootCause={metrics?.by_root_cause} />
          <ExceptionsCard records={records} />
        </div>
      </div>

      {selected && <EventDrawer record={selected} onClose={() => setSelectedId(null)} />}
    </div>
  );
}
