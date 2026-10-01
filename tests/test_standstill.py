import datetime as dt
import hashlib
from pathlib import Path

import pytest
import yaml

from credit_risk.data_loader import DATA_DIR, load_standstill_panel
from credit_risk.standstill import (
    _sign_flip_p, _sign_test_p, catch_up_test, hidden_stress, system_standstill_context,
)

FILINGS_DIR = DATA_DIR.parent / "sources" / "filings"
DEC20, MAR21 = dt.date(2020, 12, 1), dt.date(2021, 3, 1)


def test_panel_loads_with_every_quarter_traceable_to_a_source():
    panel = load_standstill_panel()
    assert len(panel.lenders) == 23
    kotak = panel.lenders["kotak_mahindra_bank"]
    assert kotak.quarters[DEC20].reported_gnpa == 2.26
    assert kotak.quarters[DEC20].proforma_gnpa == 3.27
    assert kotak.quarters[DEC20].provenance == "primary"
    # PNB's own filing was never located: it must not be passed off as primary.
    assert panel.lenders["pnb"].quarters[DEC20].provenance == "secondary"


def _write_panel(tmp_path: Path, quarter: dict) -> Path:
    path = tmp_path / "panel.yaml"
    path.write_text(yaml.safe_dump({
        "standstill": {}, "system_proforma": {}, "known_gaps": [],
        "lenders": {"x": {"name": "X", "kind": "private_bank", "ticker": "X.NS",
                          "sources": {"a": {"provenance": "primary", "doc": "d"}},
                          "quarters": {"2020-12": quarter}}},
    }), encoding="utf-8")
    return path


def test_loader_raises_on_unknown_source_key(tmp_path):
    with pytest.raises(ValueError, match="unknown source"):
        load_standstill_panel(_write_panel(tmp_path, {"reported_gnpa": 1.0, "src": "missing"}))


def test_loader_raises_when_no_source_is_cited(tmp_path):
    with pytest.raises(ValueError, match="no source cited"):
        load_standstill_panel(_write_panel(tmp_path, {"reported_gnpa": 1.0}))


def test_loader_raises_when_proforma_is_below_reported(tmp_path):
    with pytest.raises(ValueError, match="below reported"):
        load_standstill_panel(_write_panel(tmp_path, {"reported_gnpa": 2.0, "proforma_gnpa": 1.5, "src": "a"}))


def test_downloaded_filings_match_their_recorded_hashes():
    """sources/filings/ is gitignored, so this only checks files that are present --
    but for those, the bytes must be the ones the numbers were read from."""
    panel = load_standstill_panel()
    checked = 0
    for lender in panel.lenders.values():
        for source in lender.sources.values():
            if source.file is None or not (FILINGS_DIR / source.file).exists():
                continue
            digest = hashlib.sha256((FILINGS_DIR / source.file).read_bytes()).hexdigest()
            assert digest.startswith(source.sha256_16), f"{source.file} differs from the recorded download"
            checked += 1
    if checked == 0:
        pytest.skip("no filings downloaded locally")


def test_hidden_stress_ranks_bandhan_first_and_skips_lenders_without_proforma():
    panel = load_standstill_panel()
    dec = hidden_stress(panel)
    assert dec[0].lender == "Bandhan Bank"
    assert dec[0].hidden_pp == pytest.approx(6.0)
    assert len(dec) == 23
    # Most lenders have no Sep-2020 proforma on record (Bandhan, IDFC First, PNB, ...): skipped, not guessed.
    sep = hidden_stress(panel, dt.date(2020, 9, 1))
    assert len(sep) == 9
    assert "Bandhan Bank" not in {h.lender for h in sep}


def test_catch_up_test_matches_the_real_result():
    result = catch_up_test(load_standstill_panel())
    assert result.n == 22    # Shriram Transport has no Mar-2021 figure on record
    assert result.mae_reported_pp == pytest.approx(1.54, abs=0.01)
    assert result.mae_proforma_pp == pytest.approx(0.79, abs=0.01)
    # Not a clean sweep: reported was the closer number for six lenders, all with large
    # corporate books.
    assert result.n_proforma_closer == 16
    assert {r.lender for r in result.rows if r.reported_error_pp < r.proforma_error_pp} == {
        "Axis Bank", "State Bank of India", "Bank of Baroda", "Union Bank of India", "Yes Bank", "Karur Vysya Bank"}
    # Neither exact test clears 0.05 on the full panel. The 11-lender pilot gave 0.39pp and
    # a permutation p of 0.025; doubling the sample weakened it, and that is the result.
    assert result.sign_test_p == pytest.approx(0.0525, abs=0.0005)
    assert result.permutation_test_p == pytest.approx(0.0865, abs=0.0005)
    assert result.n_outcome_below_proforma == 18


def test_catch_up_direction_survives_dropping_the_largest_outlier():
    result = catch_up_test(load_standstill_panel(), exclude=("bandhan_bank",))
    assert result.n == 21
    assert result.mae_proforma_pp < result.mae_reported_pp
    assert result.n_proforma_closer == 15


def test_catch_up_test_refuses_to_score_too_few_lenders():
    panel = load_standstill_panel()
    keep = ("hdfc_bank", "sbi")
    with pytest.raises(ValueError, match="too few"):
        catch_up_test(panel, exclude=tuple(k for k in panel.lenders if k not in keep))


def test_exact_small_sample_tests_against_hand_computed_values():
    assert _sign_test_p(9, 11) == pytest.approx(2 * (55 + 11 + 1) / 2048)
    assert _sign_test_p(5, 10) == 1.0
    # All differences positive: only the all-plus and all-minus assignments are as extreme.
    assert _sign_flip_p([1.0, 2.0, 3.0]) == pytest.approx(2 / 8)
    # {1, -1}: every assignment sums to 0 or +-2, so all four are at least as extreme as 0.
    assert _sign_flip_p([1.0, -1.0]) == 1.0


def test_system_context_shows_standstill_cannot_explain_rbi_miss():
    ctx = system_standstill_context(load_standstill_panel(), rbi_baseline_pct=12.5, rbi_baseline_target="2021-03")
    assert ctx.hidden_share_of_proforma_pct == pytest.approx(14.9, abs=0.1)   # (8.7 - 7.4) / 8.7
    assert ctx.hidden_pp == pytest.approx(1.24, abs=0.01)
    # Even counting every unreported rupee, the system sat 4.2pp below RBI's baseline.
    assert ctx.baseline_minus_proforma_pp == pytest.approx(4.2, abs=0.01)
