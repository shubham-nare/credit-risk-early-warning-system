"""Lender-level analysis of the Supreme Court NPA standstill (Sep 2020 - Mar 2021).

While the order was in force, lenders published two asset-quality numbers: the reported
ratio (frozen by the order) and a proforma ratio (what it would have been otherwise).
When the order was vacated on 23 Mar 2021, reported figures had to catch up. That makes
this a natural experiment with a checkable answer: of the two numbers a lender published
in December 2020, which one told you where it would actually be in March 2021?

Everything here is arithmetic on data/standstill_panel.yaml. The panel is small (see its
`known_gaps`) and was not randomly sampled, so every result carries its n, and the
significance tests are exact small-sample tests rather than anything asymptotic.
"""
from __future__ import annotations

import datetime as dt
import itertools
import math
import random
import statistics
from dataclasses import dataclass

from credit_risk.data_loader import StandstillPanel

STANDSTILL_DATE = dt.date(2020, 12, 1)
OUTCOME_DATE = dt.date(2021, 3, 1)


@dataclass(frozen=True)
class HiddenStress:
    lender: str
    reported_gnpa: float
    proforma_gnpa: float
    hidden_pp: float                      # proforma minus reported
    hidden_share_of_proforma_pct: float   # share of the lender's proforma bad loans left unreported
    provenance: str


def hidden_stress(panel: StandstillPanel, date: dt.date = STANDSTILL_DATE) -> list[HiddenStress]:
    """Per lender, how much gross NPA the standstill kept off the reported number at
    `date`. Lenders with no proforma disclosure at that date are skipped, not guessed."""
    rows = []
    for lender in panel.lenders.values():
        q = lender.quarters.get(date)
        if q is None or q.reported_gnpa is None or q.proforma_gnpa is None:
            continue
        hidden = q.proforma_gnpa - q.reported_gnpa
        rows.append(HiddenStress(lender.name, q.reported_gnpa, q.proforma_gnpa, round(hidden, 2),
                                 round(hidden / q.proforma_gnpa * 100, 1), q.provenance))
    return sorted(rows, key=lambda r: r.hidden_pp, reverse=True)


@dataclass(frozen=True)
class CatchUpRow:
    lender: str
    reported_gnpa: float
    proforma_gnpa: float
    outcome_gnpa: float
    reported_error_pp: float   # |outcome - reported at the standstill date|
    proforma_error_pp: float   # |outcome - proforma at the standstill date|
    provenance: str            # "primary" only if both quarters are


@dataclass(frozen=True)
class CatchUpResult:
    standstill_date: str
    outcome_date: str
    rows: list[CatchUpRow]
    n: int
    mae_reported_pp: float
    mae_proforma_pp: float
    n_proforma_closer: int
    sign_test_p: float               # exact two-sided binomial: proforma closer in k of n
    permutation_test_p: float        # exact two-sided sign-flip test on paired error differences
    n_outcome_below_proforma: int
    rank_corr_hidden_vs_rise: float  # Spearman: hidden stress vs subsequent rise in reported GNPA


