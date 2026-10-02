# Credit Risk Early-Warning System

How much can you trust a bank's reported bad-loan ratio, and how much can you trust the
regulator's forecast of it? This project tests both against what actually happened, using
public disclosures from Indian banks and non-bank lenders and from the Reserve Bank of
India (RBI).

It has four parts:

1. **A lender-level panel of hidden stress.** During the Supreme Court's 2020–21 freeze on
   bad-loan classification, lenders published two numbers: the reported ratio and a
   "proforma" ratio showing what it would have been without the freeze. The panel collects
   both for 23 lenders and checks which one was the better guide to where each lender ended
   up.
2. **A share-price test.** Did investors react to the reported number or the proforma one?
3. **A twelve-year scorecard of RBI's stress-test projections** for system-wide bad loans,
   from RBI's own publications.
4. **A live, pre-registered forecast** of each lender's bad-loan ratio for the quarter ended
   30 September 2026, committed before any lender reported, to be scored against the
   published results.

Every number is traceable to a source, and each source is labelled as primary (the lender's
or RBI's own document) or secondary (press coverage or an aggregator). Nothing is
estimated, interpolated or filled in; a missing value is left missing.

> **Terms.** *GNPA* is the gross non-performing asset ratio: bad loans as a percentage of
> total loans. *pp* means percentage points. *FSR* is RBI's half-yearly Financial Stability
> Report.

## Findings

### 1. The standstill hid between 0.6 and 6.0 points of bad loans per lender

On 3 September 2020 the Supreme Court barred lenders from classifying any new account as
non-performing. The order was lifted on 23 March 2021. In between, reported GNPA was
frozen, and lenders disclosed a proforma figure alongside it.

In December 2020 the gap between the two ranged from 0.57pp (HDFC Bank) to 6.00pp (Bandhan
Bank, which reported 1.1% against a proforma 7.1%).

When the order was lifted, which December number was closer to the March 2021 reported
ratio?

| | Result (22 lenders) |
|---|---|
| Proforma was the closer number | 16 of 22 lenders |
| Average miss, proforma | 0.79pp |
| Average miss, reported | 1.54pp |
| Exact sign test | p = 0.053 |
| Exact paired permutation test | p = 0.087 |

The proforma figure's miss is half the reported figure's, and the direction is consistent,
but **this is not statistically significant at the 5% level**. The six lenders where the
reported number was closer (Axis, SBI, Bank of Baroda, Union Bank, Yes Bank, Karur Vysya)
all have large corporate loan books; fourth-quarter write-offs are a plausible reason, not
yet tested.

### 2. Investors appear to have read through to the proforma number

Around the day each lender announced its December 2020 quarter, lenders that revealed more
hidden stress did worse than the Nifty Bank index.

- Rank correlation between hidden stress (pp) and the lender's return relative to the
  index: **−0.52**, permutation p = 0.011, 23 lenders.
- It stays between −0.46 and −0.54 when the two uncertain results dates, the four lenders
  whose window spans the 1 February 2021 Budget rally, or Bandhan Bank are dropped.

Two caveats. A second measure, hidden stress as a share of proforma, shows no relationship
(−0.18, p = 0.42), so the first p-value is weaker than it looks. And a results-day return
reflects the whole earnings release, not only bad loans.

### 3. RBI's stress-test baseline is anchored to the starting point

Each FSR publishes a baseline projection of system GNPA about a year ahead. This project
scores all 25 that can be scored, from December 2014 to December 2024, against the outcome
and against the simplest benchmark: "no change from today".

- The baseline called for moves about a third the size of what happened (0.57pp projected
  against 1.77pp actual, outside the COVID editions).
- It was too low in 9 of the 11 cases where GNPA rose and too high in all 14 cases where
  GNPA fell.
- It overshot **15 times in a row**, for every target date from September 2018 to March
  2026.
- Outside the two COVID-era editions it was about as accurate as "no change" (average miss
  1.73pp against 1.77pp), and it was the closer of the two 17 times out of 23.
- The COVID editions are the exception: the two largest moves the baseline ever called for
  (+4.0pp and +6.0pp), both in the wrong direction.

RBI presents these as scenario results conditional on a macro outlook, not as forecasts.
Scoring them as forecasts is this project's framing, not RBI's. Projection windows overlap,
so the errors are not independent.

### 4. A forecast that can be wrong in public

[`forecasts/2026-09_preregistration.yaml`](forecasts/2026-09_preregistration.yaml) holds
forecasts of the September 2026 quarter GNPA for 35 lenders, with 80% intervals, the
benchmark each must beat, the scoring rules and a hash of the input data. It was committed
on 2 October 2026; the first lenders report on 17 October 2026.

The method was chosen by a rule fixed in code beforehand: the lowest average error in a
backtest of six candidates over 210 lender-quarters. The winner, `sector_drift`, applies
the average quarterly change across all lenders to each one (0.150pp average error in
backtest, against 0.192pp for "no change").

**It may lose.** The 13 quarters of history are one long fall in GNPA, so a method that
extrapolates the fall wins the backtest and loses if the cycle turns. That is the same
weakness finding 3 documents in RBI's baselines. The file says so, and the result will be
reported either way after the 30 November 2026 cutoff.

| Lender | June 2026 | Forecast, Sept 2026 | 80% interval |
|---|---|---|---|
| HDFC Bank | 1.17 | 1.11 | 0.98 – 1.21 |
| ICICI Bank | 1.38 | 1.31 | 1.15 – 1.43 |
| State Bank of India | 1.47 | 1.39 | 1.23 – 1.52 |
| Punjab National Bank | 2.78 | 2.63 | 2.32 – 2.87 |
| Bandhan Bank | 3.15 | 2.98 | 2.63 – 3.26 |

## What changed along the way

Three conclusions were weakened by later data. They are listed here because the corrections
are part of the result.

- **"A naive trend line beat RBI's stress test."** True for the two COVID editions, where
  this project started. Across twelve years it is not a general property.
- **"The loan moratorium probably explains the rest of RBI's COVID miss."** The panel
  measured that channel directly. System-wide, about 1.2pp of GNPA was unreported in
  December 2020, and it had surfaced by the March 2021 reading. Write-offs and genuine
  resilience remain as explanations; write-offs are not yet measured.
- **"Proforma predicted the outcome for 9 of 11 lenders, p = 0.025."** That was an
  11-lender pilot. At 22 lenders it is 16 of 22 and p is between 0.05 and 0.09.

The tests assert the weaker, current versions.

## Data and sources

| File | What it holds | Source quality |
|---|---|---|
| `data/standstill_panel.yaml` | Reported and proforma GNPA and net NPA, Sept 2020 – March 2021, 23 lenders | 12 lenders' December 2020 figures read from their own filings, with page numbers; the rest from press coverage. Each quarter says which. |
| `data/rbi_stress_track_record.yaml` | 28 baseline projections and 24 half-yearly outcomes, 2014–2026 | Primary: RBI press releases and FSR chapters on rbi.org.in |
| `data/quarterly_gnpa.yaml` | Quarterly GNPA, June 2023 – June 2026, 36 lenders | Secondary: screener.in, an aggregator of exchange filings |
| `data/event_prices.csv` | Adjusted daily closes, Jan – Apr 2021, 23 lenders and the Nifty Bank index | Secondary: Yahoo Finance |
| `data/q3fy21_results_dates.yaml` | The day each lender announced its December 2020 quarter | 12 from filings, 9 from same-day coverage, 2 inferred |
| `data/scb_gnpa.yaml` and other files | The original COVID-era analysis: system GNPA, restructuring, two lender series | Mixed; stated in each file's header |

Downloaded filings are not in the repository (they are the lenders' copyright). The panel
records each filing's URL and the first 16 characters of its SHA-256, and a test checks any
local copy against that hash.

## Repository layout

```
data/        sourced datasets, each with a provenance header
forecasts/   the pre-registered forecast (never edited after commit)
src/credit_risk/
  standstill.py     hidden stress and the catch-up test
  market_test.py    results-day share-price test
  track_record.py   scoring RBI's baselines
  forecast.py       forecasting methods, backtest, selection rule
  analysis.py       the original COVID forecast-error and shadow-GNPA analysis
  data_loader.py    loaders that refuse untraceable or contradictory values
scripts/
  build_*_report.py     print each analysis end to end
  fetch_*.py            re-download source data
  pdf_grep.py, html_grep.py   find a number's page or sentence in a source document
  preregister_forecast.py, score_forecast.py
tests/       50 tests, run against the real data
```

## Running it

Requires Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest                   # 50 tests, about 20 seconds
```

The report scripts need `src` on the Python path:

```bash
PYTHONPATH=src python scripts/build_panel_report.py
PYTHONPATH=src python scripts/build_market_report.py
PYTHONPATH=src python scripts/build_track_record_report.py
PYTHONPATH=src python scripts/score_forecast.py forecasts/2026-09_preregistration.yaml
```

In PowerShell, set the path first: `$env:PYTHONPATH = "src"`.

The analysis uses only the Python standard library plus PyYAML. `pypdf` and `yfinance` are
needed only to re-read source PDFs and re-download prices.

## Limitations

- **Small samples.** Twenty-odd lenders and 25 projections. Significance tests are exact or
  permutation tests with the sample size stated; none of the results is strong enough to
  stand without its caveats.
- **Not a random sample.** Lenders are in the panel because a proforma figure could be
  found, which favours those that disclosed clearly.
- **Proforma is not one definition.** HDFC Bank's uses its own analytical models, Bajaj
  Finance calls its figure "adjusted", and Bandhan Bank's counts partially paying
  microfinance borrowers. Two figures (Yes Bank, Canara Bank) are known only approximately.
- **Secondary sources.** About half the panel, all of the quarterly history behind the
  forecast, and the prices. The forecast data matched results coverage for three of four
  lenders spot-checked; the fourth, Bajaj Finance, did not and is excluded from the
  forecast.
- **No literature review yet.** This may duplicate published work on the standstill
  disclosures; no claim of novelty is made.
- **Not investment advice.**

## Still to do

- Lender-level write-offs and 2021–22 outcomes, to test the corporate-book pattern in
  finding 1 and the write-off explanation for RBI's COVID miss.
- Replace press-sourced panel entries with the lenders' own filings.
- Score the live forecast after 30 November 2026.
- Test which March 2020 characteristics predicted hidden stress.

## Author

Shubham Nare
