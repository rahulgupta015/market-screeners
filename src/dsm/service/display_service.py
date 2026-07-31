import re
from datetime import datetime

from dsm.model.calc import Calc
from dsm.model.display import Display

RESET = "\033[0m"
RED = "\033[38;5;196m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
ORANGE = "\033[38;5;214m"
PURPLE = "\033[38;5;135m"
GREEN_CHECK = f"{GREEN}\u2714{RESET}"
ANSI_RE = re.compile(r"\033\[[0-9;]*m")

ZONE_COLOR = {
    "B++": PURPLE,
    "B+": GREEN,
    "U": YELLOW,
    "B-": ORANGE,
    "B--": RED,
}


def visible_len(value):
    return len(ANSI_RE.sub("", value))


def vjust(value, width):
    return value + (" " * max(0, width - visible_len(value)))


def colorize(value, color):
    if not value or value == "-":
        return value
    return f"{color}{value}{RESET}"


def car_color(score):
    if score <= 1:
        return RED
    if score <= 4:
        return ORANGE
    if score <= 7:
        return YELLOW
    return GREEN


def shift_color(shift_pct):
    if shift_pct > 10:
        return PURPLE
    if shift_pct >= 0.01:
        return GREEN
    if shift_pct >= -10:
        return ORANGE
    return RED


def format_row(calc: Calc) -> Display:
    """Convert one raw calculation record into a display record."""
    row = Display(
        stock=calc.ticker.symbol,
        dma_bo=GREEN_CHECK if calc.dma_bo else "",
        car_bo=GREEN_CHECK if calc.car_bo else "",
    )

    if calc.ticker.market_cap_b is not None:
        row.market_cap = f"{calc.ticker.market_cap_b}"
    if calc.cmp is not None:
        row.cmp = f"{round(calc.cmp, 2)}"
    if calc.rsi is not None:
        row.rsi = f"{calc.rsi:.2f}"
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
        row.zone = colorize(calc.zone, ZONE_COLOR[calc.zone])
    if calc.car is not None:
        row.car = colorize(str(calc.car), car_color(calc.car))
    if calc.high_date is not None:
        row.high_date = calc.high_date.strftime("%m-%d-%y")
    if calc.low_date is not None:
        row.low_date = calc.low_date.strftime("%m-%d-%y")
    if calc.high_price is not None:
        row.high_price = f"{calc.high_price:.2f}"
    if calc.low_price is not None:
        row.low_price = f"{calc.low_price:.2f}"
    if calc.days_since_low is not None:
        days = f"{calc.days_since_low:+d}"
        row.days_since_low = colorize(days, GREEN) if calc.days_since_low > 0 else days

    return row


DISPLAY_COLS = [
    "Stock", "Market Cap ($B)", "CMP", "DMA BO", "CAR BO", "RSI", "EMA 8",
    "30 DMA", "50 DMA", "100 DMA", "200 DMA", "Shift %", "CAR", "Zone",
    "52W High", "52W Low", "Days Since 52W Low", "52W High Price", "52W Low Price",
]

SPLIT_HEADERS = {
    "Market Cap ($B)": ("Cap", "($B)"),
    "DMA BO": ("DMA", "BO"),
    "CAR BO": ("CAR", "BO"),
    "RSI": ("RSI", ""),
    "EMA 8": ("8", "EMA"),
    "30 DMA": ("30", "DMA"),
    "50 DMA": ("50", "DMA"),
    "100 DMA": ("100", "DMA"),
    "200 DMA": ("200", "DMA"),
    "Shift %": ("Shift%", "200 DMA"),
    "52W High": ("52WH", "Date"),
    "52W Low": ("52WL", "Date"),
    "Days Since 52W Low": ("52WL -", "52WH"),
    "52W High Price": ("52WH", "Price"),
    "52W Low Price": ("52WL", "Price"),
}


def _table_lines(rows, widths):
    separator = "+-" + "-+-".join("-" * widths[column] for column in DISPLAY_COLS) + "-+"
    header_one = "| " + " | ".join(
        SPLIT_HEADERS[column][0].ljust(widths[column]) if column in SPLIT_HEADERS else "".ljust(widths[column])
        for column in DISPLAY_COLS
    ) + " |"
    header_two = "| " + " | ".join(
        SPLIT_HEADERS[column][1].ljust(widths[column]) if column in SPLIT_HEADERS else column.ljust(widths[column])
        for column in DISPLAY_COLS
    ) + " |"

    lines = [separator, header_one, header_two, separator]
    for row in rows:
        lines.append("| " + " | ".join(vjust(str(row[column]), widths[column]) for column in DISPLAY_COLS) + " |")
    lines.append(separator)
    return lines


def print_results(calculations: list[Calc]) -> None:
    """Format, sort, and print raw calculation records."""
    if not calculations:
        print("No results to display.")
        return

    breakout = [calc for calc in calculations if calc.dma_bo or calc.car_bo]
    others = [calc for calc in calculations if not (calc.dma_bo or calc.car_bo)]
    breakout.sort(key=lambda calc: calc.shift_pct if calc.shift_pct is not None else float("inf"))
    others.sort(key=lambda calc: calc.ticker.symbol)

    breakout_rows = [format_row(calc) for calc in breakout]
    other_rows = [format_row(calc) for calc in others]
    all_rows = breakout_rows + other_rows
    widths = {}
    for column in DISPLAY_COLS:
        value_width = max((visible_len(str(row[column])) for row in all_rows), default=0)
        header_width = max(map(len, SPLIT_HEADERS[column])) if column in SPLIT_HEADERS else len(column)
        widths[column] = max(header_width, value_width)

    print(f"Date: {datetime.now().strftime('%b-%d-%Y')}\n")
    print("--- Breakouts (DMA BO / CAR BO) - sorted by 200 DMA Shift % asc ---\n")
    if breakout_rows:
        for line in _table_lines(breakout_rows, widths):
            print(line)
    else:
        print("(none)")

    print("\n--- All Other Symbols - sorted by Symbol ---\n")
    for line in _table_lines(other_rows, widths):
        print(line)
    print(f"\nTotal: {len(calculations)} symbols ({len(breakout_rows)} breakouts, {len(other_rows)} others)\n")


def display_tickers(calculations: list[Calc]) -> None:
    """Print calculation errors and render the calculation records."""
    for calc in calculations:
        if calc.error:
            level, message = calc.error
            print(f"  [{level}] {calc.ticker.symbol}: {message}")
    print_results(calculations)
