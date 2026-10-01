"""Did the stock market price the proforma number or the reported one?

On the day a lender announced its Dec-2020 quarter, the market learned two asset-quality
figures at once: reported GNPA (frozen by the standstill, usually flattering) and proforma
GNPA. If investors read through to the proforma figure, lenders revealing more hidden
stress should have done worse than the bank index around that day; if they anchored on the
reported figure, there should be no such relationship.

What this can and cannot show:
  - It is a cross-section of about twenty lenders on different days. Small.
  - A results-day return reflects the whole release (profit, margins, guidance), not just
    asset quality, and what matters is the surprise against expectations, which is not
    measured here. A weak or null result is therefore NOT evidence the market was fooled.
  - A clear negative relationship would be evidence it was not.
"""
from __future__ import annotations

import csv
import datetime as dt
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

import yaml

from credit_risk.data_loader import DATA_DIR, StandstillPanel
from credit_risk.standstill import STANDSTILL_DATE


@dataclass(frozen=True)
class PriceTable:
    dates: list[dt.date]                    # trading days, ascending
    closes: dict[str, list[float | None]]   # ticker -> adjusted close aligned to `dates`


def load_prices(path: Path = DATA_DIR / "event_prices.csv") -> PriceTable:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    tickers = rows[0][1:]
    dates = [dt.date.fromisoformat(r[0]) for r in rows[1:]]
    closes = {t: [float(r[i + 1]) if r[i + 1] else None for r in rows[1:]] for i, t in enumerate(tickers)}
    return PriceTable(dates, closes)


def load_results_dates(path: Path = DATA_DIR / "q3fy21_results_dates.yaml") -> tuple[dict[str, dict], str]:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    return raw["dates"], raw["benchmark_ticker"]


def window_return_pct(prices: PriceTable, ticker: str, event_date: dt.date) -> float:
    """Return from the close of the last trading day BEFORE the event to the close of the
    trading day AFTER the first trading day on or after it. Covers an announcement made
    during hours, after hours, or over a weekend."""
    day = next((i for i, d in enumerate(prices.dates) if d >= event_date), None)
    if day is None or day == 0 or day + 1 >= len(prices.dates):
        raise ValueError(f"{ticker}: price history does not cover the window around {event_date}")
    before, after = prices.closes[ticker][day - 1], prices.closes[ticker][day + 1]
    if before is None or after is None:
        raise ValueError(f"{ticker}: missing close around {event_date}")
    return (after / before - 1) * 100


@dataclass(frozen=True)
class EventRow:
    lender: str
    event_date: str
    date_basis: str
    hidden_pp: float
    hidden_share_pct: float
    stock_return_pct: float
    index_return_pct: float
    abnormal_return_pct: float


@dataclass(frozen=True)
class MarketTestResult:
    rows: list[EventRow]
    n: int
    rank_corr_hidden_pp: float
    p_hidden_pp: float                 # two-sided Monte Carlo permutation p, seeded
    rank_corr_hidden_share: float
    p_hidden_share: float
    mean_abnormal_high_hidden_pct: float   # lenders above the median hidden stress (pp)
    mean_abnormal_low_hidden_pct: float


def _permutation_p(xs: list[float], ys: list[float], draws: int = 100_000, seed: int = 0) -> float:
    """Two-sided permutation p-value for a Spearman correlation: how often does shuffling
    one side give a correlation at least as large in magnitude? Seeded, so reproducible."""
    observed = abs(statistics.correlation(xs, ys, method="ranked"))
    rng, shuffled, hits = random.Random(seed), ys[:], 0
    for _ in range(draws):
        rng.shuffle(shuffled)
        if abs(statistics.correlation(xs, shuffled, method="ranked")) >= observed - 1e-12:
            hits += 1
    return hits / draws


def results_day_test(panel: StandstillPanel, prices: PriceTable, dates: dict[str, dict], benchmark: str,
                     exclude: tuple[str, ...] = (), draws: int = 100_000) -> MarketTestResult:
    rows = []
    for key, lender in panel.lenders.items():
        if key in exclude or key not in dates:
            continue
        q = lender.quarters.get(STANDSTILL_DATE)
        if q is None or q.reported_gnpa is None or q.proforma_gnpa is None:
            continue
        event = dt.date.fromisoformat(dates[key]["date"])
        stock = window_return_pct(prices, lender.ticker, event)
        index = window_return_pct(prices, benchmark, event)
        hidden = q.proforma_gnpa - q.reported_gnpa
        rows.append(EventRow(lender.name, event.isoformat(), dates[key]["basis"], round(hidden, 2),
                             round(hidden / q.proforma_gnpa * 100, 1), round(stock, 2), round(index, 2),
                             round(stock - index, 2)))
    if len(rows) < 6:
        raise ValueError(f"only {len(rows)} lenders have a results date, prices and a proforma figure")
    abnormal = [r.abnormal_return_pct for r in rows]
    hidden_pp, hidden_share = [r.hidden_pp for r in rows], [r.hidden_share_pct for r in rows]
    median = statistics.median(hidden_pp)
    high = [r.abnormal_return_pct for r in rows if r.hidden_pp > median]
    low = [r.abnormal_return_pct for r in rows if r.hidden_pp <= median]
    return MarketTestResult(
        rows=sorted(rows, key=lambda r: r.hidden_pp, reverse=True), n=len(rows),
        rank_corr_hidden_pp=round(statistics.correlation(hidden_pp, abnormal, method="ranked"), 2),
        p_hidden_pp=round(_permutation_p(hidden_pp, abnormal, draws), 4),
        rank_corr_hidden_share=round(statistics.correlation(hidden_share, abnormal, method="ranked"), 2),
        p_hidden_share=round(_permutation_p(hidden_share, abnormal, draws), 4),
        mean_abnormal_high_hidden_pct=round(statistics.fmean(high), 2),
        mean_abnormal_low_hidden_pct=round(statistics.fmean(low), 2),
    )
