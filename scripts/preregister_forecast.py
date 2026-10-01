"""Writes the pre-registration file for next quarter's GNPA forecasts.

    python scripts/preregister_forecast.py

Runs the backtest, applies the pre-declared selection rule, forecasts the first quarter
after data/quarterly_gnpa.yaml ends, and writes forecasts/<quarter>_preregistration.yaml
with the forecasts, the benchmark, the scoring rules and a hash of the input data.

Refuses to overwrite an existing file: a pre-registration that can be regenerated after
the fact is not one. The file only counts once it is committed (and pushed) before the
first lender reports.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import sys
from pathlib import Path

import yaml

from credit_risk.data_loader import DATA_DIR, load_stress_track_record
from credit_risk.forecast import (
    BENCHMARK, METHODS, backtest, load_quarterly_panel, make_forecasts, select_method, _fit,
)
from credit_risk.track_record import score_track_record

OUT_DIR = DATA_DIR.parent / "forecasts"
# Bajaj Finance: the aggregator's figure (1.20% for Jun 2026) differs from the company's
# headline figure in results coverage (0.96%). Unresolved which basis each is on, so the
# target would be ambiguous. Excluded rather than forecast against an unclear definition.
EXCLUDED = {"BAJFINANCE": "source shows 1.20% for Jun 2026 vs 0.96% in results coverage; which figure is which is unresolved, so the target is ambiguous"}
SCORING_CUTOFF = "2026-11-30"


def _next_quarter(quarter: str) -> str:
    year, month = int(quarter[:4]), int(quarter[5:])
    return f"{year + 1}-03" if month == 12 else f"{year}-{month + 3:02d}"


def main() -> None:
    data_path = DATA_DIR / "quarterly_gnpa.yaml"
    panel = load_quarterly_panel(data_path, exclude=tuple(EXCLUDED))
    target = _next_quarter(panel.quarters[-1])
    out = OUT_DIR / f"{target}_preregistration.yaml"
    if out.exists():
        sys.exit(f"{out} already exists; a pre-registration is never regenerated")

    scores, residuals = backtest(panel)
    method = select_method(scores)
    forecasts = make_forecasts(panel, method, residuals[method])
    coefs = _fit(panel, method, len(panel.quarters)) if method not in ("no_change", "own_drift", "seasonal") else None
    _, open_rbi = score_track_record(load_stress_track_record())

    document = {
        "target_quarter": target,
        "what_is_forecast": "each lender's reported gross NPA ratio (%) at the end of the target quarter",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "first_results_expected": "2026-10-17 (HDFC Bank and Axis Bank, per press coverage of announced board-meeting dates; not checked against the exchange filings)",
        "input_data": {
            "file": "data/quarterly_gnpa.yaml",
            "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
            "source": "screener.in company pages (secondary aggregator of exchange filings)",
            "history": f"{panel.quarters[0]} to {panel.quarters[-1]}, {len(panel.series)} lenders",
        },
        "excluded_lenders": EXCLUDED,
        "method": {
            "candidates": list(METHODS),
            "benchmark": BENCHMARK,
            "selection_rule": "lowest mean absolute error (percentage points) in an expanding-window backtest; ties to the simpler method",
            "backtest": [
                {"method": s.method, "n": s.n, "mae_pp": s.mae_pp,
                 "median_abs_rel_error_pct": s.median_abs_rel_error_pct,
                 "share_closer_than_benchmark_pct": s.share_closer_than_benchmark_pct}
                for s in scores
            ],
            "selected": method,
            "fitted_coefficients": [round(c, 5) for c in coefs] if coefs else None,
            "plain_reading": (
                "sector_drift multiplies every lender's last GNPA by the same factor, exp(coefficient): "
                "the average quarterly percentage change across all lenders and past quarters."
                if method == "sector_drift" else "see credit_risk/forecast.py"
            ),
        },
        "scoring_rules": {
            "actual": "the lender's first-reported gross NPA ratio for the target quarter, read from the same source after results, and cross-checked against the lender's own results release for the standstill-panel lenders; later restatements are ignored",
            "primary_metric": "mean absolute error in percentage points over all lenders that have reported by the cutoff",
            "win_condition": f"the selected method's MAE is lower than the {BENCHMARK} benchmark's MAE on the same lenders",
            "secondary": [
                f"share of lenders for which the selected method is closer than {BENCHMARK}",
                "share of actuals inside the 80% interval (well calibrated if roughly 70-90%)",
            ],
            "cutoff": SCORING_CUTOFF,
            "dropped_if": "the lender has not reported by the cutoff, has merged, or has changed its NPA definition; every drop is listed in the scored file",
            "no_edits": "this file is never edited after it is committed; a correction is a new file that says so",
        },
        "stated_risk": (
            "The history is 13 quarters in which GNPA fell at almost every lender. A method that "
            "extrapolates that fall wins the backtest and will lose to the benchmark if the cycle turns "
            "this quarter. That is the same failure this project documents in RBI's baselines, which "
            "under-called every large move. Losing to no_change is a live possibility and would be reported as such."
        ),
        "forecasts": [
            {"symbol": f.symbol, "name": f.name, "last_quarter": f.last_quarter, "last_gnpa": f.last_gnpa,
             "forecast_gnpa": f.forecast_gnpa, "benchmark_gnpa": f.benchmark_gnpa,
             "interval_80": list(f.interval_80)}
            for f in forecasts
        ],
        "also_tracking_rbi_open_baselines": open_rbi,
    }
    OUT_DIR.mkdir(exist_ok=True)
    out.write_text(
        "# PRE-REGISTERED FORECAST. Generated by scripts/preregister_forecast.py; never edited by hand.\n"
        "# It counts only from the moment it is committed and pushed -- see the git history for that time.\n\n"
        + yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    print(f"wrote {out}")
    print(f"selected method: {method}  coefficients: {document['method']['fitted_coefficients']}")
    for f in forecasts:
        print(f"  {f.symbol:<11} last {f.last_gnpa:>5.2f}  forecast {f.forecast_gnpa:>5.2f}  "
              f"80% [{f.interval_80[0]:.2f}, {f.interval_80[1]:.2f}]")


if __name__ == "__main__":
    main()
