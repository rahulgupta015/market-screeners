import re
from datetime import datetime

from market_screeners.model.calc import Calc
from market_screeners.model.display import Display

RESET = "\033[0m"
RED = "\033[38;5;196m"
GREEN = "\033[92m"
YELLOW = "\033[38;5;229m"
PURPLE = "\033[35m"
ANSI_RE = re.compile(r"\033\[[0-9;]*m")

ZONE_COLOR = {
    "B++": PURPLE,
    "B+": GREEN,
    "B-": YELLOW,
    "B--": RED,
}

BREAKOUT_CODES = (
    ("D", "dma_bo"),
    ("C", "car_bo"),
    ("M", "mac_bo"),
)
BREAKOUT_CODE_ORDER = {"DCM": 0, "DC": 1, "DM": 2, "CM": 3, "D": 4, "C": 5, "M": 6}


def visible_len(value):
    return len(ANSI_RE.sub("", value))


def vjust(value, width):
    return value + (" " * max(0, width - visible_len(value)))


def colorize(value, color):
    if not value or value == "-" or color is None:
        return value
    return f"{color}{value}{RESET}"


def rsi_color(rsi):
    if rsi <= 25:
        return PURPLE
    if rsi <= 40:
        return GREEN
    if rsi <= 65:
        return YELLOW
    return RED


def car_color(score):
    if score < 2:
        return RED
    if score < 5:
        return YELLOW
    if score < 10:
        return GREEN
    return PURPLE


def rvol_color(value):
    if value >= 1.5:
        return GREEN
    if value >= 0.9:
        return YELLOW
    return None


def robv_color(obv, obv_sma_20):
    if obv is None or obv_sma_20 is None:
        return None
    if obv > 0 and obv > obv_sma_20:
        return GREEN
    if obv < 0 and obv < obv_sma_20:
        return RED
    return None


def days_since_low_color(days):
    if days > 90:
        return PURPLE
    if days >= 30:
        return GREEN
    return None


def breakout_code(calc: Calc):
    return "".join(code for code, field in BREAKOUT_CODES if getattr(calc, field))


def shift_color(shift_pct):
    if shift_pct > 10:
        return PURPLE
    if shift_pct >= 0.01:
        return GREEN
    if shift_pct >= -10:
        return YELLOW
    return RED


def format_row(calc: Calc) -> Display:
    """Convert one raw calculation record into a display record."""
    row = Display(
        stock=calc.ticker.symbol,
        dcm=breakout_code(calc),
    )

    if calc.ticker.market_cap_b is not None:
        row.market_cap = f"{calc.ticker.market_cap_b}"
    if calc.cmp is not None:
        row.cmp = f"{round(calc.cmp, 2)}"
    if calc.rvol is not None:
        row["RVOL"] = colorize(f"{calc.rvol:.2f}", rvol_color(calc.rvol))
    if calc.robv is not None:
        row["ROBV"] = colorize(
            f"{calc.robv:+.2f}", robv_color(calc.obv, calc.obv_sma_20)
        )
    if calc.rsi is not None:
        row.rsi = colorize(f"{calc.rsi:.2f}", rsi_color(calc.rsi))
    if calc.kst is not None:
        row["KST"] = colorize("▲" if calc.kst == 1 else "▼", GREEN if calc.kst == 1 else RED)
    if calc.ema_8 is not None:
        ema = f"{calc.ema_8:.2f}"
        row.ema_8 = colorize(ema, GREEN) if calc.cmp is not None and calc.cmp > calc.ema_8 else ema

    for label, value in (
        ("30 DMA", calc.dma_30),
        ("50 DMA", calc.dma_50),
        ("100 DMA", calc.dma_100),
        ("200 DMA", calc.dma_200),
    ):
        if value is not None:
            formatted = f"{round(value, 2)}"
            row[label] = colorize(formatted, GREEN) if calc.cmp is not None and calc.cmp > value else formatted

    if calc.shift_pct is not None:
        row.shift_pct = colorize(f"{calc.shift_pct:+06.2f}", shift_color(calc.shift_pct))
    if calc.zone is not None:
        zone_color = ZONE_COLOR.get(calc.zone)
        row.zone = colorize(calc.zone, zone_color) if zone_color else calc.zone
    if calc.car is not None:
        row.car = colorize(str(calc.car), car_color(calc.car))
    if calc.high_date is not None:
        row.high_date = calc.high_date.strftime("%m-%d-%y")
    if calc.days_since_low is not None:
        days = f"{calc.days_since_low:+d}"
        days_color = days_since_low_color(calc.days_since_low)
        row.days_since_low = colorize(days, days_color) if days_color else days

    return row


