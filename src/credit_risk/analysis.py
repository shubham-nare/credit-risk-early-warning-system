"""Forecast-error analysis: how far did RBI's own COVID-era stress test miss the real
outcome, and how far off is the simplest honest baseline (a naive linear trend through
the real pre-COVID data) -- both scored against what actually happened.

This deliberately does NOT fit a multi-variate regression "credit risk model": there are
only 4 real SCB GNPA data points before COVID (2018-03 through 2020-03) in this project's
sourced dataset (data/scb_gnpa.yaml), far too few to honestly claim a statistically
validated predictive model. Presenting a regression fit to 4 points as a real model would
be exactly the kind of unearned precision this project exists to avoid (see CONTEXT.md).
Instead, this module computes things that need no such claim: forecast errors that
already happened (arithmetic on real numbers), and one clearly-labeled naive linear trend
offered explicitly as an illustrative reference, not a validated model.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from credit_risk.data_loader import SCBGNPAData


@dataclass(frozen=True)
class ForecastError:
    projection_made_in: str
    target_date: str
    scenario: str  # "baseline" or "severe"
    projected_pct: float
    actual_pct: float
    error_pp: float            # projected minus actual, in percentage points
    relative_error_pct: float  # error_pp as a percentage of the actual outcome


def compute_forecast_errors(data: SCBGNPAData) -> list[ForecastError]:
    """For each RBI stress projection, score it against the real actual outcome at its
    target date. Raises rather than silently skipping if that actual outcome isn't in the
    sourced dataset -- a missing number is a gap to fix, never a number to guess."""
    errors = []
    for proj in data.stress_projections:
        if proj.target_date not in data.actual_gnpa_pct:
            raise ValueError(f"no actual GNPA recorded for {proj.target_date}, cannot score {proj.projection_made_in!r}")
        actual = data.actual_gnpa_pct[proj.target_date]
        for scenario, projected in (("baseline", proj.baseline_pct), ("severe", proj.severe_pct)):
            error_pp = projected - actual
            errors.append(ForecastError(
                projection_made_in=proj.projection_made_in, target_date=proj.target_date.isoformat(),
                scenario=scenario, projected_pct=projected, actual_pct=actual,
                error_pp=round(error_pp, 2), relative_error_pct=round(error_pp / actual * 100, 1),
            ))
    return errors


@dataclass(frozen=True)
class NaiveTrendProjection:
    fitted_from_dates: tuple[str, ...]
    slope_pp_per_year: float
    target_date: str
    projected_pct: float
    actual_pct: float
    error_pp: float


def naive_linear_trend_projection(data: SCBGNPAData, target_date: dt.date,
                                  cutoff: dt.date = dt.date(2020, 3, 31)) -> NaiveTrendProjection:
    """A simple ordinary-least-squares line through only the real actual GNPA points on or
    before `cutoff`, projected forward to `target_date`. Explicitly illustrative: with a
    handful of points this is not a statistically validated model -- it is the simplest
    possible honest baseline, presented as exactly that and no more."""
    pre_cutoff = sorted((d, v) for d, v in data.actual_gnpa_pct.items() if d <= cutoff)
    if len(pre_cutoff) < 2:
        raise ValueError("need at least 2 points on or before the cutoff to fit even a naive trend")
    x0 = pre_cutoff[0][0].toordinal()
    xs = [(d.toordinal() - x0) / 365.25 for d, _ in pre_cutoff]
    ys = [v for _, v in pre_cutoff]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        raise ValueError("all pre-cutoff points fall on the same date; cannot fit a trend")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    target_x = (target_date.toordinal() - x0) / 365.25
    projected = intercept + slope * target_x
    if target_date not in data.actual_gnpa_pct:
        raise ValueError(f"no actual GNPA recorded for {target_date}")
    actual = data.actual_gnpa_pct[target_date]
    return NaiveTrendProjection(
        fitted_from_dates=tuple(d.isoformat() for d, _ in pre_cutoff), slope_pp_per_year=round(slope, 2),
        target_date=target_date.isoformat(), projected_pct=round(projected, 2), actual_pct=actual,
        error_pp=round(projected - actual, 2),
    )


@dataclass(frozen=True)
class PolicyScaleContext:
    eclgs_disbursed_by_date_cr: float
    eclgs_as_of: str
    total_credit_book_cr: float
    credit_book_as_of: str
    eclgs_share_of_credit_book_pct: float


def eclgs_scale_vs_credit_book(policy: dict) -> PolicyScaleContext:
    """A real, if rough, sense of scale for how large COVID-specific credit support was
    relative to the whole banking system -- offered as a plausible contributing factor to
    the forecast miss above, not a proven causal attribution (no causal claim is
    computable from this data alone, and none is made)."""
    eclgs_date, eclgs_amt = sorted(policy["eclgs"]["disbursed_milestones_cr"].items())[0]
    credit_series = policy["aggregate_credit_context"]["non_food_gross_bank_credit_outstanding_cr"]
    credit_date, credit_amt = next(iter(credit_series.items()))
    return PolicyScaleContext(
        eclgs_disbursed_by_date_cr=eclgs_amt, eclgs_as_of=eclgs_date,
        total_credit_book_cr=credit_amt, credit_book_as_of=credit_date,
        eclgs_share_of_credit_book_pct=round(eclgs_amt / credit_amt * 100, 2),
    )
