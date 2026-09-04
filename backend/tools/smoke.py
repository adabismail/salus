"""Quick end-to-end check: run the agent twice and print the scoreboard.
Run from the backend/ directory:  .venv\\Scripts\\python.exe tools\\smoke.py
"""
from app.store import store


def run_once(label: str):
    for _ in store.run_stream():
        pass
    m = store.summary.metrics
    print(f"\n== {label} ==")
    print(f" events           : {m.at_risk_count}")
    print(f" at risk          : Rs {m.at_risk_paise // 100:,}")
    print(f" recovered        : {m.recovered_count}  (Rs {m.recovered_paise // 100:,})")
    print(f" recovery rate    : {m.recovery_rate * 100:.1f}%")
    print(f" promise-to-pay   : {m.promise_count}  (Rs {m.promise_paise // 100:,})")
    print(f" escalated        : {m.escalated_count}  (Rs {m.escalated_paise // 100:,})")
    print(f" lost             : {m.lost_count}  (Rs {m.lost_paise // 100:,})")
    print(f" cost of recovery : Rs {m.cost_paise / 100:,.2f}")
    print(f" net recovered    : Rs {m.net_recovered_paise // 100:,}")
    print(f" ROI              : {m.roi}x")
    print(f" avg time-to-recover: {m.avg_time_to_recover_hours}h")
    print(f" actions taken/blocked/deferred: {m.actions_taken}/{m.actions_blocked}/{m.actions_deferred}")
    return m.recovered_paise


if __name__ == "__main__":
    a = run_once("run 1")
    b = run_once("run 2 (reproducibility check)")
    print("\nreproducible:", a == b, "(", a // 100, "==", b // 100, ")")
    print("\nby root cause:")
    for rc, v in sorted(store.summary.metrics.by_root_cause.items()):
        print(f"  {rc:22s} at_risk={v['at_risk']:2d} recovered={v['recovered']:2d} "
              f"Rs {v['recovered_paise'] // 100:,}")
