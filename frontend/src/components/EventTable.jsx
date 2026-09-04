import React from "react";
import { inr, titleCase } from "../lib/format.js";
import { StatusChip, TypeTag } from "./Chips.jsx";

export default function EventTable({ records, liveStatus, selectedId, onSelect }) {
  return (
    <div className="card">
      <div className="panel-title">
        <span>At-Risk Ledger</span>
        <span className="count">{records.length} events</span>
      </div>
      <div className="thead">
        <div>Customer</div>
        <div>Type</div>
        <div style={{ textAlign: "right" }}>Amount</div>
        <div>Status</div>
      </div>
      <div className="tlist">
        {records.map((r) => {
          const status = liveStatus[r.event.id] || r.status;
          const cause = r.diagnosis?.root_cause;
          return (
            <div
              key={r.event.id}
              className={"trow" + (selectedId === r.event.id ? " sel" : "")}
              onClick={() => onSelect(r.event.id)}
            >
              <div className="who">
                {r.event.customer.name}
                <small>{cause ? titleCase(cause) : r.event.customer.email}</small>
              </div>
              <div><TypeTag type={r.event.type} /></div>
              <div className="amt" style={{ textAlign: "right" }}>{inr(r.event.amount_paise)}</div>
              <div><StatusChip status={status} /></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
