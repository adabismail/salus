import React, { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api.js";
import { compactInr, inr } from "../lib/format.js";

export default function LivePanel({ onChange }) {
  const [live, setLive] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try { setLive(await api.liveState()); } catch { setLive({ configured: false }); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (live && !live.configured) return null; // no keys → hide the panel entirely

  const createLinks = async () => {
    setBusy("create");
    try { await api.liveRecover(8); await load(); onChange && onChange(); } finally { setBusy(""); }
  };
  const sync = async () => {
    setBusy("sync");
    try { await api.liveSync(); await load(); onChange && onChange(); } finally { setBusy(""); }
  };

  return (
    <div className="card" style={{ borderColor: "#0b5", boxShadow: "6px 6px 0 #0b5" }}>
      <div className="panel-title">
        <span>🔗 Live · Razorpay Test</span>
        <span className="count">{live?.key_id || ""}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
        <div className="card--flat" style={{ border: "2px solid var(--ink)", padding: 8 }}>
          <div className="metric__label upper">Links created</div>
          <div className="mono" style={{ fontWeight: 800, fontSize: 20 }}>
            {live?.count ?? 0} · {compactInr(live?.created_paise)}
          </div>
        </div>
        <div className="card--flat" style={{ border: "2px solid var(--ink)", padding: 8, background: "#e9fbf1" }}>
          <div className="metric__label upper">Recovered (real)</div>
          <div className="mono" style={{ fontWeight: 800, fontSize: 20 }}>
            {live?.paid ?? 0} · {compactInr(live?.paid_paise)}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <button className="btn btn--ghost" style={{ boxShadow: "3px 3px 0 var(--ink)", padding: "8px 12px", fontSize: 12 }}
          disabled={busy} onClick={createLinks}>
          {busy === "create" ? "Creating…" : "＋ Create real links"}
        </button>
        <button className="btn btn--go" style={{ boxShadow: "3px 3px 0 var(--ink)", padding: "8px 12px", fontSize: 12 }}
          disabled={busy} onClick={sync}>
          {busy === "sync" ? "Syncing…" : "⟳ Sync from Razorpay"}
        </button>
      </div>

      <div className="exc" style={{ maxHeight: 220 }}>
        {(live?.links || []).map((l) => (
          <div key={l.link_id} className="exc__item" style={{ background: l.status === "paid" ? "#e9fbf1" : "#fff" }}>
            <div className="exc__top">
              <span>{l.customer}</span>
              <span className="amt">{inr(l.amount_paise)}</span>
            </div>
            <div className="exc__why" style={{ display: "flex", justifyContent: "space-between" }}>
              <a href={l.short_url} target="_blank" rel="noreferrer" className="mono">{l.short_url}</a>
              <span className={"tag"} style={{ background: l.status === "paid" ? "var(--green)" : "#e7e2d3" }}>
                {l.status}
              </span>
            </div>
          </div>
        ))}
        {(!live?.links || live.links.length === 0) && (
          <div className="empty">No live links yet — click “Create real links”.</div>
        )}
      </div>
      <div className="metric__sub" style={{ marginTop: 8 }}>
        Real Razorpay test-mode links. Pay one (UPI <b>success@razorpay</b> or test card
        <b> 4111 1111 1111 1111</b>) then hit Sync — “Recovered (real)” reflects money Razorpay
        actually confirmed. No real money moves.
      </div>
    </div>
  );
}
