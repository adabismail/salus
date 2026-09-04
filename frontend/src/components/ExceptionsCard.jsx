import React from "react";
import { inr } from "../lib/format.js";
import { StatusChip } from "./Chips.jsx";

function reasonFor(r) {
  if (r.status === "escalated") {
    const esc = r.interventions.find((i) => i.gate && i.gate.decision === "escalate");
    if (esc) return esc.gate.reasons.join(" ");
    const blocked = r.interventions.filter((i) => i.gate && i.gate.decision === "block");
    if (blocked.length)
      return "Every action blocked by policy → routed to a human. " + blocked[0].gate.reasons.join(" ");
    const stop = [...r.audit].reverse().find((a) => a.phase === "stop");
    return stop ? stop.summary : "Routed to a human reviewer.";
  }
  return "Recovery levers exhausted within guardrails; not recovered.";
}

export default function ExceptionsCard({ records }) {
  const exceptions = records.filter(
    (r) => r.status === "escalated" || r.status === "lost"
  );
  return (
    <div className="card">
      <div className="panel-title">
        <span>⚠ Exceptions</span>
        <span className="count">{exceptions.length} not auto-recovered</span>
      </div>
      {exceptions.length === 0 ? (
        <div className="empty">Run the agent to see the honest exception list.</div>
      ) : (
        <div className="exc">
          {exceptions.map((r) => (
            <div
              key={r.event.id}
              className={"exc__item" + (r.status === "lost" ? " blocked" : "")}
            >
              <div className="exc__top">
                <span>{r.event.customer.name}</span>
                <span className="amt">{inr(r.event.amount_paise)}</span>
              </div>
              <div style={{ margin: "4px 0" }}>
                <StatusChip status={r.status} />
              </div>
              <div className="exc__why">{reasonFor(r)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
