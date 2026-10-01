"""Prints the scored track record of RBI's stress-test baselines for system GNPA. Every
number traces to data/rbi_stress_track_record.yaml, which cites RBI's own page for each."""
from __future__ import annotations

from credit_risk.data_loader import load_stress_track_record
from credit_risk.track_record import score_track_record, summarise


def _print_summary(label: str, s) -> None:
    print(f"\n=== {label} (n={s.n}) ===")
    print(f"  mean absolute error: RBI baseline {s.mae_rbi_pp:.2f}pp vs 'no change' {s.mae_no_change_pp:.2f}pp")
    print(f"  'no change' was closer {s.n_no_change_closer} times, RBI's baseline {s.n_rbi_closer} times, "
          f"tied {s.n_tied} (sign test p={s.sign_test_p}, indicative only: overlapping horizons)")
    print(f"  direction of change called correctly: {s.n_direction_correct} of {s.n_direction_scored}")
    if s.mean_error_when_gnpa_rose_pp is not None:
        print(f"  when GNPA actually ROSE ({s.n_when_rose} cases): mean error {s.mean_error_when_gnpa_rose_pp:+.2f}pp")
    if s.mean_error_when_gnpa_fell_pp is not None:
        print(f"  when GNPA actually FELL ({s.n_when_fell} cases): mean error {s.mean_error_when_gnpa_fell_pp:+.2f}pp")
    print(f"  correlation between RBI's error and the actual change in GNPA: {s.error_vs_actual_change_corr:+.2f}")
    print(f"  average size of move: RBI's baseline called for {s.mean_abs_predicted_change_pp:.2f}pp, "
          f"the actual move was {s.mean_abs_actual_change_pp:.2f}pp")
    print(f"  longest run of consecutive overshoots: {s.longest_overshoot_streak} "
          f"({s.overshoot_streak_from} to {s.overshoot_streak_to})")


def main() -> None:
    record = load_stress_track_record()
    scored, pending = score_track_record(record)

    print("=== RBI stress-test baselines for SCB gross NPA, scored against outcomes ===")
    print("  edition        as-of -> target   start  baseline  actual | RBI error  no-change error  direction")
    for s in scored:
        direction = {True: "right", False: "WRONG", None: "-"}[s.direction_correct]
        print(f"  {s.edition:<13} {s.as_of} -> {s.target}  {s.start_pct:>5.2f}  {s.baseline_pct:>7.2f}  {s.actual_pct:>6.2f} | "
              f"{s.rbi_error_pp:>+8.2f}  {s.no_change_error_pp:>+14.2f}   {direction}")

    _print_summary("All scored projections", summarise(scored))
    covid = {"FSR Jul 2020", "FSR Jan 2021"}
    _print_summary("Excluding the two COVID-era editions", summarise([s for s in scored if s.edition not in covid]))

    print("\n=== Still open (target date not yet reported) ===")
    for line in pending:
        print(f"  {line}")
    print("\n=== Not scored ===")
    for item in record.unscored:
        print(f"  {item['edition']}: {item['reason']}")


if __name__ == "__main__":
    main()
