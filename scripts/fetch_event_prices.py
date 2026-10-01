"""Downloads adjusted daily closes for the panel lenders and the Nifty Bank index around
the Q3 FY21 results season and writes them to data/event_prices.csv.

    python scripts/fetch_event_prices.py        # needs: pip install yfinance

The prices are cached in the repo so the market test and its tests run offline and give
the same answer every time. Source: Yahoo Finance via yfinance (dividend- and
split-adjusted closes) -- a secondary source for prices.
"""
from __future__ import annotations

import csv

import yaml
import yfinance as yf

from credit_risk.data_loader import DATA_DIR, load_standstill_panel

START, END = "2021-01-01", "2021-04-16"


def main() -> None:
    panel = load_standstill_panel()
    benchmark = yaml.safe_load(open(DATA_DIR / "q3fy21_results_dates.yaml", encoding="utf-8"))["benchmark_ticker"]
    tickers = sorted({lender.ticker for lender in panel.lenders.values()}) + [benchmark]
    closes = yf.download(tickers, start=START, end=END, auto_adjust=True, progress=False)["Close"]
    missing = [t for t in tickers if t not in closes.columns or closes[t].isna().all()]
    if missing:
        raise SystemExit(f"no prices returned for: {missing}")
    with open(DATA_DIR / "event_prices.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date"] + tickers)
        for date, row in closes.iterrows():
            writer.writerow([date.strftime("%Y-%m-%d")] + ["" if row[t] != row[t] else f"{row[t]:.2f}" for t in tickers])
    print(f"wrote {len(closes)} trading days x {len(tickers)} tickers")
    print("days with any gap:", int(closes.isna().any(axis=1).sum()))


if __name__ == "__main__":
    main()
