import hashlib
import math

import pytest
import yaml

from credit_risk.data_loader import DATA_DIR

from credit_risk.forecast import (
    BENCHMARK, METHODS, QuarterlyPanel, _fit, _ols, _solve, backtest, load_quarterly_panel,
    make_forecasts, predict, select_method,
)


def _synthetic_panel(rates: dict[str, float], n_quarters: int = 13) -> QuarterlyPanel:
    """Each lender's GNPA changes by a constant percentage every quarter."""
    quarters = [f"q{i:02d}" for i in range(n_quarters)]
    series = {name: [2.0 * (1 + rate) ** i for i in range(n_quarters)] for name, rate in rates.items()}
    return QuarterlyPanel(quarters, series, {name: name for name in rates})


def test_solver_and_ols_recover_known_coefficients():
    assert _solve([[2.0, 1.0], [1.0, 3.0]], [5.0, 10.0]) == pytest.approx([1.0, 3.0])
    rows = [[1.0, x] for x in (0.0, 1.0, 2.0, 3.0)]
    assert _ols(rows, [1.0 + 2.0 * r[1] for r in rows]) == pytest.approx([1.0, 2.0])
    with pytest.raises(ValueError, match="singular"):
        _solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_simple_methods_do_what_they_say():
    panel = QuarterlyPanel([f"q{i}" for i in range(7)], {"A": [4.0, 4.0, 2.0, 2.0, 2.0, 2.0, 1.0]}, {"A": "A"})
    assert predict(panel, "A", 7, "no_change") == 1.0
    assert predict(panel, "A", 7, "own_drift") == pytest.approx(0.5)    # last change was a halving
    assert predict(panel, "A", 6, "seasonal") == pytest.approx(1.0)     # change four quarters earlier was a halving


def test_sector_drift_recovers_a_common_trend_exactly():
    panel = _synthetic_panel({name: -0.05 for name in "ABCDEFGHIJ"})
    k = len(panel.quarters)
    assert _fit(panel, "sector_drift", k) == pytest.approx([math.log(0.95)])
    assert predict(panel, "A", k, "sector_drift") == pytest.approx(2.0 * 0.95 ** 13)
    assert predict(panel, "A", k, "no_change") == pytest.approx(2.0 * 0.95 ** 12)


def test_pooled_fit_refuses_collinear_regressors():
    """With a perfectly constant trend the lag-1 and lag-4 changes are identical; the fit
    must raise rather than return arbitrary coefficients."""
    panel = _synthetic_panel({name: -0.05 for name in "ABCDEFGHIJ"})
    with pytest.raises(ValueError, match="singular"):
        _fit(panel, "pooled_ar1_seas", len(panel.quarters))


def test_forecast_for_a_quarter_never_uses_that_quarter():
    """Tripling every lender's final-quarter GNPA must leave the forecast OF that quarter
    unchanged, for every method -- including the pooled ones, which are fitted on earlier
    quarters only."""
    base = load_quarterly_panel(exclude=("BAJFINANCE",))
    shocked = QuarterlyPanel(base.quarters, {k: v[:-1] + [v[-1] * 3] for k, v in base.series.items()}, base.names)
    last = len(base.quarters) - 1
    for method in METHODS:
        for symbol in ("HDFCBANK", "PNB", "RBLBANK"):
            assert predict(base, symbol, last, method) == pytest.approx(predict(shocked, symbol, last, method))


def test_loader_drops_lenders_with_gaps(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text(
        "lenders:\n"
        "  FULL: {name: Full, quarters: {'2025-03': {gnpa: 2.0}, '2025-06': {gnpa: 1.9}}}\n"
        "  GAP:  {name: Gap,  quarters: {'2025-03': {gnpa: 2.0}}}\n", encoding="utf-8")
    panel = load_quarterly_panel(path)
    assert list(panel.series) == ["FULL"]
    assert panel.quarters == ["2025-03", "2025-06"]


def test_real_backtest_selects_sector_drift_and_beats_no_change():
    panel = load_quarterly_panel(exclude=("BAJFINANCE",))
    assert len(panel.series) == 35
    assert (panel.quarters[0], panel.quarters[-1]) == ("2023-06", "2026-06")
    scores, residuals = backtest(panel)
    by_method = {s.method: s for s in scores}
    assert by_method["no_change"].n == 210            # 6 target quarters x 35 lenders
    assert by_method["no_change"].mae_pp == pytest.approx(0.1917, abs=0.0005)
    assert by_method["sector_drift"].mae_pp == pytest.approx(0.1497, abs=0.0005)
    assert select_method(scores) == "sector_drift"
    # Not every extrapolation helps: repeating a lender's own last change is no better than no change.
    assert by_method["own_drift"].mae_pp > by_method["no_change"].mae_pp


def test_real_forecasts_are_ordered_and_bracketed():
    panel = load_quarterly_panel(exclude=("BAJFINANCE",))
    scores, residuals = backtest(panel)
    method = select_method(scores)
    for f in make_forecasts(panel, method, residuals[method]):
        assert f.benchmark_gnpa == f.last_gnpa        # the benchmark is literally no change
        assert f.interval_80[0] < f.forecast_gnpa < f.interval_80[1]
        assert math.isfinite(f.forecast_gnpa) and f.forecast_gnpa > 0
    assert BENCHMARK == "no_change"


PREREG = DATA_DIR.parent / "forecasts" / "2026-09_preregistration.yaml"


def test_preregistration_hash_matches_its_input_data():
    """The hash was taken on Windows, where the working copy has CRLF line endings while
    git stores LF. The pre-registration file is never edited, so the check normalises to
    CRLF instead: same content, the line endings the hash was actually taken over."""
    recorded = yaml.safe_load(open(PREREG, encoding="utf-8"))["input_data"]["sha256"]
    raw = (DATA_DIR / "quarterly_gnpa.yaml").read_bytes()
    as_crlf = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert hashlib.sha256(as_crlf).hexdigest() == recorded


def test_preregistered_forecasts_are_exactly_what_the_code_produces():
    prereg = yaml.safe_load(open(PREREG, encoding="utf-8"))
    panel = load_quarterly_panel(exclude=tuple(prereg["excluded_lenders"]))
    scores, residuals = backtest(panel)
    method = select_method(scores)
    assert method == prereg["method"]["selected"]
    recomputed = {f.symbol: f for f in make_forecasts(panel, method, residuals[method])}
    assert len(prereg["forecasts"]) == len(recomputed) == 35
    for entry in prereg["forecasts"]:
        f = recomputed[entry["symbol"]]
        assert (f.forecast_gnpa, f.benchmark_gnpa, list(f.interval_80)) == (
            entry["forecast_gnpa"], entry["benchmark_gnpa"], entry["interval_80"])
