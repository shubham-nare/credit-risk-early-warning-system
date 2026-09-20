import datetime as dt

import pytest

from credit_risk.analysis import (
    compute_forecast_errors, eclgs_scale_vs_credit_book, naive_linear_trend_projection,
)
from credit_risk.data_loader import (
    load_bajaj_finance, load_iifl_finance, load_macro_conditions, load_nbfc_gnpa,
    load_nbfc_stress_test, load_policy_interventions, load_scb_gnpa,
)


def test_scb_gnpa_data_loads_and_parses_dates():
    data = load_scb_gnpa()
    assert data.actual_gnpa_pct[dt.date(2020, 3, 1)] == 8.5
    assert data.actual_gnpa_pct[dt.date(2021, 3, 1)] == 7.48
    assert len(data.stress_projections) == 2
    assert len(data.known_gaps) == 2


def test_compute_forecast_errors_matches_real_known_miss():
    data = load_scb_gnpa()
    errors = compute_forecast_errors(data)
    assert len(errors) == 4  # 2 projections x 2 scenarios each
    mar21_baseline = next(e for e in errors if e.target_date == "2021-03-01" and e.scenario == "baseline")
    assert mar21_baseline.projected_pct == 12.5
    assert mar21_baseline.actual_pct == 7.48
    assert mar21_baseline.error_pp == pytest.approx(5.02, abs=0.01)
    assert mar21_baseline.relative_error_pct == pytest.approx(67.1, abs=0.5)  # RBI overshot by ~67% of the actual level

    sep21_severe = next(e for e in errors if e.target_date == "2021-09-01" and e.scenario == "severe")
    assert sep21_severe.projected_pct == 14.8
    assert sep21_severe.actual_pct == 6.9
    assert sep21_severe.error_pp == pytest.approx(7.9, abs=0.01)


def test_compute_forecast_errors_raises_on_missing_actual():
    from credit_risk.data_loader import SCBGNPAData, StressProjection
    data = SCBGNPAData(
        actual_gnpa_pct={dt.date(2020, 3, 1): 8.5},
        stress_projections=[StressProjection("test", dt.date(2099, 1, 1), 10.0, 12.0)],
        known_gaps=[],
    )
    with pytest.raises(ValueError, match="no actual GNPA recorded"):
        compute_forecast_errors(data)


def test_naive_trend_is_a_downward_line_and_still_misses_high():
    """The real pre-COVID GNPA points were falling (11.5 -> 10.8 -> 9.3 -> 8.5), so a
    naive trend should also project a further, real decline -- and the test checks it
    against the real actual outcome, not an assumed one."""
    data = load_scb_gnpa()
    proj = naive_linear_trend_projection(data, dt.date(2021, 3, 1))
    assert proj.slope_pp_per_year < 0  # real historical trend was declining
    assert proj.actual_pct == 7.48
    assert len(proj.fitted_from_dates) == 4  # the 4 real pre-COVID points


def test_naive_trend_raises_with_insufficient_points():
    from credit_risk.data_loader import SCBGNPAData
    data = SCBGNPAData({dt.date(2020, 3, 1): 8.5}, [], [])
    with pytest.raises(ValueError, match="at least 2 points"):
        naive_linear_trend_projection(data, dt.date(2021, 3, 1))


def test_macro_conditions_load_real_repo_rate_history():
    macro = load_macro_conditions()
    assert macro.repo_rate_pct[dt.date(2020, 5, 22)] == 4.00
    assert macro.repo_rate_pct[dt.date(2018, 2, 7)] == 6.00
    assert len(macro.repo_rate_pct) == 10


def test_bajaj_finance_gnpa_loads_and_flags_the_recognition_norm_caveat():
    bajaj = load_bajaj_finance()
    assert bajaj.quarterly[dt.date(2019, 3, 1)]["gnpa_pct"] == 1.54
    assert bajaj.quarterly[dt.date(2021, 6, 1)]["gnpa_pct"] == 2.96
    # Bajaj's own book stayed far below the system-wide SCB level throughout
    scb = load_scb_gnpa()
    for date, values in bajaj.quarterly.items():
        if date in scb.actual_gnpa_pct:
            assert values["gnpa_pct"] < scb.actual_gnpa_pct[date]


def test_eclgs_scale_vs_credit_book_uses_real_disclosed_figures():
    policy = load_policy_interventions()
    ctx = eclgs_scale_vs_credit_book(policy)
    assert ctx.eclgs_disbursed_by_date_cr == 100000
    assert ctx.total_credit_book_cr == 9263000
    assert ctx.eclgs_share_of_credit_book_pct == pytest.approx(1.08, abs=0.01)


def test_nbfc_gnpa_primary_series_resolves_the_earlier_march_2019_conflict():
    nbfc = load_nbfc_gnpa()
    # Neither of the two originally-conflicting secondary figures (5.3%, 6.1%) is here for
    # 2019-03: the primary table gives 6.6%, and 6.1% turns out to be 2017-03's real value.
    assert nbfc.fiscal_year_end_gnpa_pct[dt.date(2019, 3, 1)]["value"] == 6.6
    assert nbfc.fiscal_year_end_gnpa_pct[dt.date(2019, 3, 1)]["provenance"] == "primary"
    assert nbfc.fiscal_year_end_gnpa_pct[dt.date(2017, 3, 1)]["value"] == 6.1
    assert nbfc.fiscal_year_end_gnpa_pct[dt.date(2021, 9, 1)]["provenance"] == "secondary_single_source"


def test_nbfc_stress_test_is_a_capital_adequacy_shock_not_a_gnpa_forecast():
    stress = load_nbfc_stress_test()
    assert stress["baseline_sector_crar_pct"] == 19.5
    assert len(stress["shocks"]) == 3
    # CRAR should fall monotonically as the shock gets more severe
    crars = [s["resulting_sector_crar_pct"] for s in stress["shocks"]]
    assert crars == sorted(crars, reverse=True)


def test_iifl_finance_regulatory_forbearance_evidence_is_internally_consistent():
    iifl = load_iifl_finance()
    fb = iifl.regulatory_forbearance_evidence
    assert fb["reported_gnpa_pct"] == iifl.series[dt.date(2020, 9, 1)]["gnpa_pct"]
    assert fb["proforma_gnpa_pct_without_the_order"] - fb["reported_gnpa_pct"] == pytest.approx(
        fb["implied_gnpa_suppression_pp"], abs=0.01
    )
    assert fb["implied_gnpa_suppression_pp"] > 0  # forbearance suppressed, not inflated, reported GNPA
