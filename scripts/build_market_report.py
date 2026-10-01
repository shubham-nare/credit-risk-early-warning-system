"""Prints the results-day market test. Inputs: data/standstill_panel.yaml,
data/q3fy21_results_dates.yaml and the cached prices in data/event_prices.csv."""
from __future__ import annotations

from credit_risk.data_loader import load_standstill_panel
from credit_risk.market_test import load_prices, load_results_dates, results_day_test

# The Union Budget of 1 Feb 2021 moved the bank index 9-12% inside these lenders' event
# windows; a market-adjusted return with no beta is at its least reliable there.
BUDGET_WINDOW = ("icici_bank", "idfc_first_bank", "indusind_bank", "union_bank")


def _print(label: str, r) -> None:
    print(f"\n=== {label} (n={r.n}) ===")
    print(f"  rank correlation, hidden stress in percentage points vs abnormal return: "
          f"{r.rank_corr_hidden_pp:+.2f} (permutation p={r.p_hidden_pp})")
    print(f"  rank correlation, hidden stress as a share of proforma vs abnormal return: "
          f"{r.rank_corr_hidden_share:+.2f} (permutation p={r.p_hidden_share})")
    print(f"  mean abnormal return: above-median hidden stress {r.mean_abnormal_high_hidden_pct:+.2f}%, "
          f"at-or-below median {r.mean_abnormal_low_hidden_pct:+.2f}%")


def main() -> None:
    panel, prices = load_standstill_panel(), load_prices()
    dates, benchmark = load_results_dates()
    result = results_day_test(panel, prices, dates, benchmark)

    print("=== Results day, quarter ended Dec 2020: hidden stress revealed vs share-price reaction ===")
    print("  (return from the close before the announcement to the close of the trading day after it,")
    print(f"   minus the same for {benchmark})")
    print("  lender                       date        date basis  hidden pp  stock %  index %  abnormal %")
    for x in result.rows:
        print(f"  {x.lender:<28} {x.event_date}  {x.date_basis:<10} {x.hidden_pp:>9.2f} {x.stock_return_pct:>8.2f} "
              f"{x.index_return_pct:>8.2f} {x.abnormal_return_pct:>11.2f}")

    _print("All lenders", result)
    inferred = tuple(k for k, v in dates.items() if v["basis"] == "inferred")
    _print("Robustness: dropping the two lenders whose results date is inferred",
           results_day_test(panel, prices, dates, benchmark, exclude=inferred))
    _print("Robustness: dropping the four lenders whose window spans Budget day (1 Feb 2021)",
           results_day_test(panel, prices, dates, benchmark, exclude=BUDGET_WINDOW))
    _print("Robustness: dropping Bandhan Bank, the largest hidden stress",
           results_day_test(panel, prices, dates, benchmark, exclude=("bandhan_bank",)))
    print("\n  Two measures were tested, so a p-value near 0.01 on one of them is weaker evidence than it looks.")
    print("  Returns are market-adjusted only (no beta), and reflect the whole results release, not just GNPA.")


if __name__ == "__main__":
    main()
