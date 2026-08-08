# Market Screeners

Three independent console screeners for US stocks and ETFs: a multi-indicator
technical scanner, an institutional-accumulation scanner, and an option-chain
mood scanner. Each downloads its own Yahoo Finance data, computes its own
indicators (using `pandas-ta-classic` for the technical ones), and prints a
color-coded status table for every requested ticker. Every run also saves a
self-contained HTML snapshot preserving the ANSI colors seen in the terminal.

## Attribution and Disclaimer

Thanks to [Mahesh Chander Kaushik](https://www.maheshkaushik.com/) for sharing
the educational material that inspired this project. The logic in this
repository is derived from his blog posts and videos; none of the algorithmic
logic is mine. This is an independent implementation for educational purposes
and is not affiliated with or endorsed by Mahesh Kaushik.

See his [official website](https://www.maheshkaushik.com/),
[YouTube channel](https://www.youtube.com/maheshchanderkaushik), and
[YouTube playlist](https://www.youtube.com/playlist?list=PL-X8WTMcEbY9PwIlpUbaMtp1JNNtdcWyM)
for the original material. Related videos: [How to find best stocks using a data bank](https://youtu.be/BYm-rppAHSc)
and [How to build your own data bank](https://youtu.be/1z-xatk8LKg). Nothing
here is investment advice — always do your own research and consult a qualified professional.

## Setup

This project is intended for traders and investors who want to screen US stocks and ETFs using technical indicators and option chain analysis. Here's how to get started:

### First-Time Setup

1. **Clone or download this repository** and open a terminal in the root directory (where `pyproject.toml` lives).

2. **Confirm Python 3.12+**:
   ```bash
   python --version
   # On Windows: py --version
   ```
   If you need to install Python, download it from [python.org](https://www.python.org/downloads/).

3. **Install [uv](https://docs.astral.sh/uv/getting-started/)** if not already installed:
   ```bash
   # macOS / Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows (PowerShell):
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

4. **Create the virtual environment and install dependencies**:
   ```bash
   uv sync
   ```
   This creates `.venv` from `pyproject.toml` and `uv.lock`. You don't need to activate it when using `uv run`.

5. **Verify the installation**:
   ```bash
   uv run python -m unittest discover -s tests -v
   ```
   Tests use synthetic data and mocked Yahoo Finance responses — no network requests.

6. **Set up your personal watch list (optional)**:
   ```bash
   # Copy the example file to my_tickers.txt
   cp my_tickers.example.txt my_tickers.txt
   
   # On Windows:
   copy my_tickers.example.txt my_tickers.txt
   ```
   Then edit `my_tickers.txt` and add your own stock symbols (one per line, e.g., `AAPL`, `MSFT`).

### Running the Screeners

Once setup is complete, you can run any of the three screeners:



## Tests

```bash
uv run python -m unittest discover -s tests -v
```

## Run

There are three main screeners available:

### 1. Multi-Indicator Screener (default)

Scans US stocks and ETFs using technical indicators (DMA, CAR, MAC, RSI, KST, Zone, Shift%).

```bash
# Personal watch list
uv run python -m market_screeners --my

# First 10 symbols (quick test)
uv run python -m market_screeners --test

# Full stock and ETF universe
uv run python -m market_screeners

# Export to a specific HTML path
uv run python -m market_screeners --export-html path/to/output.html
```

**Note:** `uv run python -m market_screeners` is a shortcut for
`uv run python -m market_screeners.screeners.multi_indicator` — both run the
same screener. The scheduled GitHub Actions workflow uses the explicit
`market_screeners.screeners.multi_indicator` path.

### 2. Institutional Accumulation Scanner

Analyzes institutional buying patterns using volume flow, OBV/AD divergence, and Wyckoff-style analysis (same input modes):

```bash
# Personal watch list
uv run python -m market_screeners.screeners.institution --my

# Quick test (first 10 symbols)
uv run python -m market_screeners.screeners.institution --test

# Full universe
uv run python -m market_screeners.screeners.institution

# Export HTML
uv run python -m market_screeners.screeners.institution --export-html data/institution_custom.html
```

**Note:** The institutional scanner is a separate module and is not invoked by `uv run python -m market_screeners`. Run it directly as shown above.

**Data fetch / analysis note:** The institutional scanner fetches a longer history (210 days) but analyzes the most recent 120 days. In general, set the fetch period about 80–100 days longer than the analysis window to properly warm up technical indicators (sma/ema/atr/obv windows and other rolling stats). This avoids edge effects and ensures moving averages and other indicators have enough prior data to be stable.

### 3. Option Analysis Scanner

Reads the mood of the option market for a list of tickers by analyzing put/call ratios, IV skew, BMI (Balanced Method Indicator), max pain, and other option-chain metrics (same input modes):

```bash
# Personal watch list
uv run python -m market_screeners.screeners.option_analysis --my

# Quick test (first 10 symbols)
uv run python -m market_screeners.screeners.option_analysis --test

# Full universe
uv run python -m market_screeners.screeners.option_analysis

# Export HTML
uv run python -m market_screeners.screeners.option_analysis --export-html data/option_analysis_custom.html
```

**Note:** The option analysis scanner fetches live option chain data (may take 1-2 seconds per ticker depending on network speed). Run it in `--test` mode first to verify connectivity and performance.

## GitHub Actions

A workflow runs `market_screeners.screeners.multi_indicator` (the
multi-indicator screener only — the institution and option-analysis screeners
are not scheduled) daily (Mon–Fri at 1 AM EST) and commits the HTML report to
`data/` in the repository, named by day of week (e.g. `data/screener_FRI.html`).
At most 7 files accumulate — one per day — each overwritten in place on its
next occurrence. You can also trigger the workflow manually from the Actions tab.

## Architecture

There are three independent screeners, each a self-contained module under
`src/market_screeners/screeners/` with its own `main()` and CLI flag handling
(`--my`, `--test`, `--export-html`). All three share the same `model/` and
`service/` layer for market-universe data and HTML export:

```
market universe → Ticker → (per-screener analysis) → console + HTML
```

- `model/` — dataclasses and market-universe data shared by all screeners
- `service/compute_service.py` — fetches Yahoo Finance data, calculates indicators and CAR (multi-indicator only)
- `service/display_service.py` — formats, colorizes, sorts, and prints results (multi-indicator only)
- `service/html_service.py` — captures ANSI output and exports it as self-contained HTML (shared by all three)
- `cli/main.py` — parses CLI flags and orchestrates the multi-indicator services
- `screeners/multi_indicator.py` — thin entry point that delegates to `cli/main.py`
- `screeners/institution.py` — self-contained institutional-accumulation screener (indicators, scoring, and CLI all in one module)
- `screeners/option_analysis.py` — self-contained option-chain mood screener (metrics, coloring, and CLI all in one module)

`Ticker` is immutable metadata. `Calc` holds raw numeric/date results. `Display`
holds final strings with ANSI color codes, breakout codes, and formatted dates.
These three model types are used by the multi-indicator screener; the
institution and option-analysis screeners work directly off pandas DataFrames
and their own small dataclasses instead.

## Indicators

### DCM

Combines breakout flags: `D` = DMA BO, `C` = CAR BO, `M` = MAC BO. `DCM` means
all three qualify. The Breakouts table contains rows with at least one flag;
Others contains the rest.

### DMA BO (`D`)

`CMP > 50 DMA > 100 DMA > 200 DMA` and `0% < Shift% < 10%`.

### CAR BO (`C`)

CMP is above the 50, 100, and 200 DMAs, `0% < Shift% < 10%`, and `CAR >= 5`.

### MAC BO (`M`)

CMP and the 50, 100, and 200 DMAs are all within 3% of the lowest of those four values.

### RVOL

`Current Volume / 20-period SMA of Volume`. Green ≥ 1.5, yellow ≥ 0.9, normal otherwise.

### ROBV

`Current OBV / 20-period SMA of OBV`. Green when OBV is positive and above its SMA;
red when OBV is negative and below its SMA. Note: a positive ratio can still be
bearish if OBV is negative (e.g. `−278 / −100 = +2.78` but still below SMA).

### CAR

Longest increasing tail (10→1) of the expanding mean of closing prices from the
52-week-high date. Red < 2, yellow 2–4, green 5–9, purple ≥ 10.

### Zone

- `B++` — CMP > 50 DMA > 100 DMA > 200 DMA and all three DMAs are rising — purple
- `B+` — CMP above all three DMAs and 50 DMA crossed above 100 or 200 DMA — green
- `B--` — CMP < 50 DMA < 100 DMA < 200 DMA and all three DMAs are falling — red
- `B-` — CMP below all three DMAs and 50 DMA crossed below 100 or 200 DMA — yellow
- `U` — all other cases

### RSI

14-period RSI. Purple ≤ 25, green 26–40, yellow 41–65, red > 65.

### KST

Know Sure Thing momentum oscillator. Shows `▲` (green) when the KST line is above its signal line (bullish momentum) and `▼` (red) when below (bearish). `-` when fewer than 54 bars of data are available.

### EMA 8 and DMAs

EMA 8 and the 30, 50, 100, 200 DMAs. Each is green when CMP is above it.

### Shift%

`(CMP − 200 DMA) / 200 DMA × 100`. Purple > 10, green 0.01–10, yellow −10 to 0, red < −10.

### 52WL − 52WH (Days Since 52W Low)

Days since the 52-week low, negative when the low preceded the high. Purple > 90, green 30–90.

**Note:** The 52-week high date, low date, high price, and low price are computed for internal analysis but are hidden from both the console display and the saved HTML report to reduce clutter. Only the "Days Since 52W Low" metric is shown in outputs.
