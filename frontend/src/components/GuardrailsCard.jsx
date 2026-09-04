import React from "react";

function NumRow({ label, value, unit, onChange, disabled, step = 1, min = 0 }) {
  return (
    <div className="grow">
      <label>{label}</label>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input
          type="number"
          value={Number.isFinite(value) ? value : 0}
          step={step}
          min={min}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {unit && <span className="unit">{unit}</span>}
      </div>
    </div>
  );
}

function Toggle({ label, value, onChange, disabled }) {
  return (
    <div className="grow">
      <label>{label}</label>
      <button
        className={"tag"}
        disabled={disabled}
        style={{ background: value ? "var(--green)" : "#e7e2d3", cursor: "pointer" }}
        onClick={() => onChange(!value)}
      >
        {value ? "ON" : "OFF"}
      </button>
    </div>
  );
}

export default function GuardrailsCard({ guardrails, onSave, disabled }) {
  const g = guardrails;
  const set = (patch) => onSave({ ...g, ...patch });
  return (
    <div className="card">
      <div className="panel-title">
        <span>⛓ Guardrails</span>
        <span className="count">policy engine</span>
      </div>
      <NumRow label="Max retries / event" value={g.max_retries} disabled={disabled}
              onChange={(v) => set({ max_retries: v })} />
      <NumRow label="Max contacts / customer" value={g.max_contacts_per_customer} disabled={disabled}
              onChange={(v) => set({ max_contacts_per_customer: v })} />
      <NumRow label="Min gap between contacts" value={g.min_gap_hours} unit="hrs" disabled={disabled}
              onChange={(v) => set({ min_gap_hours: v })} />
      <NumRow label="Quiet hours start" value={g.quiet_start_hour} unit="IST" disabled={disabled}
              onChange={(v) => set({ quiet_start_hour: v })} />
      <NumRow label="Quiet hours end" value={g.quiet_end_hour} unit="IST" disabled={disabled}
              onChange={(v) => set({ quiet_end_hour: v })} />
      <NumRow label="Auto-charge ceiling" value={Math.round(g.max_auto_amount_paise / 100)} unit="₹"
              step={5000} disabled={disabled}
              onChange={(v) => set({ max_auto_amount_paise: v * 100 })} />
      <NumRow label="Human-review ceiling" value={Math.round(g.human_review_amount_paise / 100)} unit="₹"
              step={25000} disabled={disabled}
              onChange={(v) => set({ human_review_amount_paise: v * 100 })} />
      <Toggle label="Respect opt-out" value={g.respect_opt_out} disabled={disabled}
              onChange={(v) => set({ respect_opt_out: v })} />
      <Toggle label="Escalate fraud-flagged" value={g.escalate_risk_blocked} disabled={disabled}
              onChange={(v) => set({ escalate_risk_blocked: v })} />
      <div className="metric__sub" style={{ marginTop: 10 }}>
        Changes apply on the next run. These bounds are enforced deterministically — the
        agent can never act outside them.
      </div>
    </div>
  );
}
