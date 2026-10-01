"""Scores a pre-registered forecast against what lenders actually reported.

    python scripts/score_forecast.py forecasts/2026-09_preregistration.yaml

Re-downloads each lender's page (into sources/screener_<today>/, so the pages the forecast
was built from are left untouched), reads the target quarter's gross NPA ratio where it has
been published, and prints the comparison under the rules written in the pre-registration
file. Lenders that have not reported yet are listed, not scored. Writes nothing to the
pre-registration file.
"""
from __future__ import annotations

import datetime as dt
import statistics
import sys
import time
import urllib.request
from pathlib import Path

import yaml

from fetch_quarterly_gnpa import HEADERS, ROOT, parse


def _fresh_page(symbol: str, raw_dir: Path) -> str:
    target = raw_dir / f"{symbol.replace('&', '_')}.html"
    if not target.exists():
        url = f"https://www.screener.in/company/{urllib.request.quote(symbol)}/"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
            target.write_bytes(response.read())
        time.sleep(1.5)
    return target.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    prereg = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
    quarter = prereg["target_quarter"]
    raw_dir = ROOT / "sources" / f"screener_{dt.date.today().isoformat()}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows, waiting = [], []
    for f in prereg["forecasts"]:
        parsed = parse(_fresh_page(f["symbol"], raw_dir))
        actual = parsed[1].get(quarter, {}).get("gnpa") if parsed else None
        if actual is None:
            waiting.append(f["symbol"])
            continue
        low, high = f["interval_80"]
        rows.append((f["symbol"], f["last_gnpa"], f["forecast_gnpa"], f["benchmark_gnpa"], actual, low <= actual <= high))

    print(f"Target quarter {quarter}: {len(rows)} of {len(prereg['forecasts'])} lenders have reported")
    if waiting:
        print("  not yet reported:", ", ".join(waiting))
    if not rows:
        return
    print("\n  lender        last  forecast  benchmark  actual | model err  bench err  in 80%")
    for symbol, last, forecast, bench, actual, inside in rows:
        print(f"  {symbol:<11} {last:>5.2f}  {forecast:>8.2f}  {bench:>9.2f}  {actual:>6.2f} | "
              f"{forecast - actual:>+9.2f}  {bench - actual:>+9.2f}  {'yes' if inside else 'NO'}")
    model_mae = statistics.fmean(abs(r[2] - r[4]) for r in rows)
    bench_mae = statistics.fmean(abs(r[3] - r[4]) for r in rows)
    closer = sum(abs(r[2] - r[4]) < abs(r[3] - r[4]) for r in rows)
    print(f"\n  PRIMARY  MAE: {prereg['method']['selected']} {model_mae:.3f}pp vs "
          f"{prereg['method']['benchmark']} {bench_mae:.3f}pp -> "
          f"{'model wins' if model_mae < bench_mae else 'benchmark wins or ties'}")
    print(f"  model closer than benchmark for {closer} of {len(rows)} lenders")
    print(f"  80% interval coverage: {sum(r[5] for r in rows)} of {len(rows)}")
    print(f"  (final only after the cutoff, {prereg['scoring_rules']['cutoff']})")


if __name__ == "__main__":
    main()
