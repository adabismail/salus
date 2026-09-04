import React from "react";
import { inr, titleCase } from "../lib/format.js";
import { StatusChip, GateChip, TypeTag } from "./Chips.jsx";

function Intervention({ iv }) {
  return (
    <div className="ivcard">
      <div className="ivcard__top">
        <span className="ivcard__name">
          {titleCase(iv.type)}
          {iv.firmness && iv.firmness !== "gentle" && (
            <span className="tag" style={{
              marginLeft: 6, fontSize: 10,
              background: iv.firmness === "final" ? "var(--red)" : "var(--yellow)",
              color: iv.firmness === "final" ? "#fff" : "inherit",
            }}>{iv.firmness}</span>
          )}
        </span>
        {iv.gate && <GateChip decision={iv.gate.decision} />}
      </div>
      {iv.gate && iv.gate.reasons?.length > 0 && (
        <div className="metric__sub" style={{ marginTop: 6 }}>{iv.gate.reasons.join(" ")}</div>
      )}
      {iv.message && <div className="ivcard__msg">“{iv.message}”</div>}
      <div className="ivcard__meta">
        {iv.channel && iv.channel !== "none" && <span>via {titleCase(iv.channel)}</span>}
        {iv.cost_paise > 0 && <span>cost {inr(iv.cost_paise, 2)}</span>}
        {iv.razorpay_ref && <span className="mono">{iv.razorpay_ref}</span>}
        {iv.executed && iv.succeeded === true && <span className="ok">✓ recovered</span>}
        {iv.executed && iv.succeeded === false && <span className="no">✗ no response</span>}
      </div>
    </div>
  );
}

export default function EventDrawer({ record, onClose }) {
  if (!record) return null;
  const { event: ev, diagnosis: dg, interventions, audit, status, outcome } = record;
  return (
    <div className="drawer__overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer__head">
          <div>
            <h2>{ev.customer.name}</h2>
            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <TypeTag type={ev.type} />
              <StatusChip status={status} />
            </div>
          </div>
          <button className="close-x" onClick={onClose}>✕</button>
        </div>

        <dl className="kv">
          <dt>Amount</dt><dd>{inr(ev.amount_paise)}</dd>
          <dt>Method</dt><dd>{ev.method || "—"}</dd>
          {ev.error_reason && (<><dt>Error</dt><dd>{ev.error_reason}</dd></>)}
          {ev.error_source && (<><dt>Source</dt><dd>{ev.error_source} / {ev.error_step}</dd></>)}
          <dt>Attempts</dt><dd>{ev.attempt_count}</dd>
          <dt>Age</dt><dd>{ev.age_hours}h</dd>
          <dt>Contact</dt><dd>{ev.customer.phone}</dd>
          {ev.customer.opted_out && (<><dt>Opt-out</dt><dd className="no">YES</dd></>)}
          {ev.risk_flag && (<><dt>Fraud flag</dt><dd className="no">RAISED</dd></>)}
        </dl>

        {dg && (
          <>
            <h3>Diagnosis</h3>
            <div className="dg">
              <div className="dg__cause">
                {titleCase(dg.root_cause)}{" "}
                <span className="mono" style={{ fontSize: 13, color: "var(--muted)" }}>
                  {Math.round(dg.confidence * 100)}% conf · {dg.source}
                </span>
              </div>
              <div className="dg__why">{dg.rationale}</div>
              <div className="signals">
                {dg.signals.map((s, i) => (
                  <span className="signal" key={i}>{s}</span>
                ))}
              </div>
            </div>
          </>
        )}

        {outcome?.recovered && (
          <div className="dg" style={{ background: "#e9fbf1" }}>
            <b>✅ Recovered {inr(outcome.recovered_amount_paise)}</b> via{" "}
            {titleCase(outcome.winning_intervention)} — {outcome.note}
          </div>
        )}

        {outcome?.promised && (
          <div className="dg" style={{ background: "#eaf1ff" }}>
            <b>Promise-to-pay secured — {inr(outcome.promise_amount_paise)}</b>
            {outcome.promise_due && <> · due {new Date(outcome.promise_due).toLocaleDateString("en-IN")}</>}
            <div className="dg__why">{outcome.note}</div>
          </div>
        )}

        {interventions?.length > 0 && (
          <>
            <h3>Actions ({interventions.length})</h3>
            {interventions.map((iv) => <Intervention key={iv.id} iv={iv} />)}
          </>
        )}

        {audit?.length > 0 && (
          <>
            <h3>Audit Trail</h3>
            <div className="timeline">
              {audit.map((a) => (
                <div className={"tl phase-" + a.phase} key={a.id}>
                  <div className="tl__phase">{a.phase} · {a.actor}</div>
                  <div className="tl__summary">{a.summary}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {!dg && <div className="empty">Run the agent to populate diagnosis, actions & audit.</div>}
      </div>
    </div>
  );
}
