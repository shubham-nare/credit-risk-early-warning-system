"""One-quarter-ahead forecasts of each lender's reported gross NPA ratio, built to be
PRE-REGISTERED: written down and committed before the quarter's results are published,
then scored against what the lenders report.

The candidate methods are deliberately few and simple, and all are fixed here in code
before any forecast is scored:

  no_change        next quarter = this quarter                      (the benchmark)
  own_drift        repeat the lender's own last quarterly % change
  seasonal         repeat the lender's % change in the same quarter a year ago
  sector_drift     apply the average % change across all lenders, estimated on past quarters
  pooled_ar1       sector drift plus a pooled response to the lender's own last change
  pooled_ar1_seas  the above plus a pooled response to its change a year ago

Changes are modelled in logs (percentage changes), because GNPA levels differ several-fold
across lenders. Pooled coefficients are re-estimated at each backtest date on earlier
quarters only, so the backtest never sees the quarter it is scoring.

Known weakness, stated up front: the history is 13 quarters in which GNPA fell almost
everywhere. Any method that extrapolates that fall will look good in backtest and will be
wrong at a turn in the cycle -- which is exactly the failure this project documents in
RBI's own baselines (track_record.py). The pre-registered scoring is the test of that.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from pathlib import Path

import yaml

from credit_risk.data_loader import DATA_DIR

METHODS = ("no_change", "own_drift", "seasonal", "sector_drift", "pooled_ar1", "pooled_ar1_seas")
BENCHMARK = "no_change"
MIN_HISTORY = 5   # quarters needed before a target so that every method can be computed


@dataclass(frozen=True)
class QuarterlyPanel:
    quarters: list[str]                 # sorted "YYYY-MM"
    series: dict[str, list[float]]      # symbol -> GNPA % aligned to `quarters`
    names: dict[str, str]


def load_quarterly_panel(path: Path = DATA_DIR / "quarterly_gnpa.yaml",
                         exclude: tuple[str, ...] = ()) -> QuarterlyPanel:
    """Loads lenders that have a GNPA figure for every quarter in the file; a lender with a
    gap is dropped rather than interpolated."""
    raw = yaml.safe_load(open(path, encoding="utf-8"))["lenders"]
    quarters = sorted({q for entry in raw.values() for q in entry["quarters"]})
    series, names = {}, {}
    for symbol, entry in raw.items():
        if symbol in exclude:
            continue
        values = [entry["quarters"].get(q, {}).get("gnpa") for q in quarters]
        if any(v is None or v <= 0 for v in values):
            continue
        series[symbol], names[symbol] = values, entry["name"]
    return QuarterlyPanel(quarters, series, names)


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting, for the tiny normal-equation systems here."""
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular system: regressors are collinear")
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(col + 1, n):
            factor = a[row][col] / a[col][col]
            a[row] = [x - factor * y for x, y in zip(a[row], a[col])]
    solution = [0.0] * n
    for row in range(n - 1, -1, -1):
        solution[row] = (a[row][n] - sum(a[row][c] * solution[c] for c in range(row + 1, n))) / a[row][row]
    return solution


def _ols(rows: list[list[float]], targets: list[float]) -> list[float]:
    k = len(rows[0])
    xtx = [[sum(r[i] * r[j] for r in rows) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * t for r, t in zip(rows, targets)) for i in range(k)]
    return _solve(xtx, xty)


def _dlog(values: list[float], k: int) -> float:
    return math.log(values[k] / values[k - 1])


def _features(values: list[float], k: int, method: str) -> list[float]:
    """Regressors for the log change into quarter index k, using only quarters before k."""
    if method == "sector_drift":
        return [1.0]
    if method == "pooled_ar1":
        return [1.0, _dlog(values, k - 1)]
    return [1.0, _dlog(values, k - 1), _dlog(values, k - 4)]


def _fit(panel: QuarterlyPanel, method: str, before: int) -> list[float]:
    """Pooled OLS coefficients using only targets strictly before quarter index `before`."""
    rows, targets = [], []
    for values in panel.series.values():
        for j in range(MIN_HISTORY, before):
            rows.append(_features(values, j, method))
            targets.append(_dlog(values, j))
    if len(rows) < 10 * len(rows[0] if rows else [0]):
        raise ValueError(f"too little history to fit {method} before quarter index {before}")
    return _ols(rows, targets)


