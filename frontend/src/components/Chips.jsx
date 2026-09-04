import React from "react";
import { titleCase } from "../lib/format.js";

export function StatusChip({ status }) {
  const label = {
    at_risk: "At Risk",
    in_recovery: "In Recovery",
    recovered: "Recovered",
    escalated: "Escalated",
    promise_to_pay: "Promise to Pay",
    lost: "Not Recovered",
    stopped: "Stopped",
  }[status] || status;
  return <span className={`chip chip--${status}`}>{label}</span>;
}

export function GateChip({ decision }) {
  return <span className={`chip gate--${decision}`}>{decision}</span>;
}

export function TypeTag({ type }) {
  const color = {
    payment_failure: "var(--pink)",
    checkout_abandonment: "var(--purple)",
    subscription_failure: "var(--cyan)",
    invoice_overdue: "var(--orange)",
  }[type] || "var(--yellow)";
  return (
    <span className="tag type-tag" style={{ background: color }}>
      {titleCase(type)}
    </span>
  );
}
