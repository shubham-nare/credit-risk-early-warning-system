"""Loads the real, sourced datasets in data/*.yaml. See each file's own header comment
for the exact provenance (disclosed / secondary / assumption) of every number it holds.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _parse_date(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%Y-%m").date() if len(s) == 7 else dt.date.fromisoformat(s)


@dataclass(frozen=True)
class StressProjection:
    projection_made_in: str
    target_date: dt.date
    baseline_pct: float
    severe_pct: float
    as_of_date: dt.date | None = None
    as_of_gnpa_pct: float | None = None


@dataclass(frozen=True)
class SCBGNPAData:
    actual_gnpa_pct: dict[dt.date, float]
    stress_projections: list[StressProjection]
    known_gaps: list[str]


def load_scb_gnpa(path: Path = DATA_DIR / "scb_gnpa.yaml") -> SCBGNPAData:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    actual = {_parse_date(k): v for k, v in raw["actual_gnpa_pct"].items()}
    projections = [
        StressProjection(
            projection_made_in=p["projection_made_in"], target_date=_parse_date(p["target_date"]),
            baseline_pct=p["baseline_pct"], severe_pct=p["severe_pct"],
            as_of_date=_parse_date(p["as_of_date"]) if "as_of_date" in p else None,
            as_of_gnpa_pct=p.get("as_of_gnpa_pct"),
        )
        for p in raw["rbi_stress_projections"]
    ]
    return SCBGNPAData(actual, projections, raw["known_gaps"])


@dataclass(frozen=True)
class MacroConditions:
    repo_rate_pct: dict[dt.date, float]
    gdp_growth_pct: dict[str, float]


def load_macro_conditions(path: Path = DATA_DIR / "macro_conditions.yaml") -> MacroConditions:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    repo = {_parse_date(k): v for k, v in raw["repo_rate_pct"].items()}
    return MacroConditions(repo, raw["gdp_growth_pct"])


@dataclass(frozen=True)
class BajajFinanceGNPA:
    quarterly: dict[dt.date, dict[str, float]]


def load_bajaj_finance(path: Path = DATA_DIR / "bajaj_finance_gnpa.yaml") -> BajajFinanceGNPA:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    return BajajFinanceGNPA({_parse_date(k): v for k, v in raw["quarterly"].items()})


def load_policy_interventions(path: Path = DATA_DIR / "policy_interventions.yaml") -> dict:
    return yaml.safe_load(open(path, encoding="utf-8"))
