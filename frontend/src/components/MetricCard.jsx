import React from "react";

export default function MetricCard({ label, value, sub, accent, highlight, pop }) {
  return (
    <div
      className={"card metric" + (highlight ? " metric--hi" : "")}
      style={{ "--accent": accent }}
    >
      <div className="metric__label upper">{label}</div>
      <div className={"metric__value" + (highlight ? " metric__value--lg" : "") + (pop ? " pop" : "")}>
        {value}
      </div>
      {sub != null && <div className="metric__sub">{sub}</div>}
    </div>
  );
}
