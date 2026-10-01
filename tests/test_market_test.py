import datetime as dt

import pytest

from credit_risk.data_loader import load_standstill_panel
from credit_risk.market_test import (
    PriceTable, _permutation_p, load_prices, load_results_dates, results_day_test, window_return_pct,
)


def _table() -> PriceTable:
    # Mon 4 Jan .. Fri 8 Jan 2021, then Mon 11 Jan: a weekend sits between index 4 and 5.
    dates = [dt.date(2021, 1, d) for d in (4, 5, 6, 7, 8, 11, 12)]
    return PriceTable(dates, {"X": [100.0, 100.0, 110.0, 121.0, 121.0, 60.5, 60.5], "GAP": [1.0, None, 1.0, 1.0, 1.0, 1.0, 1.0]})


def test_window_runs_from_the_close_before_to_the_close_after():
    table = _table()
    # Announced Wed 6 Jan: close of 5 Jan (100) to close of 7 Jan (121).
    assert window_return_pct(table, "X", dt.date(2021, 1, 6)) == pytest.approx(21.0)
    # Announced Sat 9 Jan: first trading day after is Mon 11 Jan; close of Fri 8 (121) to close of Tue 12 (60.5).
    assert window_return_pct(table, "X", dt.date(2021, 1, 9)) == pytest.approx(-50.0)


def test_window_raises_when_history_does_not_cover_it():
    table = _table()
    with pytest.raises(ValueError, match="does not cover"):
        window_return_pct(table, "X", dt.date(2021, 1, 12))   # no trading day after
    with pytest.raises(ValueError, match="does not cover"):
        window_return_pct(table, "X", dt.date(2021, 1, 4))    # no trading day before
    with pytest.raises(ValueError, match="missing close"):
        window_return_pct(table, "GAP", dt.date(2021, 1, 6))


def test_permutation_p_is_small_for_a_perfect_ranking_and_reproducible():
    xs = [float(i) for i in range(10)]
    assert _permutation_p(xs, [-x for x in xs], draws=20_000) < 0.001
    noisy = [3.0, 1.0, 4.0, 1.5, 5.0, 9.0, 2.0, 6.0, 5.5, 3.5]
    assert _permutation_p(xs, noisy, draws=5_000) == _permutation_p(xs, noisy, draws=5_000)


def test_every_panel_lender_has_a_results_date_and_prices():
    panel, prices = load_standstill_panel(), load_prices()
    dates, benchmark = load_results_dates()
    assert set(dates) == set(panel.lenders)
    assert benchmark in prices.closes
    for lender in panel.lenders.values():
        assert lender.ticker in prices.closes
    # Bandhan fell hard over its results window; this pins the price data and the window logic together.
    assert window_return_pct(prices, "BANDHANBNK.NS", dt.date(2021, 1, 21)) == pytest.approx(-12.70, abs=0.05)


def test_real_market_test_result():
    panel, prices = load_standstill_panel(), load_prices()
    dates, benchmark = load_results_dates()
    result = results_day_test(panel, prices, dates, benchmark, draws=20_000)
    assert result.n == 23
    # More hidden stress revealed, worse relative performance.
    assert result.rank_corr_hidden_pp == pytest.approx(-0.52, abs=0.01)
    assert result.p_hidden_pp < 0.03
    # The second measure (hidden stress as a share of proforma) shows no clear relationship.
    assert result.rank_corr_hidden_share == pytest.approx(-0.18, abs=0.01)
    assert result.p_hidden_share > 0.3
    assert result.mean_abnormal_high_hidden_pct < 0 < result.mean_abnormal_low_hidden_pct


def test_market_test_refuses_too_few_lenders():
    panel, prices = load_standstill_panel(), load_prices()
    dates, benchmark = load_results_dates()
    keep = ("hdfc_bank", "sbi", "pnb")
    with pytest.raises(ValueError, match="only 3 lenders"):
        results_day_test(panel, prices, dates, benchmark, exclude=tuple(k for k in panel.lenders if k not in keep))