DISPLAY_COLS = [
    "Stock", "Market Cap ($B)", "CMP", "DCM", "RVOL", "ROBV", "RSI", "KST", "EMA 8",
    "30 DMA", "50 DMA", "100 DMA", "200 DMA", "Shift %", "CAR", "Zone",
    "Days Since 52W Low", "Stock",
]

SPLIT_HEADERS = {
    "Market Cap ($B)": ("Cap", "($B)"),
    "DCM": ("DCM", ""),
    "RVOL": ("RVOL", ""),
    "ROBV": ("ROBV", ""),
    "RSI": ("RSI", ""),
    "KST": ("KST", ""),
    "EMA 8": ("8", "EMA"),
    "30 DMA": ("30", "DMA"),
    "50 DMA": ("50", "DMA"),
    "100 DMA": ("100", "DMA"),
    "200 DMA": ("200", "DMA"),
    "Shift %": ("Shift%", "200 DMA"),
    "Days Since 52W Low": ("52WL -", "52WH"),
}


def _table_lines(rows, widths):
    columns = DISPLAY_COLS
    separator = "+-" + "-+-".join("-" * widths[column] for column in columns) + "-+"
    header_one = "| " + " | ".join(
        SPLIT_HEADERS[column][0].ljust(widths[column]) if column in SPLIT_HEADERS else "".ljust(widths[column])
        for column in columns
    ) + " |"
    header_two = "| " + " | ".join(
        SPLIT_HEADERS[column][1].ljust(widths[column]) if column in SPLIT_HEADERS else column.ljust(widths[column])
        for column in columns
    ) + " |"

    lines = [separator, header_one, header_two, separator]
    for row in rows:
        lines.append("| " + " | ".join(vjust(str(row[column]), widths[column]) for column in columns) + " |")
    lines.append(separator)
    return lines


def print_results(calculations: list[Calc]) -> None:
    """Format, sort, and print raw calculation records."""
    if not calculations:
        print("No results to display.")
        return

    breakout_calculations = [
        calc for calc in calculations if calc.dma_bo or calc.car_bo or calc.mac_bo
    ]
    others = [
        calc for calc in calculations
        if not calc.dma_bo and not calc.car_bo and not calc.mac_bo
    ]
    breakout_calculations.sort(
        key=lambda calc: (
            BREAKOUT_CODE_ORDER[breakout_code(calc)],
            calc.shift_pct if calc.shift_pct is not None else float("inf"),
        )
    )
    others.sort(key=lambda calc: calc.ticker.symbol)

    breakout_rows = [format_row(calc) for calc in breakout_calculations]
    other_rows = [format_row(calc) for calc in others]
    all_rows = breakout_rows + other_rows
    widths = {}
    for column in DISPLAY_COLS:
        value_width = max((visible_len(str(row[column])) for row in all_rows), default=0)
        header_width = max(map(len, SPLIT_HEADERS[column])) if column in SPLIT_HEADERS else len(column)
        widths[column] = max(header_width, value_width)

    print(f"Date: {datetime.now().strftime('%b-%d-%Y')}\n")
    print("--- Breakouts (sorted by DCM, then Shift% asc) ---")
    print("DCM: D = DMA BO, C = CAR BO, M = MAC BO.\n")
    if breakout_rows:
        for line in _table_lines(breakout_rows, widths):
            print(line)
    else:
        print("(none)")

    print("\n--- Others (sorted by Symbol) ---\n")
    for line in _table_lines(other_rows, widths):
        print(line)
    print(
        f"\nTotal: {len(calculations)} symbols "
        f"({len(breakout_rows)} breakouts, {len(other_rows)} others)\n"
    )


def display_tickers(calculations: list[Calc]) -> None:
    """Print calculation errors and render the calculation records."""
    for calc in calculations:
        if calc.error:
            level, message = calc.error
            print(f"  [{level}] {calc.ticker.symbol}: {message}")
    print_results(calculations)
