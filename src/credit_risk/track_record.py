"""Scores every RBI stress-test baseline for system GNPA (Dec 2014 onward) against what
actually happened, and against the simplest possible benchmark: "no change" -- GNPA stays
where it was on the date the projection was made.

This generalises analysis.compute_forecast_errors, which scored only the two COVID-era
editions. The question it answers is whether the COVID miss was a one-off or a pattern.

Two cautions built into how results are reported:
  - RBI calls these scenario results, not forecasts (see the data file's header).
  - Projections overlap in time (an edition every six months, each looking a year or more
    ahead), so the scored errors are not independent. The sign-test p-value is therefore
    indicative only and overstates significance; counts and streaks are the honest summary.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from credit_risk.data_loader import StressTrackRecord
from credit_risk.standstill import _sign_test_p


@dataclass(frozen=True)
class ScoredProjection:
    edition: str
    as_of: str
    target: str
    horizon_months: int
    start_pct: float              # actual GNPA on the as-of date
    baseline_pct: float
    actual_pct: float
    rbi_error_pp: float           # baseline minus actual: positive = RBI projected too high
    no_change_error_pp: float     # start minus actual
    predicted_change_pp: float
    actual_change_pp: float
    direction_correct: bool | None   # None when either change is exactly zero


def score_track_record(record: StressTrackRecord) -> tuple[list[ScoredProjection], list[str]]:
    """Returns (scored projections, editions still pending). A projection is pending only
    if its target date has no published actual yet. A missing as-of actual raises: the
    starting point is something RBI itself stated, so its absence is a data-entry gap."""
    scored, pending = [], []
    for p in record.projections:
        if p.as_of not in record.actual_gnpa_pct:
            raise ValueError(f"{p.edition}: no actual GNPA recorded for its as-of date {p.as_of}")
        if p.target not in record.actual_gnpa_pct:
            pending.append(f"{p.edition} -> {p.target.isoformat()[:7]}: baseline {p.baseline_pct}%")
            continue
        start, actual = record.actual_gnpa_pct[p.as_of], record.actual_gnpa_pct[p.target]
        predicted_change, actual_change = round(p.baseline_pct - start, 2), round(actual - start, 2)
        direction = None if 0 in (predicted_change, actual_change) else (predicted_change > 0) == (actual_change > 0)
        scored.append(ScoredProjection(
            p.edition, p.as_of.isoformat()[:7], p.target.isoformat()[:7],
            (p.target.year - p.as_of.year) * 12 + p.target.month - p.as_of.month,
            start, p.baseline_pct, actual, round(p.baseline_pct - actual, 2), round(start - actual, 2),
            predicted_change, actual_change, direction,
        ))
    return scored, pending


@dataclass(frozen=True)
class TrackRecordSummary:
    n: int
    mae_rbi_pp: float
    mae_no_change_pp: float
    n_no_change_closer: int
    n_rbi_closer: int
    n_tied: int
    sign_test_p: float               # indicative only: overlapping horizons are not independent
    n_direction_scored: int
    n_direction_correct: int
    mean_error_when_gnpa_rose_pp: float | None    # negative = RBI projected too low
    mean_error_when_gnpa_fell_pp: float | None
    n_when_rose: int
    n_when_fell: int
    error_vs_actual_change_corr: float
    mean_abs_predicted_change_pp: float   # how big a move RBI's baseline called for, on average
    mean_abs_actual_change_pp: float      # how big the move actually was
    longest_overshoot_streak: int
    overshoot_streak_from: str | None
    overshoot_streak_to: str | None


def summarise(scored: list[ScoredProjection]) -> TrackRecordSummary:
    if len(scored) < 3:
        raise ValueError("too few scored projections to summarise")
    rbi_abs = [abs(s.rbi_error_pp) for s in scored]
    naive_abs = [abs(s.no_change_error_pp) for s in scored]
    naive_closer = sum(n < r for n, r in zip(naive_abs, rbi_abs))
    rbi_closer = sum(r < n for n, r in zip(naive_abs, rbi_abs))
    directional = [s for s in scored if s.direction_correct is not None]
    rose = [s.rbi_error_pp for s in scored if s.actual_change_pp > 0]
    fell = [s.rbi_error_pp for s in scored if s.actual_change_pp < 0]

    best, best_span, run, run_start = 0, (None, None), 0, None
    for s in scored:                 # scored is in publication order
        if s.rbi_error_pp > 0:
            run, run_start = run + 1, run_start or s.edition
            if run > best:
                best, best_span = run, (run_start, s.edition)
        else:
            run, run_start = 0, None

    return TrackRecordSummary(
        n=len(scored), mae_rbi_pp=round(statistics.fmean(rbi_abs), 2),
        mae_no_change_pp=round(statistics.fmean(naive_abs), 2),
        n_no_change_closer=naive_closer, n_rbi_closer=rbi_closer, n_tied=len(scored) - naive_closer - rbi_closer,
        sign_test_p=round(_sign_test_p(naive_closer, naive_closer + rbi_closer), 4),
        n_direction_scored=len(directional), n_direction_correct=sum(s.direction_correct for s in directional),
        mean_error_when_gnpa_rose_pp=round(statistics.fmean(rose), 2) if rose else None,
        mean_error_when_gnpa_fell_pp=round(statistics.fmean(fell), 2) if fell else None,
        n_when_rose=len(rose), n_when_fell=len(fell),
        error_vs_actual_change_corr=round(statistics.correlation(
            [s.rbi_error_pp for s in scored], [s.actual_change_pp for s in scored]), 2),
        mean_abs_predicted_change_pp=round(statistics.fmean(abs(s.predicted_change_pp) for s in scored), 2),
        mean_abs_actual_change_pp=round(statistics.fmean(abs(s.actual_change_pp) for s in scored), 2),
        longest_overshoot_streak=best, overshoot_streak_from=best_span[0], overshoot_streak_to=best_span[1],
    )

