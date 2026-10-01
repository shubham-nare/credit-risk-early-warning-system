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


@dataclass(frozen=True)
class NBFCGNPAData:
    fiscal_year_end_gnpa_pct: dict[dt.date, dict]  # {date: {"value": float, "provenance": str}}
    known_gaps: list[str]


def load_nbfc_gnpa(path: Path = DATA_DIR / "nbfc_gnpa.yaml") -> NBFCGNPAData:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    series = {_parse_date(k): v for k, v in raw["fiscal_year_end_gnpa_pct"].items()}
    return NBFCGNPAData(series, raw["known_gaps"])


def load_nbfc_stress_test(path: Path = DATA_DIR / "nbfc_stress_test.yaml") -> dict:
    return yaml.safe_load(open(path, encoding="utf-8"))


@dataclass(frozen=True)
class IIFLFinanceGNPA:
    series: dict[dt.date, dict[str, float]]
    regulatory_forbearance_evidence: dict


def load_iifl_finance(path: Path = DATA_DIR / "iifl_finance_gnpa.yaml") -> IIFLFinanceGNPA:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    series = {_parse_date(k): v for k, v in raw["annual_and_quarterly"].items()}
    return IIFLFinanceGNPA(series, raw["regulatory_forbearance_evidence"])


@dataclass(frozen=True)
class ResolutionFrameworkData:
    actual_restructured_pct: dict[dt.date, float]
    known_gaps: list[str]


def load_resolution_framework(path: Path = DATA_DIR / "resolution_framework.yaml") -> ResolutionFrameworkData:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    series = {_parse_date(k): v for k, v in raw["actual_restructured_pct_of_total_advances"].items()}
    return ResolutionFrameworkData(series, raw["known_gaps"])


@dataclass(frozen=True)
class BaselineProjection:
    edition: str
    as_of: dt.date
    target: dt.date
    baseline_pct: float
    severe_pct: float | None


@dataclass(frozen=True)
class StressTrackRecord:
    actual_gnpa_pct: dict[dt.date, float]   # as first published, not as later revised
    projections: list[BaselineProjection]
    unscored: list[dict]


def load_stress_track_record(path: Path = DATA_DIR / "rbi_stress_track_record.yaml") -> StressTrackRecord:
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    actual = {_parse_date(k): v["value"] for k, v in raw["actual_gnpa_pct"].items()}
    projections = [
        BaselineProjection(p["edition"], _parse_date(p["as_of"]), _parse_date(p["target"]),
                           p["baseline"], p.get("severe"))
        for p in raw["projections"]
    ]
    return StressTrackRecord(actual, projections, raw["unscored"])


@dataclass(frozen=True)
class PanelSource:
    provenance: str            # "primary" (the lender's own filing) or "secondary" (press coverage)
    doc: str
    url: str | None = None
    file: str | None = None    # filename under sources/filings/, primary sources only
    sha256_16: str | None = None


@dataclass(frozen=True)
class PanelQuarter:
    date: dt.date
    reported_gnpa: float | None
    proforma_gnpa: float | None
    reported_nnpa: float | None
    proforma_nnpa: float | None
    provenance: str            # "primary" only if every source this quarter draws on is primary


@dataclass(frozen=True)
class PanelLender:
    key: str
    name: str
    kind: str                  # private_bank / public_bank / nbfc
    ticker: str
    sources: dict[str, PanelSource]
    quarters: dict[dt.date, PanelQuarter]
    extras: dict               # restructured / moratorium / writeoffs etc., as recorded


@dataclass(frozen=True)
class StandstillPanel:
    lenders: dict[str, PanelLender]
    system_proforma: dict
    standstill: dict
    known_gaps: list[str]


_SRC_FIELDS = ("src", "nnpa_src", "proforma_src")
_VALUE_FIELDS = ("reported_gnpa", "proforma_gnpa", "reported_nnpa", "proforma_nnpa")


def load_standstill_panel(path: Path = DATA_DIR / "standstill_panel.yaml") -> StandstillPanel:
    """Loads the lender-level reported-vs-proforma NPA panel. Raises on anything that
    would let an untraceable or internally contradictory number through: a quarter citing
    a source key its lender does not define, or a proforma ratio below the reported one
    (proforma adds accounts back, so that can only be a transcription error)."""
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    lenders = {}
    for key, entry in raw["lenders"].items():
        sources = {k: PanelSource(**v) for k, v in entry["sources"].items()}
        quarters = {}
        for date_str, q in entry["quarters"].items():
            cited = [q[f] for f in _SRC_FIELDS if f in q]
            if not cited:
                raise ValueError(f"{key} {date_str}: no source cited")
            for src in cited:
                if src not in sources:
                    raise ValueError(f"{key} {date_str}: cites unknown source {src!r}")
            for measure in ("gnpa", "nnpa"):
                reported, proforma = q.get(f"reported_{measure}"), q.get(f"proforma_{measure}")
                if reported is not None and proforma is not None and proforma < reported:
                    raise ValueError(f"{key} {date_str}: proforma {measure} {proforma} is below reported {reported}")
            provenance = "primary" if all(sources[s].provenance == "primary" for s in cited) else "secondary"
            date = _parse_date(date_str)
            quarters[date] = PanelQuarter(date, *(q.get(f) for f in _VALUE_FIELDS), provenance)
        extras = {k: v for k, v in entry.items() if k not in ("name", "kind", "ticker", "sources", "quarters")}
        lenders[key] = PanelLender(key, entry["name"], entry["kind"], entry["ticker"], sources, quarters, extras)
    return StandstillPanel(lenders, raw["system_proforma"], raw["standstill"], raw["known_gaps"])
