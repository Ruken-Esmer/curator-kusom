#!/usr/bin/env python3
"""Run the full MİMAR protocol on synthetic data from the command line.

    cd backend
    python ../scripts/run_mimar_demo.py [--quick] [--db data/mimar/demo.sqlite3] [--out demo_summary.json]

Writes a JSON summary (AS1 → AS6, audit-chain status).  Synthetic data and
simulated raters only — the numbers are illustrative, not evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.mimar.demo import run_full_demo  # noqa: E402
from app.mimar.service import MimarService  # noqa: E402
from app.mimar.store import Store  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip stability and controlled AS6 scenarios")
    ap.add_argument("--db", default=":memory:")
    ap.add_argument("--out", default="mimar_demo_summary.json")
    a = ap.parse_args()
    svc = MimarService(Store(a.db))
    admin = svc.ensure_admin("dev-admin-token")
    t0 = time.perf_counter()
    s = run_full_demo(svc, admin, quick=a.quick)
    s.pop("users", None)
    s["runtime_seconds"] = round(time.perf_counter() - t0, 1)
    Path(a.out).write_text(json.dumps(s, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    h1 = s["as1"]["h1"]
    print(f"AS1  H1 verdict: {h1['verdict']}  (sens={h1['criterion_sensitivity']['estimate']}, "
          f"ΔPPV CI low={h1['criterion_ppv_difference']['ci95_lower']})")
    print(f"AS2a ΔMU = {s['as2a']['main']['delta_pp']} pp, CI {s['as2a']['main']['ci95']}, H2a met={s['as2a']['h2a']['met']}")
    print(f"AS2b new verified share = {s['as2b']['share']}")
    print(f"AS5  joint rate = {s['as5']['joint_rate']} ({s['as5']['verdict']})")
    if "as6_controlled" in s:
        print(f"AS6  controlled: verified={s['as6_controlled']['verified_alert_rate']}, missed={s['as6_controlled']['missed_expected_rate']}")
    print(f"audit chain valid={s['audit']['valid']} ({s['audit']['entries']} entries) · {s['runtime_seconds']} s → {a.out}")


if __name__ == "__main__":
    main()
