# Market Screeners

A console stock screener for US stocks and ETFs. It downloads two years of
daily Yahoo Finance data, computes technical indicators with `pandas-ta-classic`,
and prints a color-coded status table for every requested ticker. Each run also
saves a self-contained HTML snapshot preserving the ANSI colors seen in the terminal.

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

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/)
- Internet access to download market data from Yahoo Finance

## Setup

1. Clone or download this repository and open a terminal in the root directory
   (where `pyproject.toml` lives).

2. Confirm Python 3.12+:

   ```bash
   python --version
   # On Windows: py --version
   ```

3. Install [uv](https://docs.astral.sh/uv/getting-started/) if not already installed.

4. Create the virtual environment and install dependencies:

   ```bash
   uv sync
   ```

   This creates `.venv` from `pyproject.toml` and `uv.lock`. You don't need to
   activate it when using `uv run`.

5. Verify the installation:

   ```bash
   uv run python -m unittest discover -s tests -v
   ```

   Tests use synthetic data and mocked Yahoo Finance responses — no network requests.

## Run

```bash
# Full stock and ETF universe
uv run python -m market_screeners

# First 10 symbols (quick test)
uv run python -m market_screeners --test

# Personal watch list (reads from my_tickers.txt — see my_tickers.example.txt)
uv run python -m market_screeners --my

# Export to a specific HTML path
uv run python -m market_screeners --export-html path/to/output.html
```

Each run automatically saves a timestamped HTML snapshot to `data/` (e.g.
`data/screener_full_20260802_143022.html`). Pass `--export-html` to override
the output path.

To use `--my` mode, copy `my_tickers.example.txt` to `my_tickers.txt` and add
your own symbols (one per line). The file is gitignored so your watch list stays
private.

## GitHub Actions

A workflow runs the full screener daily (Mon–Fri at 9 PM EST) and commits the
HTML report to `data/` in the repository, named by day of week (e.g.
`data/screener_FRI.html`). At most 7 files accumulate — one per day — each
overwritten in place on its next occurrence. You can also trigger the workflow
manually from the Actions tab.

## Architecture

```
market universe → Ticker → compute service → Calc → display service → Display → console + HTML
```

- `model/` — dataclasses and market-universe data
- `service/compute_service.py` — fetches Yahoo Finance data, calculates indicators and CAR
- `service/display_service.py` — formats, colorizes, sorts, and prints results
- `service/html_service.py` — captures ANSI output and exports it as self-contained HTML
- `cli/main.py` — parses CLI flags and orchestrates the services

`Ticker` is immutable metadata. `Calc` holds raw numeric/date results. `Display`
holds final strings with ANSI color codes, breakout codes, and formatted dates.

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

### EMA 8 and DMAs

EMA 8 and the 30, 50, 100, 200 DMAs. Each is green when CMP is above it.

### Shift%

`(CMP − 200 DMA) / 200 DMA × 100`. Purple > 10, green 0.01–10, yellow −10 to 0, red < −10.

### 52WL − 52WH (Days Since 52W Low)

Days since the 52-week low, negative when the low preceded the high. Purple > 90, green 30–90.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
