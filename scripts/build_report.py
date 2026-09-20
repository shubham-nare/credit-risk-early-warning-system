"""Prints the real forecast-error analysis end to end. Every number traces to
data/*.yaml; see each file's header for exact provenance."""
from __future__ import annotations

import datetime as dt

from credit_risk.analysis import compute_forecast_errors, eclgs_scale_vs_credit_book, naive_linear_trend_projection
from credit_risk.data_loader import load_bajaj_finance, load_policy_interventions, load_scb_gnpa


def main() -> None:
    scb = load_scb_gnpa()

    print("=== RBI's own COVID stress-test forecast errors (SCB system GNPA) ===")
    for e in compute_forecast_errors(scb):
        print(f"  [{e.projection_made_in}] {e.target_date} {e.scenario}: projected {e.projected_pct}% "
              f"vs actual {e.actual_pct}% -> missed by {e.error_pp:+.2f}pp ({e.relative_error_pct:+.1f}% relative)")

    print("\n=== Naive linear trend through the 4 real pre-COVID points, for comparison ===")
    for target in (dt.date(2021, 3, 1), dt.date(2021, 9, 1)):
        try:
            proj = naive_linear_trend_projection(scb, target)
            print(f"  {proj.target_date}: naive trend projects {proj.projected_pct}% vs actual {proj.actual_pct}% "
                  f"-> missed by {proj.error_pp:+.2f}pp (fit slope {proj.slope_pp_per_year:+.2f}pp/year)")
        except ValueError as exc:
            print(f"  {target}: {exc}")

    print("\n=== Scale of COVID-specific credit support vs. the whole system ===")
    ctx = eclgs_scale_vs_credit_book(load_policy_interventions())
    print(f"  ECLGS disbursed Rs.{ctx.eclgs_disbursed_by_date_cr:,.0f} Cr by {ctx.eclgs_as_of}, "
          f"vs. Rs.{ctx.total_credit_book_cr:,.0f} Cr total non-food bank credit outstanding ({ctx.credit_book_as_of}) "
          f"= {ctx.eclgs_share_of_credit_book_pct}% of the whole book")

    print("\n=== Bajaj Finance (real company-level cross-check) vs. system-wide SCB GNPA ===")
    bajaj = load_bajaj_finance()
    for date, values in sorted(bajaj.quarterly.items()):
        scb_val = scb.actual_gnpa_pct.get(date)
        comp = f"(system: {scb_val}%)" if scb_val is not None else "(no system figure at this exact date)"
        print(f"  {date}: Bajaj GNPA {values['gnpa_pct']}% {comp}")

    print("\n=== Known gaps, stated plainly ===")
    for gap in scb.known_gaps:
        print(f"  - {gap}")


if __name__ == "__main__":
    main()
