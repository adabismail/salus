from __future__ import annotations

import asyncio
import json
import os
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import live
from .config import settings
from .diagnosis import diagnose
from .models import (AuditEntry, Channel, EventRecord, EventStatus, GateDecision,
                     Guardrails, Intervention, InterventionType, Metrics, Outcome,
                     PolicyResult, RunSummary, new_id, now_ist)
from .store import store

app = FastAPI(title="Salus — Revenue Recovery Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "salus", "version": "0.1.0"}


@app.get("/api/config")
def get_config() -> dict:
    return {
        "mode": settings.MODE,
        "razorpay_live": settings.razorpay_live,
        "razorpay_configured": settings.razorpay_configured,
        "key_id": settings.masked_key_id,
        "llm_enabled": settings.llm_enabled,
        "seed": store.seed,
        "batch_size": len(store.events),
    }


@app.get("/api/events", response_model=list[EventRecord])
def list_events() -> list[EventRecord]:
    return store.records


@app.get("/api/events/{event_id}", response_model=EventRecord)
def get_event(event_id: str) -> EventRecord:
    rec = store.record_by_id(event_id)
    if not rec:
        raise HTTPException(404, "event not found")
    return rec


@app.get("/api/guardrails", response_model=Guardrails)
def get_guardrails() -> Guardrails:
    return store.guardrails


@app.put("/api/guardrails", response_model=Guardrails)
def put_guardrails(g: Guardrails) -> Guardrails:
    store.set_guardrails(g)
    return store.guardrails


@app.get("/api/metrics", response_model=Metrics)
def get_metrics() -> Metrics:
    return store.current_metrics()


@app.get("/api/summary", response_model=RunSummary)
def get_summary() -> RunSummary:
    if not store.summary:
        raise HTTPException(404, "no run yet")
    return store.summary


@app.get("/api/audit", response_model=list[AuditEntry])
def get_audit() -> list[AuditEntry]:
    entries: list[AuditEntry] = []
    for rec in store.records:
        entries.extend(rec.audit)
    entries.sort(key=lambda e: e.ts)
    return entries


@app.post("/api/reset")
def reset(seed: int | None = None) -> dict:
    store.reset(seed)
    return {"ok": True, "seed": store.seed, "batch_size": len(store.events)}


@app.post("/api/run", response_model=RunSummary)
def run_once() -> RunSummary:
    for _ in store.run_stream():
        pass
    assert store.summary is not None
    return store.summary


@app.get("/api/run/stream")
async def run_stream() -> StreamingResponse:
    async def gen():
        for progress in store.run_stream():
            yield f"data: {json.dumps(progress)}\n\n"
            await asyncio.sleep(0.035)  # paces the live animation
        # emit the final summary so the client can render the scoreboard
        if store.summary:
            payload = {"type": "summary", "summary": json.loads(store.summary.model_dump_json())}
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _require_keys() -> None:
    if not settings.razorpay_configured:
        raise HTTPException(400, "No Razorpay keys configured (set RAZORPAY_KEY_ID/SECRET in backend/.env).")


@app.post("/api/live/verify")
def live_verify() -> dict:
    _require_keys()
    return live.verify()


@app.post("/api/live/recover_batch")
def live_recover_batch(limit: int = 8) -> dict:
    """Create REAL Razorpay test-mode payment links for the first `limit`
    genuinely-recoverable events. These appear in the merchant's dashboard."""
    _require_keys()
    created: list[dict] = []
    errors: list[str] = []
    eligible = 0
    for rec in store.records:
        if len(created) >= limit:
            break
        ev = rec.event
        if ev.id in store.live_links:
            continue
        dg = rec.diagnosis or diagnose(ev)
        rec.diagnosis = dg
        if not dg.recoverable or ev.risk_flag:
            continue
        if ev.amount_paise > store.guardrails.human_review_amount_paise:
            continue
        eligible += 1
        if created:
            time.sleep(0.4)  # space the calls out; Razorpay throttles bursts
        try:
            link = live.create_payment_link(ev)
        except Exception as exc:  # noqa: BLE001 - report it, don't fail silently
            msg = str(exc)
            errors.append(f"{ev.customer.name}: {msg[:160]}")
            rec.audit.append(AuditEntry(event_id=ev.id, phase="execute", actor="razorpay",
                                        summary=f"Razorpay link creation failed: {msg[:200]}"))
            if "429" in msg or "rate limit" in msg.lower():
                break  # throttled — stop hammering and report back
            continue
        store.live_links[ev.id] = {
            "event_id": ev.id, "customer": ev.customer.name,
            "link_id": link["id"], "short_url": link["short_url"],
            "amount_paise": link["amount"], "status": link.get("status", "created"),
            "amount_paid_paise": link.get("amount_paid", 0),
        }
        rec.interventions.append(Intervention(
            id=new_id("act"), event_id=ev.id, type=InterventionType.NEW_PAYMENT_LINK,
            channel=Channel.WHATSAPP, razorpay_ref=link["id"],
            message=f"(live) Pay ₹{ev.amount_paise // 100:,} here: {link['short_url']}",
            gate=PolicyResult(decision=GateDecision.ALLOW, reasons=["Live test-mode link created."]),
            executed=True))
        rec.status = EventStatus.IN_RECOVERY
        rec.audit.append(AuditEntry(event_id=ev.id, phase="execute", actor="razorpay",
                                    summary=f"Created REAL Razorpay test link for ₹{ev.amount_paise // 100:,}.",
                                    detail={"link_id": link["id"], "short_url": link["short_url"]}))
        created.append(store.live_links[ev.id])

    if created:
        message = f"Created {len(created)} real Razorpay test link(s)."
    elif errors:
        message = errors[0]
    elif eligible == 0:
        message = "No eligible events left — every recoverable event already has a link. Hit Sync, or reset the batch."
    else:
        message = "Nothing was created."
    return {"created": len(created), "links": created, "errors": errors, "message": message}


@app.post("/api/live/sync")
def live_sync() -> dict:
    """Poll Razorpay for the real status of every created link; mark truly-paid ones recovered."""
    _require_keys()
    paid = paid_paise = created_paise = 0
    for event_id, info in store.live_links.items():
        try:
            data = live.fetch_payment_link(info["link_id"])
        except Exception:  # noqa: BLE001
            continue
        info["status"] = data.get("status", info["status"])
        info["amount_paid_paise"] = data.get("amount_paid", 0)
        created_paise += info["amount_paise"]
        if info["status"] == "paid":
            amt = data.get("amount_paid") or info["amount_paise"]
            paid += 1
            paid_paise += amt
            rec = store.record_by_id(event_id)
            if rec and rec.status != EventStatus.RECOVERED:
                rec.status = EventStatus.RECOVERED
                rec.outcome = Outcome(recovered=True, recovered_amount_paise=amt, recovered_at=now_ist(),
                                      winning_intervention=InterventionType.NEW_PAYMENT_LINK,
                                      note="Confirmed paid via Razorpay (test mode).")
                rec.audit.append(AuditEntry(event_id=event_id, phase="outcome", actor="razorpay",
                                            summary=f"✅ Razorpay confirmed ₹{amt // 100:,} paid — recovered."))
    return {"tracked": len(store.live_links), "created_paise": created_paise,
            "paid": paid, "paid_paise": paid_paise}


@app.get("/api/live/state")
def live_state() -> dict:
    links = list(store.live_links.values())
    paid = [l for l in links if l.get("status") == "paid"]
    return {
        "configured": settings.razorpay_configured,
        "key_id": settings.masked_key_id,
        "count": len(links),
        "created_paise": sum(l["amount_paise"] for l in links),
        "paid": len(paid),
        "paid_paise": sum((l.get("amount_paid_paise") or l["amount_paise"]) for l in paid),
        "links": links,
    }


@app.post("/api/webhook/razorpay")
async def razorpay_webhook(request: Request) -> dict:
    """Real-time recovery: verify the HMAC signature, then flip the matched event."""
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not live.verify_webhook_signature(raw, sig):
        raise HTTPException(400, "invalid webhook signature")
    event = json.loads(raw or b"{}")
    entity = event.get("payload", {}).get("payment_link", {}).get("entity", {})
    event_id = entity.get("notes", {}).get("salus_event_id")
    if event_id:
        rec = store.record_by_id(event_id)
        if rec and rec.status != EventStatus.RECOVERED:
            amt = entity.get("amount_paid") or rec.event.amount_paise
            rec.status = EventStatus.RECOVERED
            rec.outcome = Outcome(recovered=True, recovered_amount_paise=amt, recovered_at=now_ist(),
                                  winning_intervention=InterventionType.NEW_PAYMENT_LINK,
                                  note="Confirmed paid via Razorpay webhook (test mode).")
    return {"ok": True}


@app.post("/api/live/import")
def live_import() -> dict:
    """Re-attach payment links that already exist on the Razorpay account.

    Link state lives in memory, so a restart loses it - but the links themselves
    live on in Razorpay. This pulls them back (and picks up any paid meanwhile)
    without creating anything, which also sidesteps the create rate limit.
    """
    _require_keys()
    try:
        links = live.list_payment_links()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Could not list Razorpay links: {exc}")

    by_event = {r.event.id: r for r in store.records}
    by_key = {}
    for r in store.records:
        by_key.setdefault((r.event.customer.name.strip().lower(), r.event.amount_paise), r)

    # Paid links win when several match the same event.
    links = sorted(links, key=lambda l: 0 if l.get("status") == "paid" else 1)

    touched = set()
    paid = 0
    for l in links:
        eid = (l.get("notes") or {}).get("salus_event_id")
        rec = by_event.get(eid) if eid else None
        if rec is None:
            name = ((l.get("customer") or {}).get("name") or "").strip().lower()
            rec = by_key.get((name, l.get("amount")))
        if rec is None:
            continue
        existing = store.live_links.get(rec.event.id)
        if existing and existing.get("status") == "paid":
            continue
        store.live_links[rec.event.id] = {
            "event_id": rec.event.id, "customer": rec.event.customer.name,
            "link_id": l["id"], "short_url": l.get("short_url", ""),
            "amount_paise": l.get("amount", rec.event.amount_paise),
            "status": l.get("status", "created"),
            "amount_paid_paise": l.get("amount_paid", 0),
        }
        touched.add(rec.event.id)
        if l.get("status") == "paid":
            paid += 1

    store._apply_live_recoveries()
    imported = len(touched)
    message = (f"Imported {imported} existing Razorpay link(s) - {paid} already paid."
               if imported else "No matching links found on your Razorpay account.")
    return {"imported": imported, "paid": paid, "message": message}


_static_dir = os.getenv("SALUS_STATIC_DIR")
if _static_dir and os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