def predict(panel: QuarterlyPanel, symbol: str, k: int, method: str, coefs: list[float] | None = None) -> float:
    """Forecast of `symbol`'s GNPA at quarter index k (k may be len(quarters), i.e. the
    first quarter not yet in the data), from data before k only."""
    values = panel.series[symbol]
    last = values[k - 1]
    if method == "no_change":
        return last
    if method == "own_drift":
        return last * values[k - 1] / values[k - 2]
    if method == "seasonal":
        return last * values[k - 4] / values[k - 5]
    coefs = coefs if coefs is not None else _fit(panel, method, k)
    return last * math.exp(sum(c * x for c, x in zip(coefs, _features(values, k, method))))


@dataclass(frozen=True)
class BacktestScore:
    method: str
    n: int
    mae_pp: float                    # PRIMARY metric: mean absolute error in percentage points
    median_abs_rel_error_pct: float  # secondary: scale-free
    share_closer_than_benchmark_pct: float | None


def backtest(panel: QuarterlyPanel, first_target: int | None = None) -> tuple[list[BacktestScore], dict[str, list[float]]]:
    """Expanding-window backtest. For each target quarter from `first_target` on, every
    method forecasts every lender using earlier quarters only. Returns the scores and, per
    method, the log residuals (log actual - log forecast) for building intervals."""
    first_target = first_target if first_target is not None else MIN_HISTORY + 2
    n_quarters = len(panel.quarters)
    if first_target >= n_quarters:
        raise ValueError("no quarters left to backtest on")
    abs_err = {m: [] for m in METHODS}
    rel_err = {m: [] for m in METHODS}
    residuals = {m: [] for m in METHODS}
    for k in range(first_target, n_quarters):
        fitted = {m: _fit(panel, m, k) for m in ("sector_drift", "pooled_ar1", "pooled_ar1_seas")}
        for symbol, values in panel.series.items():
            for m in METHODS:
                forecast = predict(panel, symbol, k, m, fitted.get(m))
                abs_err[m].append(abs(forecast - values[k]))
                rel_err[m].append(abs(forecast - values[k]) / values[k] * 100)
                residuals[m].append(math.log(values[k] / forecast))
    scores = []
    for m in METHODS:
        closer = None
        if m != BENCHMARK:
            wins = sum(a < b for a, b in zip(abs_err[m], abs_err[BENCHMARK]))
            closer = round(wins / len(abs_err[m]) * 100, 1)
        scores.append(BacktestScore(m, len(abs_err[m]), round(statistics.fmean(abs_err[m]), 4),
                                    round(statistics.median(rel_err[m]), 2), closer))
    return scores, residuals


def select_method(scores: list[BacktestScore]) -> str:
    """The pre-declared rule: lowest backtest MAE in percentage points wins; ties go to the
    simpler method (earlier in METHODS)."""
    return min(scores, key=lambda s: (s.mae_pp, METHODS.index(s.method))).method


@dataclass(frozen=True)
class Forecast:
    symbol: str
    name: str
    last_quarter: str
    last_gnpa: float
    forecast_gnpa: float
    benchmark_gnpa: float
    interval_80: tuple[float, float]   # from the method's own backtest residuals (10th-90th percentile)


def make_forecasts(panel: QuarterlyPanel, method: str, residuals: list[float]) -> list[Forecast]:
    """Forecasts the first quarter after the data ends, for every lender in the panel."""
    k = len(panel.quarters)
    coefs = _fit(panel, method, k) if method in ("sector_drift", "pooled_ar1", "pooled_ar1_seas") else None
    deciles = statistics.quantiles(residuals, n=10)
    low, high = math.exp(deciles[0]), math.exp(deciles[-1])
    forecasts = []
    for symbol in panel.series:
        point = predict(panel, symbol, k, method, coefs)
        forecasts.append(Forecast(
            symbol, panel.names[symbol], panel.quarters[-1], panel.series[symbol][-1],
            round(point, 2), round(predict(panel, symbol, k, BENCHMARK), 2),
            (round(point * low, 2), round(point * high, 2)),
        ))
    return forecasts
