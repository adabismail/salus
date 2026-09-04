import React from "react";
import { compactInr, titleCase } from "../lib/format.js";

export default function BreakdownCard({ byRootCause }) {
  const rows = Object.entries(byRootCause || {}).sort(
    (a, b) => b[1].at_risk - a[1].at_risk
  );
  return (
    <div className="card">
      <div className="panel-title">
        <span>◍ Recovery by Root Cause</span>
      </div>
      {rows.length === 0 ? (
        <div className="empty">Run the agent to see where money was recovered.</div>
      ) : (
        <div className="bd">
          {rows.map(([cause, v]) => {
            const rec = (v.recovered / v.at_risk) * 100;
            const esc = (v.escalated / v.at_risk) * 100;
            return (
              <div className="bd__row" key={cause}>
                <div className="bd__head">
                  <span className="cause">{titleCase(cause)}</span>
                  <span className="val">
                    {v.recovered}/{v.at_risk} · {compactInr(v.recovered_paise)}
                  </span>
                </div>
                <div className="bar" style={{ display: "flex" }}>
                  <div className="bar__fill" style={{ width: `${rec}%` }} />
                  <div className="bar__fill bar__esc" style={{ width: `${esc}%` }} />
                </div>
              </div>
            );
          })}
          <div className="metric__sub" style={{ marginTop: 4 }}>
            <span style={{ color: "var(--green)", fontWeight: 800 }}>█</span> recovered&nbsp;&nbsp;
            <span style={{ color: "var(--orange)", fontWeight: 800 }}>█</span> escalated to human
          </div>
        </div>
      )}
    </div>
  );
}
