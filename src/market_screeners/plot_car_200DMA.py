import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import math

# ---------------------------------------------------------
# Dark theme
# ---------------------------------------------------------
plt.style.use("dark_background")

# ---------------------------------------------------------
# Colors
# ---------------------------------------------------------
COLOR_PRICE = None          # None = matplotlib's default color cycle
COLOR_CAR = "#FBAD60"       # orange, sampled from the compute_car()/close_prices screenshot
COLOR_DMA = "#B370D3"       # purple, sampled from the def keyword in the same screenshot
COLOR_STREAK_TEXT = "white"
COLOR_STREAK_BOX_EDGE = COLOR_CAR

# ---------------------------------------------------------
# CAR = expanding mean of prices starting from 52-week high
# ---------------------------------------------------------
def compute_car(close_prices):
    return close_prices.expanding().mean()


# ---------------------------------------------------------
# Tickers to compare
# ---------------------------------------------------------
tickers = ["BULL", "PG", "ADP", "TMO", "NDAQ", "JEPI"]  # 6 tickers


# ---------------------------------------------------------
# Grid layout: 3 per row
# ---------------------------------------------------------
cols = 3
rows = math.ceil(len(tickers) / cols)

fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 5 * rows))
axes = axes.flatten()


# ---------------------------------------------------------
# Loop through each ticker
# ---------------------------------------------------------
for ax, ticker in zip(axes, tickers):

    df = yf.download(ticker, period="2y", auto_adjust=False)

    if df.empty:
        ax.set_title(f"{ticker}: No data")
        ax.axis("off")
        continue

    df = df[["Close"]].dropna().copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # -----------------------------------------------------
    # 200 DMA
    # -----------------------------------------------------
    df["200DMA"] = df["Close"].rolling(200).mean()

    # -----------------------------------------------------
    # 52-week high (last 252 trading days)
    # -----------------------------------------------------
    df_52w = df.tail(252)
    high_52w = df_52w["Close"].max()
    high_52w_date = df_52w["Close"].idxmax()

    high_pos = df.index.get_loc(high_52w_date)
    df_after = df.iloc[high_pos:].copy()

    # Compute CAR
    df_after["CAR"] = compute_car(df_after["Close"])

    # -----------------------------------------------------
    # Plot Price + CAR + 200DMA
    # -----------------------------------------------------
    x = range(len(df_after))

    ax.plot(x, df_after["Close"], label="Price", linewidth=1.5, color=COLOR_PRICE)
    ax.plot(x, df_after["CAR"], label="CAR", linewidth=1.5, color=COLOR_CAR)

    # 200DMA must be sliced to same window
    dma_slice = df["200DMA"].iloc[high_pos:]
    ax.plot(x, dma_slice, label="200 DMA", linewidth=1.5, color=COLOR_DMA)

    # -----------------------------------------------------
    # Monotonic CAR streak: how many days in a row (ending today)
    # has CAR been strictly increasing? Same 1-10 cap the real
    # screener uses -- walk backward from today and stop at the
    # first break.
    # -----------------------------------------------------
    car_series = df_after["CAR"]
    streak_length = 0
    for length in range(min(10, len(car_series)), 0, -1):
        if car_series.tail(length).is_monotonic_increasing:
            streak_length = length
            break

    if streak_length > 0:
        streak_start_pos = len(car_series) - streak_length
        streak_start_value = car_series.iloc[streak_start_pos]

        # No marker on the line -- just print the score and the CAR value
        # where the increasing run started, in free space on the chart.
        ax.text(
            0.03, 0.95,
            f"CAR streak: {streak_length} (from {streak_start_value:.2f})",
            transform=ax.transAxes, fontsize=10, color=COLOR_STREAK_TEXT,
            va="top", ha="left",
            bbox=dict(boxstyle="round", facecolor="black", alpha=0.5, edgecolor=COLOR_STREAK_BOX_EDGE),
        )

    ax.set_title(
        f"{ticker} — From 52WH ({high_52w_date.strftime('%Y-%m-%d')})"
    )
    ax.set_xlabel("Days Since 52WH")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)
    ax.legend()


# Turn off unused axes
for i in range(len(tickers), len(axes)):
    axes[i].axis("off")

plt.tight_layout()
plt.show()