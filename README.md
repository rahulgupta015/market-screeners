# Market Screeners

A console stock screener for US stocks and ETFs. It downloads two years of
daily Yahoo Finance data, computes technical indicators with
`pandas-ta-classic`, and prints a status table for every requested ticker.

## Attribution and Disclaimer

Thanks to [Mahesh Chander Kaushik (Mahesh Kaushik)](https://www.maheshkaushik.com/)
for sharing the educational material that inspired this project. The logic in
this repository is derived from his blog posts and videos; none of the
algorithmic logic is mine. This repository is an independent implementation
for educational purposes and is not affiliated with or endorsed by Mahesh
Kaushik.

Please see his [official website](https://www.maheshkaushik.com/),
[YouTube channel](https://www.youtube.com/maheshchanderkaushik), and related
[YouTube video playlist](https://www.youtube.com/playlist?list=PL-X8WTMcEbY9PwIlpUbaMtp1JNNtdcWyM)
for the original educational material. Related videos include [How to find
best stocks using a data bank](https://youtu.be/BYm-rppAHSc) and [How to build
your own data bank](https://youtu.be/1z-xatk8LKg). Nothing in this project is investment
advice; always do your own research and consult a qualified professional.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/)
- Internet access when the screener downloads market data from Yahoo Finance.

## Setup

1. Clone or download this repository, then open a terminal in the repository
   root (the directory containing `pyproject.toml`).

2. Confirm that Python 3.12 or newer is available:

   ```bash
   python --version
   ```

   On Windows, use `py --version` if the `python` command is unavailable.

3. Install [uv](https://docs.astral.sh/uv/getting-started/) if it is not
   already installed.

4. Create the project environment and install the project plus its pinned
   dependencies:

   ```bash
   uv sync
   ```

   `uv sync` creates or updates the local `.venv` environment from
   `pyproject.toml` and `uv.lock`. You do not need to activate the environment
   when using `uv run`.

5. Verify the installation by running the test suite:

   ```bash
   uv run python -m unittest discover -s tests -v
   ```

   The tests use synthetic data and mocked Yahoo Finance responses, so they do
   not make network requests.

If you prefer to activate the environment first, use `.venv\\Scripts\\Activate.ps1`
in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. After
activation, `python -m market_screeners` can be used instead of
`uv run python -m market_screeners`.

## Run

```bash
# Full stock and ETF universe
uv run python -m market_screeners

# First 10 symbols from the sorted universe
uv run python -m market_screeners --test

# Personal watch list
uv run python -m market_screeners --my
```

Direct execution of the compatibility wrapper is also available:

```bash
uv run src/market_screeners/screeners/multi_indicator.py --test
```

## Architecture

```text
market universe -> Ticker -> compute service -> Calc -> display service -> Display -> console
```

- `model/` contains dataclasses and market-universe data.
- `service/compute_service.py` fetches Yahoo Finance data and calculates indicators and CAR.
- `service/display_service.py` formats, colors, sorts, and prints results.
- `cli/main.py` handles command-line flags and orchestrates the services.

`Ticker` is immutable metadata loaded from the stock and ETF universe files.
`Calc` contains raw numeric/date results. `Display` contains final strings,
colors, breakout codes, and compact dates.

## Indicators

### DCM

The `DCM` column combines breakout flags: `D` = DMA BO, `C` = CAR BO, and
`M` = MAC BO. For example, `DCM` means the ticker qualifies for all three.
The Breakouts table contains rows with at least one code; Others contains rows
with no code.

### DMA BO

Flag `D` when `CMP > 50 DMA > 100 DMA > 200 DMA` and `0% < Shift% < 10%`.
Zone does not affect this flag.

### CAR BO

Flag `C` when CMP is above the 50, 100, and 200 DMAs, `0% < Shift% < 10%`, and
`CAR >= 5`. Zone does not affect this flag.

### MAC BO

Flag `M` when CMP and the 50, 100, and 200 DMAs are all within 3% of the lowest
of those four values. Zone does not affect this flag.

### RVOL

`Current Volume / 20-period SMA of Volume`. Green when `>= 1.5`, yellow when
`>= 0.9 and < 1.5`, normal otherwise.

### ROBV

`Current OBV / 20-period SMA of OBV`. Green when current OBV is positive and
above its 20-period SMA. Red when current OBV is negative and below its
20-period SMA. Normal otherwise. Because OBV is signed, a positive ROBV can
still be bearish. For example, `OBV = -278 / SMA = -100 = +2.78`; current OBV
is still below its SMA, so the value is bearish/red.

### CAR

The longest increasing tail, from 10 down to 1, of the expanding mean of
closing prices starting at the 52-week-high date. Red below 2, yellow from 2
through 4, green from 5 through 9, purple from 10 upward.

### Zone

Display-only classification:

- `B++`: CMP > 50 DMA > 100 DMA > 200 DMA and all three DMAs are rising -- purple
- `B+`: CMP is above all three DMAs and the 50 DMA crossed above the 100 or 200 DMA -- green
- `B--`: CMP < 50 DMA < 100 DMA < 200 DMA and all three DMAs are falling -- red
- `B-`: CMP is below all three DMAs and the 50 DMA crossed below the 100 or 200 DMA -- yellow
- `U`: all other cases -- normal

### RSI

14-period RSI. Purple when `<= 25`, green when `> 25 and <= 40`, yellow when
`> 40 and <= 65`, red when `> 65`.

### EMA 8 and DMAs

EMA 8 and the 30, 50, 100, and 200 DMAs. Each value is green when CMP is above
it, normal otherwise.

### Shift%

`(CMP - 200 DMA) / 200 DMA * 100`. Purple when `> 10`, green when `>= 0.01 and
<= 10`, yellow when `>= -10 and < 0.01`, red when `< -10`.

### 52WL - 52WH

Days since the 52-week low, signed negative when the low occurred before the
52-week high. Purple when `> 90`, green when `>= 30 and <= 90`, normal otherwise.

## Test

Tests use synthetic data and mocks, so they do not download market data:

```bash
uv run python -m unittest discover -s tests -v
```
