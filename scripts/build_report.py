"""Prints the real forecast-error analysis end to end. Every number traces to
data/*.yaml; see each file's header for exact provenance."""
from __future__ import annotations

import datetime as dt

from credit_risk.analysis import (
    compute_forecast_errors, compute_shadow_gnpa, eclgs_scale_vs_credit_book, naive_linear_trend_projection,
)
from credit_risk.data_loader import (
    load_bajaj_finance, load_iifl_finance, load_nbfc_gnpa, load_nbfc_stress_test,
    load_policy_interventions, load_resolution_framework, load_scb_gnpa,
)


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

    print("\n=== NBFC-sector aggregate GNPA (now primary-sourced for FY15-FY19) ===")
    nbfc = load_nbfc_gnpa()
    for date, v in sorted(nbfc.fiscal_year_end_gnpa_pct.items()):
        print(f"  {date}: {v['value']}% ({v['provenance']})")

    print("\n=== RBI's real NBFC-sector stress test (capital adequacy, not a GNPA forecast) ===")
    nbfc_stress = load_nbfc_stress_test()
    print(f"  As of {nbfc_stress['as_of']}, baseline sector CRAR {nbfc_stress['baseline_sector_crar_pct']}%")
    for s in nbfc_stress["shocks"]:
        print(f"    GNPA shock {s['gnpa_shock']}: sector CRAR falls to {s['resulting_sector_crar_pct']}%, "
              f"{s['pct_of_companies_breaching_15pct_crar']}% of companies breach 15% CRAR")

    print("\n=== IIFL Finance (third real NBFC cross-check) + direct forbearance evidence ===")
    iifl = load_iifl_finance()
    for date, v in sorted(iifl.series.items()):
        print(f"  {date}: GNPA {v['gnpa_pct']}% / NNPA {v['nnpa_pct']}%")
    fb = iifl.regulatory_forbearance_evidence
    print(f"  Direct evidence of NPA-recognition suppression, as of {fb['as_of']}:")
    print(f"    Reported (with '{fb['mechanism']}'): GNPA {fb['reported_gnpa_pct']}% / NNPA {fb['reported_nnpa_pct']}%")
    print(f"    Proforma (without it): GNPA {fb['proforma_gnpa_pct_without_the_order']}% / "
          f"NNPA {fb['proforma_nnpa_pct_without_the_order']}%")
    print(f"    -> a real company disclosed {fb['implied_gnpa_suppression_pp']}pp of GNPA suppression from this "
          f"one mechanism alone -- direct support for the interpretation above, not just a plausible guess")

    print("\n=== Shadow GNPA: how far can real restructuring data close RBI's forecast gap? ===")
    rf = load_resolution_framework()
    for target, proj_key in ((dt.date(2021, 3, 1), 0), (dt.date(2021, 9, 1), 1)):
        proj = scb.stress_projections[proj_key]
        restructured = rf.actual_restructured_pct[target]
        for k in (0.0, 0.5, 1.0):
            result = compute_shadow_gnpa(scb.actual_gnpa_pct[target], restructured, k, proj.baseline_pct, target.isoformat())
            print(f"  {target} k={k:.1f}: shadow GNPA {result.shadow_gnpa_pct}% "
                  f"(closes {result.gap_to_rbi_baseline_explained_pct}% of the gap to RBI's {proj.baseline_pct}% baseline)")
    print("  -> even at k=1.0, restructuring alone cannot come close to explaining RBI's forecast miss")

    print("\n=== Known gaps, stated plainly ===")
    for gap in scb.known_gaps + nbfc.known_gaps + rf.known_gaps:
        print(f"  - {gap}")


if __name__ == "__main__":
    main()
