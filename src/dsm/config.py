# Stock lists sourced from Tickers.java (daily-stock-monitor project) and community contributions
# Organized by market cap category, largest first

# Market Cap > $200B
OVER_200B = [
    "AAPL", "ABBV", "ACN", "ADBE", "AMZN", "AVGO", "BAC", "BLK", "BRK-B", "CAT", "COST",
    "CRM", "CVX", "DIS", "GE", "GOOG", "GOOGL", "HD", "HON", "INTU", "JNJ", "JPM", "KO",
    "LIN", "LLY", "LMT", "MA", "MCD", "META", "MRK", "MSFT", "NFLX", "NKE", "NVDA", "ORCL",
    "PEP", "PFE", "PG", "PM", "QCOM", "SBUX", "TMO", "TSLA", "UNH", "V", "WMT", "XOM",
]

# Market Cap $100B - $200B
BETWEEN_100B_200B = [
    "ADP", "AMGN", "AMD", "ANET", "APD", "AXP", "BA", "BKNG", "BMY", "CB", "CEG", "CHTR",
    "CMCSA", "CME", "COP", "CSCO", "CSX", "CTAS", "DUK", "EL", "ETN", "FDX", "GILD", "GM", "GS",
    "HUM", "IBM", "ICE", "INTC", "ISRG", "ITW", "LHX", "LOW", "LRCX", "MAR", "MDLZ", "MDT", "MS", "MU",
    "NOW", "NSC", "NXPI", "OXY", "PANW", "PCAR", "PLD", "REGN", "ROST", "SCHW", "SO", "SPG", "TGT",
    "TJX", "TMUS", "TXN", "UNP", "UPS", "USB", "VZ", "WFC", "ZTS",
]

# Market Cap $50B - $100B
BETWEEN_50B_100B = [
    "ADI", "AMAT", "APTV", "BIIB", "BK", "CDNS", "CL", "COF", "CPRT", "CVS", "DHR", "ECL", "EMR",
    "EXC", "FIS", "FISV", "GIS", "GLW", "HCA", "HES", "HLT", "IDXX", "ILMN", "KHC", "KMI", "KLAC", "KR", "LRCX",
    "LULU", "MNST", "MRNA", "NOC", "NTRS", "NUE", "ORLY", "PAYX", "PGR", "PH", "PPG", "PSA", "PYPL",
    "REGN", "ROST", "RSG", "SBAC", "SCHW", "SHW", "SLB", "SYY", "T", "TRV", "WELL", "WM",
]

# Market Cap < $50B (includes former 10B-50B range and additional stocks)
BELOW_50B = [
    "AEP", "AFL", "AIG", "ALGN", "ALL", "AMCR", "AMT", "AON", "APA", "ARE", "ATO", "AVB", "AWK",
    "BALL", "BAX", "BDX", "BEN", "BILL", "BKR", "BXP", "C", "CAG", "CCI", "CARR", "CBRE", "CDW", "CHD",
    "CINF", "CLX", "CMS", "CNP", "CRL", "CRWD", "CTSH", "D", "DAL", "DD", "DE", "DG", "DHI", "DOV",
    "DRI", "DTE", "EA", "EBAY", "ED", "EFX", "EIX", "EL", "ELV", "EOG", "EQIX", "EQR", "ESS", "ETR",
    "EVRG", "FAST", "FE", "FITB", "FOX", "FOXA", "FTNT", "GD", "GPC", "GRMN", "HBAN", "HIG",
    "HPQ", "HSY", "HST", "IEX", "INCY", "IP", "IQV", "IR", "IT", "JBHT", "JKHY", "JCI", "KEY",
    "KEYS", "KIM", "L", "LDOS", "LEN", "LH", "LKQ", "LNT", "LUV", "LYB", "MCHP",
    "MET", "MKC", "MLM", "MMC", "MO", "MPWR", "MRVL", "MTB", "MTCH", "MTD", "NDAQ", "NEM",
    "OGN", "OKE", "OMC", "ON", "OTIS", "PENN", "PKG", "PNC", "PNR", "PODD", "POOL",
    "PRU", "PTC", "PWR", "QRVO", "RCL", "RJF", "RMD", "RSG", "SBAC", "SEDG",
    "SJM", "SLB", "SNA", "SNPS", "STT", "STZ", "SWK", "SWKS", "SYF", "TDG", "TEL", "TFX",
    "TROW", "TSCO", "TT", "TYL", "UAL", "UDR", "UHS", "ULTA", "VICI", "VMC", "VRSK", "VTR",
    "VTRS", "WAB", "WAT", "WBD", "WEC", "WMB", "WST", "WY", "YUM",
]

# ETFs with AUM > $1B
ETF_OVER_1B = [
    "GLD", "IBIT", "IVV", "IWM", "MAGS", "QQQ", "SCHD", "SLV", "SMH", "SOXX", "SPY", "TOPT", "VOO", "VTI",
    "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLV", "XLY",
]

# Leveraged & Inverse ETFs
LEVERAGED = [
    "AAPU", "AVL", "DIA", "GGLL", "LLYX", "METU", "MSFU", "NFXL", "NVDL", "ORCX", "QLD", "SSO", "TQQQ", "UPRO", "USD", "UWM",
]

# Other stocks & cryptocurrencies
OTHERS = ["BIDU", "BSX", "BULL", "DJT", "DOCU", "DDOG", "INFY", "JD", "KDP", "LCID", "MELI", "OKTA", "SOFI", "SPLK", "TEAM", "VRTX", "WDAY", "ZM"]

# Test set for quick validation
FOR_TESTING = ["WFC", "UPS", "AIG", "NDAQ", "OMC", "IQV"]

def get_all_tickers():
    """Returns combined list of all stock tickers"""
    return (
        OVER_200B
        + BETWEEN_100B_200B
        + BETWEEN_50B_100B
        + BELOW_50B
        + ETF_OVER_1B
        + LEVERAGED
        + OTHERS
    )

def get_test_tickers():
    """Returns small test set of tickers for quick testing"""
    return FOR_TESTING

def get_combined_universe():
    """Returns deduplicated combined universe (all tickers, no duplicates)"""
    return sorted(set(get_all_tickers()))


def get_ticker_category(ticker):
    """Returns the market cap category for a given ticker"""
    if ticker in OVER_200B:
        return "OVER_200B"
    elif ticker in BETWEEN_100B_200B:
        return "BETWEEN_100B_200B"
    elif ticker in BETWEEN_50B_100B:
        return "BETWEEN_50B_100B"
    elif ticker in BELOW_50B:
        return "BELOW_50B"
    elif ticker in ETF_OVER_1B:
        return "ETF_OVER_1B"
    elif ticker in LEVERAGED:
        return "LEVERAGED"
    elif ticker in OTHERS:
        return "OTHERS"
    else:
        return "UNKNOWN"


CATEGORY_DISPLAY_NAMES = {
    "OVER_200B": "OVER_200B (>$200B)",
    "BETWEEN_100B_200B": "BETWEEN_100B_200B ($100B-$200B)",
    "BETWEEN_50B_100B": "BETWEEN_50B_100B ($50B-$100B)",
    "BELOW_50B": "BELOW_50B (<$50B)",
    "ETF_OVER_1B": "ETF_OVER_1B (>$1B AUM)",
    "LEVERAGED": "LEVERAGED (2x/3x/Inverse)",
    "OTHERS": "OTHERS",
}
