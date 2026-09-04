"""Regression test: a real (Razorpay-confirmed) payment must survive Run Recovery.
Run from backend/:  set PYTHONPATH=.  then  python tools\\livecheck.py
"""
from app.store import store

# Pick a checkout-abandonment event (the simulator often fails these), mark it
# as really paid via a live link, exactly like /api/live/sync would.
target = next(e for e in store.events if e.type.value == "checkout_abandonment")
store.live_links[target.id] = {
    "event_id": target.id, "customer": target.customer.name,
    "link_id": "plink_test", "short_url": "https://rzp.io/test",
    "amount_paise": target.amount_paise, "status": "paid",
    "amount_paid_paise": target.amount_paise,
}
print(f"paid target: {target.customer.name}  ₹{target.amount_paise // 100:,}")

for run in (1, 2):
    for _ in store.run_stream():
        pass
    rec = store.record_by_id(target.id)
    print(f" after run {run}: status={rec.status.value}  recovered=₹{rec.outcome.recovered_amount_paise // 100:,}")
    assert rec.status.value == "recovered", "BUG: live-paid event got overwritten by the simulator!"

m = store.summary.metrics
print(f" metrics: recovered={m.recovered_count} (₹{m.recovered_paise // 100:,})  rate={m.recovery_rate * 100:.1f}%")
print("PASS — real payment survives repeated Run Recovery")
