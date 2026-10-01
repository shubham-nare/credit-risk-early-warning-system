import datetime as dt

import pytest

from credit_risk.data_loader import (
    BaselineProjection, StressTrackRecord, load_scb_gnpa, load_stress_track_record,
)
from credit_risk.track_record import score_track_record, summarise


def test_track_record_loads_all_editions():
    record = load_stress_track_record()
    assert len(record.projections) == 28
    assert record.actual_gnpa_pct[dt.date(2021, 3, 1)] == 7.48
    assert record.actual_gnpa_pct[dt.date(2026, 3, 1)] == 1.8


def test_track_record_agrees_with_the_original_covid_dataset():
    """scb_gnpa.yaml was built earlier from secondary sources; this file is primary. Where
    they overlap they must agree, or one of them is wrong."""
    record, scb = load_stress_track_record(), load_scb_gnpa()
    for p in scb.stress_projections:
        match = next(q for q in record.projections if q.target == p.target_date and q.severe_pct == p.severe_pct)
        assert match.baseline_pct == p.baseline_pct
    for date in (dt.date(2020, 3, 1), dt.date(2021, 3, 1), dt.date(2021, 9, 1)):
        assert record.actual_gnpa_pct[date] == scb.actual_gnpa_pct[date]


def test_scoring_separates_scored_from_pending():
    scored, pending = score_track_record(load_stress_track_record())
    assert len(scored) == 25
    assert len(pending) == 3     # FSR Jun 2025, Dec 2025, Jun 2026: targets not yet reported
    covid = next(s for s in scored if s.edition == "FSR Jul 2020")
    assert covid.rbi_error_pp == pytest.approx(5.02)
    assert covid.no_change_error_pp == pytest.approx(1.02)
    assert covid.direction_correct is False
    assert covid.horizon_months == 12


def test_scoring_raises_when_the_as_of_actual_is_missing():
    record = StressTrackRecord(
        actual_gnpa_pct={dt.date(2021, 3, 1): 7.48},
        projections=[BaselineProjection("X", dt.date(2020, 3, 1), dt.date(2021, 3, 1), 12.5, None)],
        unscored=[],
    )
    with pytest.raises(ValueError, match="as-of date"):
        score_track_record(record)


def test_summary_matches_the_real_result():
    scored, _ = score_track_record(load_stress_track_record())
    s = summarise(scored)
    assert s.n == 25
    assert s.mae_rbi_pp == pytest.approx(2.06, abs=0.01)
    assert s.mae_no_change_pp == pytest.approx(1.70, abs=0.01)
    # On mean error "no change" wins, but it was the closer number only 8 times in 25.
    assert (s.n_no_change_closer, s.n_rbi_closer, s.n_tied) == (8, 17, 0)
    assert (s.n_direction_correct, s.n_direction_scored) == (17, 25)
    # On average too low when GNPA rose, too high when it fell.
    assert s.mean_error_when_gnpa_rose_pp == pytest.approx(-1.75, abs=0.01)
    assert s.mean_error_when_gnpa_fell_pp == pytest.approx(2.23, abs=0.01)
    assert s.longest_overshoot_streak == 15
    assert (s.overshoot_streak_from, s.overshoot_streak_to) == ("FSR Dec 2017", "FSR Dec 2024")


def test_naive_beating_rbi_is_a_covid_result_not_a_general_one():
    """The project's original headline (a naive line beat RBI's stress test) does not
    survive outside the two COVID-era editions: there, RBI's baseline was closer than
    'no change' 17 times out of 23 and the two mean errors are within 0.05pp."""
    scored, _ = score_track_record(load_stress_track_record())
    s = summarise([x for x in scored if x.edition not in ("FSR Jul 2020", "FSR Jan 2021")])
    assert s.n == 23
    assert s.n_rbi_closer == 17
    assert abs(s.mae_rbi_pp - s.mae_no_change_pp) < 0.05
    # But the baseline still called for moves a third the size of what happened.
    assert s.mean_abs_predicted_change_pp == pytest.approx(0.57, abs=0.01)
    assert s.mean_abs_actual_change_pp == pytest.approx(1.77, abs=0.01)
    assert s.error_vs_actual_change_corr == pytest.approx(-0.95, abs=0.01)


def test_direction_is_none_when_no_change_was_projected():
    record = StressTrackRecord(
        actual_gnpa_pct={dt.date(2020, 3, 1): 5.0, dt.date(2021, 3, 1): 6.0},
        projections=[BaselineProjection("X", dt.date(2020, 3, 1), dt.date(2021, 3, 1), 5.0, None)],
        unscored=[],
    )
    scored, _ = score_track_record(record)
    assert scored[0].direction_correct is None
