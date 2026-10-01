"""Builds data/quarterly_gnpa.yaml: reported gross and net NPA ratios by quarter for a set
of listed Indian lenders, read from each company's public page on screener.in.

    python scripts/fetch_quarterly_gnpa.py

PROVENANCE: SECONDARY. screener.in is an aggregator of exchange filings, not the filing
itself. It is used here because it gives ~13 consistent quarters per lender in one page,
which is what a backtest needs. The raw pages are kept in sources/screener/ (gitignored)
so the extraction can be re-checked. Lenders whose page has no gross-NPA row are listed
under `skipped`, not filled in.
"""
from __future__ import annotations

import datetime as dt
import re
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "sources" / "screener"
OUT = ROOT / "data" / "quarterly_gnpa.yaml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# NSE symbols. The first eleven are the standstill-panel lenders.
SYMBOLS = [
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN", "INDUSINDBK", "BANDHANBNK", "BAJFINANCE",
    "IDFCFIRSTB", "RBLBANK", "PNB",
    "BANKBARODA", "CANBK", "UNIONBANK", "INDIANB", "BANKINDIA", "IOB", "UCOBANK", "CENTRALBK", "MAHABANK",
    "PSB", "IDBI", "FEDERALBNK", "YESBANK", "AUBANK", "KARURVYSYA", "CUB", "DCBBANK", "SOUTHBANK",
    "KTKBANK", "CSBBANK", "TMB", "EQUITASBNK", "UJJIVANSFB", "J&KBANK", "DHANBANK",
]
MONTHS = {"Mar": 3, "Jun": 6, "Sep": 9, "Dec": 12}


def _fetch(symbol: str) -> str:
    target = RAW / f"{symbol.replace('&', '_')}.html"
    if not target.exists():
        url = f"https://www.screener.in/company/{urllib.request.quote(symbol)}/"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
            target.write_bytes(response.read())
        time.sleep(1.5)
    return target.read_text(encoding="utf-8", errors="replace")


def _row(section: str, label: str) -> list[str] | None:
    match = re.search(re.escape(label) + r".*?</tr>", section, flags=re.S)
    return re.findall(r"<td[^>]*>\s*([\d.]*)%?\s*</td>", match.group(0)) if match else None


def parse(page: str) -> tuple[str, dict[str, dict[str, float]]] | None:
    """Returns (company name, {YYYY-MM: {gnpa, nnpa}}) from the quarterly-results table,
    or None if the page has no gross-NPA row."""
    start = page.find('id="quarters"')
    end = page.find('id="profit-loss"', start)
    if start < 0:
        return None
    section = page[start:end if end > 0 else start + 80000]
    quarters = re.findall(r"<th[^>]*>\s*([A-Z][a-z]{2}) (\d{4})\s*</th>", section)
    gnpa, nnpa = _row(section, "Gross NPA %"), _row(section, "Net NPA %")
    if not gnpa or len(gnpa) != len(quarters):
        return None
    name = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.S)
    series = {}
    for i, (month, year) in enumerate(quarters):
        if gnpa[i] == "":
            continue
        point = {"gnpa": float(gnpa[i])}
        if nnpa and len(nnpa) == len(quarters) and nnpa[i] != "":
            point["nnpa"] = float(nnpa[i])
        series[f"{year}-{MONTHS[month]:02d}"] = point
    return re.sub(r"\s+", " ", name.group(1)).strip() if name else "?", series


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    lenders, skipped = {}, []
    for symbol in SYMBOLS:
        try:
            parsed = parse(_fetch(symbol))
        except Exception as exc:   # a failed download is reported, never papered over
            skipped.append(f"{symbol}: download failed ({exc})")
            continue
        if parsed is None or not parsed[1]:
            skipped.append(f"{symbol}: no gross-NPA row in the quarterly table")
            continue
        lenders[symbol] = {"name": parsed[0], "quarters": parsed[1]}
        print(f"{symbol:<11} {len(parsed[1]):>2} quarters  {min(parsed[1])} .. {max(parsed[1])}")
    header = (
        "# Reported gross / net NPA ratio (%) by quarter-end, listed Indian lenders.\n"
        "# SECONDARY: extracted from each company's page on screener.in (an aggregator of\n"
        "# exchange filings) by scripts/fetch_quarterly_gnpa.py. Not read from the filings.\n"
        "# Spot-checks against primary filings / results coverage are recorded in CONTEXT.md.\n"
        f"# Retrieved {dt.date.today().isoformat()}.\n\n"
    )
    OUT.write_text(header + yaml.safe_dump(
        {"retrieved": dt.date.today().isoformat(), "lenders": lenders, "skipped": skipped},
        sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"\n{len(lenders)} lenders written, {len(skipped)} skipped")
    for line in skipped:
        print("  skipped:", line)


if __name__ == "__main__":
    main()
