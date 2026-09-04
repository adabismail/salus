const J = async (r) => {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
};

export const getConfig = () => fetch("/api/config").then(J);
export const getEvents = () => fetch("/api/events").then(J);
export const getEvent = (id) => fetch(`/api/events/${id}`).then(J);
export const getGuardrails = () => fetch("/api/guardrails").then(J);
export const getSummary = () => fetch("/api/summary").then(J);

export const putGuardrails = (g) =>
  fetch("/api/guardrails", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(g),
  }).then(J);

export const resetBatch = (seed) =>
  fetch("/api/reset" + (seed != null ? `?seed=${seed}` : ""), { method: "POST" }).then(J);

// Live Razorpay (test mode)
export const liveState = () => fetch("/api/live/state").then(J);
export const liveVerify = () => fetch("/api/live/verify", { method: "POST" }).then(J);
export const liveRecover = (limit = 8) =>
  fetch(`/api/live/recover_batch?limit=${limit}`, { method: "POST" }).then(J);
export const liveSync = () => fetch("/api/live/sync", { method: "POST" }).then(J);

// Server-Sent-Events run feed. Returns a cancel function.
export function runStream({ onEvent, onDone, onError }) {
  const es = new EventSource("/api/run/stream");
  let finished = false;
  es.onmessage = (e) => {
    let d;
    try {
      d = JSON.parse(e.data);
    } catch {
      return;
    }
    if (d.type === "summary") {
      finished = true;
      es.close();
      onDone && onDone(d.summary);
    } else if (d.type === "event") {
      onEvent && onEvent(d);
    }
  };
  es.onerror = () => {
    if (finished) return;
    es.close();
    onError && onError(new Error("stream error"));
  };
  return () => {
    finished = true;
    es.close();
  };
}