def _sign_test_p(k: int, n: int) -> float:
    """Exact two-sided binomial test of k successes in n against p = 0.5."""
    tail = sum(math.comb(n, i) for i in range(max(k, n - k), n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _sign_flip_p(diffs: list[float]) -> float:
    """Exact two-sided paired permutation test: under the null that neither number is the
    better predictor, each lender's error difference is as likely positive as negative.
    Enumerates all 2**n sign assignments, so it is exact, up to n = 22 (about four million
    assignments). Beyond that it switches to 200,000 seeded random assignments and is an
    estimate, reproducible but no longer exact."""
    observed = abs(sum(diffs))
    if len(diffs) > 22:
        rng, draws = random.Random(0), 200_000
        hits = sum(
            abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= observed - 1e-12
            for _ in range(draws)
        )
        return hits / draws
    hits = sum(
        abs(sum(d * s for d, s in zip(diffs, signs))) >= observed - 1e-12
        for signs in itertools.product((1, -1), repeat=len(diffs))
    )
    return hits / 2 ** len(diffs)


def catch_up_test(panel: StandstillPanel, standstill_date: dt.date = STANDSTILL_DATE,
                  outcome_date: dt.date = OUTCOME_DATE, exclude: tuple[str, ...] = ()) -> CatchUpResult:
    """Scores a lender's two standstill-date numbers as predictors of its first reported
    GNPA after the order was lifted. `exclude` takes lender keys, for robustness checks
    (one outlier, Bandhan Bank, has by far the largest gap).

    What this does NOT show: that proforma was a forecast. The outcome also reflects a
    further quarter of slippages, recoveries and write-offs. It tests only which of the
    two published numbers was closer to where the lender ended up."""
    rows = []
    for key, lender in panel.lenders.items():
        if key in exclude:
            continue
        then, later = lender.quarters.get(standstill_date), lender.quarters.get(outcome_date)
        if then is None or later is None:
            continue
        if None in (then.reported_gnpa, then.proforma_gnpa, later.reported_gnpa):
            continue
        provenance = "primary" if then.provenance == later.provenance == "primary" else "secondary"
        rows.append(CatchUpRow(
            lender.name, then.reported_gnpa, then.proforma_gnpa, later.reported_gnpa,
            round(abs(later.reported_gnpa - then.reported_gnpa), 2),
            round(abs(later.reported_gnpa - then.proforma_gnpa), 2), provenance,
        ))
    if len(rows) < 3:
        raise ValueError(f"only {len(rows)} lenders have all three numbers; too few to score")
    n = len(rows)
    closer = sum(r.proforma_error_pp < r.reported_error_pp for r in rows)
    rank_corr = statistics.correlation(
        [r.proforma_gnpa - r.reported_gnpa for r in rows],
        [r.outcome_gnpa - r.reported_gnpa for r in rows], method="ranked",
    )
    return CatchUpResult(
        standstill_date.isoformat(), outcome_date.isoformat(), rows, n,
        mae_reported_pp=round(statistics.fmean(r.reported_error_pp for r in rows), 2),
        mae_proforma_pp=round(statistics.fmean(r.proforma_error_pp for r in rows), 2),
        n_proforma_closer=closer, sign_test_p=round(_sign_test_p(closer, n), 4),
        permutation_test_p=round(_sign_flip_p([r.reported_error_pp - r.proforma_error_pp for r in rows]), 4),
        n_outcome_below_proforma=sum(r.outcome_gnpa < r.proforma_gnpa for r in rows),
        rank_corr_hidden_vs_rise=round(rank_corr, 2),
    )


@dataclass(frozen=True)
class SystemStandstillContext:
    as_of: str
    system_proforma_gnpa_pct: float
    hidden_share_of_proforma_pct: float   # (proforma - reported) / proforma, from the two rupee amounts
    hidden_pp: float                      # that share applied to the proforma ratio (same advances base)
    rbi_baseline_pct: float
    rbi_baseline_target: str
    baseline_minus_proforma_pp: float     # how far RBI's baseline sits above even the proforma figure


def system_standstill_context(panel: StandstillPanel, rbi_baseline_pct: float,
                              rbi_baseline_target: str) -> SystemStandstillContext:
    """Puts the system-wide standstill effect next to RBI's stress-test baseline.

    The only derived figure is `hidden_pp`: the source gives proforma and reported GNPA in
    rupees and the proforma ratio; both amounts share one advances base, so the hidden
    ratio is the proforma ratio times the unreported share. The source is an ICRA
    compilation quoted in the press (secondary), covering "all banks" -- close to, but not
    defined identically to, RBI's scheduled-commercial-bank universe."""
    sp = panel.system_proforma
    hidden_share = (sp["proforma_gnpa_lakh_cr"] - sp["reported_gnpa_lakh_cr"]) / sp["proforma_gnpa_lakh_cr"]
    return SystemStandstillContext(
        as_of=sp["as_of"], system_proforma_gnpa_pct=sp["proforma_gnpa_pct"],
        hidden_share_of_proforma_pct=round(hidden_share * 100, 1),
        hidden_pp=round(sp["proforma_gnpa_pct"] * hidden_share, 2),
        rbi_baseline_pct=rbi_baseline_pct, rbi_baseline_target=rbi_baseline_target,
        baseline_minus_proforma_pp=round(rbi_baseline_pct - sp["proforma_gnpa_pct"], 2),
    )
