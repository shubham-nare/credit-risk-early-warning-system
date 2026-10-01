"""Prints the lender-level standstill analysis end to end. Every number traces to
data/standstill_panel.yaml, which records the filing and page each one was read from."""
from __future__ import annotations

import datetime as dt

from credit_risk.data_loader import load_scb_gnpa, load_standstill_panel
from credit_risk.standstill import catch_up_test, hidden_stress, system_standstill_context


def _print_catch_up(label: str, result) -> None:
    print(f"\n=== {label} (n={result.n}) ===")
    print(f"  mean absolute error vs Mar-2021 reported GNPA: Dec-2020 REPORTED {result.mae_reported_pp:.2f}pp, "
          f"Dec-2020 PROFORMA {result.mae_proforma_pp:.2f}pp")
    print(f"  proforma was the closer number for {result.n_proforma_closer} of {result.n} lenders "
          f"(exact sign test p={result.sign_test_p}; exact paired permutation test p={result.permutation_test_p})")
    print(f"  Mar-2021 reported GNPA came in below the Dec-2020 proforma for {result.n_outcome_below_proforma} of {result.n}")
    print(f"  rank correlation, hidden stress vs subsequent rise in reported GNPA: {result.rank_corr_hidden_vs_rise:+.2f}")


def main() -> None:
    panel = load_standstill_panel()

    for date, label in ((dt.date(2020, 9, 1), "Sep 2020"), (dt.date(2020, 12, 1), "Dec 2020")):
        print(f"\n=== Hidden gross NPA under the standstill, {label} (proforma minus reported) ===")
        for h in hidden_stress(panel, date):
            print(f"  {h.lender:<22} reported {h.reported_gnpa:>5.2f}%  proforma {h.proforma_gnpa:>5.2f}%  "
                  f"hidden {h.hidden_pp:>4.2f}pp = {h.hidden_share_of_proforma_pct:>4.1f}% of proforma  [{h.provenance}]")

    result = catch_up_test(panel)
    print("\n=== Which Dec-2020 number told you where the lender would be in Mar-2021? ===")
    for r in result.rows:
        print(f"  {r.lender:<22} Dec reported {r.reported_gnpa:>5.2f}%  Dec proforma {r.proforma_gnpa:>5.2f}%  "
              f"Mar reported {r.outcome_gnpa:>5.2f}%  | error: reported {r.reported_error_pp:.2f}pp, "
              f"proforma {r.proforma_error_pp:.2f}pp  [{r.provenance}]")
    _print_catch_up("All lenders", result)
    _print_catch_up("Robustness: excluding Bandhan Bank, the largest gap", catch_up_test(panel, exclude=("bandhan_bank",)))
    primary_only = tuple(k for k, lender in panel.lenders.items()
                         if not all(q.provenance == "primary" for d, q in lender.quarters.items()
                                    if d in (dt.date(2020, 12, 1), dt.date(2021, 3, 1))))
    _print_catch_up("Robustness: primary-sourced lenders only", catch_up_test(panel, exclude=primary_only))

    scb = load_scb_gnpa()
    proj = next(p for p in scb.stress_projections if p.target_date == dt.date(2021, 3, 1))
    ctx = system_standstill_context(panel, proj.baseline_pct, "2021-03")
    print("\n=== System level: could the standstill explain RBI's stress-test miss? ===")
    print(f"  All banks, {ctx.as_of} (ICRA, secondary): proforma GNPA {ctx.system_proforma_gnpa_pct}%, of which "
          f"{ctx.hidden_share_of_proforma_pct}% ({ctx.hidden_pp}pp) was unreported")
    print(f"  RBI's baseline for {ctx.rbi_baseline_target} was {ctx.rbi_baseline_pct}% -- still "
          f"{ctx.baseline_minus_proforma_pp}pp above even the proforma figure three months earlier")
    print(f"  And the Mar-2021 actual ({scb.actual_gnpa_pct[dt.date(2021, 3, 1)]}%) was struck after the order was vacated on "
          f"{panel.standstill['vacated_date']}, so it already includes the catch-up")

    print("\n=== Known gaps in the panel ===")
    for gap in panel.known_gaps:
        print(f"  - {gap}")


if __name__ == "__main__":
    main()
