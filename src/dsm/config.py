# Stock lists sourced from Tickers.java (daily-stock-monitor project)
# Organized by market cap category, largest first

SP500_NASDAQ_OVER_200B = [
    "AAPL", "ABBV", "ACN", "ADBE", "AMZN", "AVGO", "BAC", "BLK", "BRK-B", "CAT", "COST",
    "CRM", "CVX", "DIS", "GE", "GOOG", "GOOGL", "HD", "HON", "INTU", "JNJ", "JPM", "KO",
    "LIN", "LLY", "LMT", "MA", "MCD", "META", "MRK", "MSFT", "NFLX", "NKE", "NVDA", "ORCL",
    "PEP", "PFE", "PG", "PM", "QCOM", "SBUX", "TMO", "TSLA", "UNH", "V", "WMT", "XOM",
]

SP500_NASDAQ_BETWEEN_100B_200B = [
    "ADP", "AMGN", "AMD", "ANET", "APD", "AXP", "BA", "BKNG", "BMY", "CB", "CEG", "CHTR",
    "CMCSA", "CME", "COP", "CSCO", "CSX", "CTAS", "DUK", "EL", "FDX", "GILD", "GM", "GS",
    "HUM", "IBM", "ICE", "INTC", "ISRG", "LOW", "LRCX", "MAR", "MDLZ", "MDT", "MS", "MU",
    "NOW", "NXPI", "OXY", "PANW", "PCAR", "PLD", "REGN", "ROST", "SCHW", "SO", "SPG", "TGT",
    "TJX", "TMUS", "TXN", "UNP", "UPS", "USB", "VZ", "WFC", "ZTS",
]

SP500_NASDAQ_BETWEEN_50B_100B = [
    "ADI", "AMAT", "APTV", "BIIB", "BK", "CDNS", "CL", "COF", "CPRT", "CVS", "DHR", "EMR",
    "EXC", "FIS", "FISV", "GIS", "GLW", "HCA", "HLT", "IDXX", "ILMN", "KHC", "KMI", "LULU",
    "MNST", "MRNA", "NOC", "PAYX", "PGR", "PH", "PPG", "PYPL", "SYY", "T", "TRV", "WELL",
    "WM",
]

SP500_NASDAQ_BETWEEN_10B_50B = [
    "AEP", "AFL", "AIG", "ALGN", "ALL", "AMCR", "AON", "APA", "ARE", "ATO", "AVB", "AWK",
    "BALL", "BAX", "BDX", "BEN", "BILL", "BKR", "BXP", "CAG", "CARR", "CBRE", "CDW", "CHD",
    "CINF", "CLX", "CMS", "CNP", "CRL", "CTSH", "D", "DAL", "DD", "DE", "DG", "DHI", "DOV",
    "DRI", "DTE", "EA", "EBAY", "ED", "EFX", "EIX", "ELV", "EOG", "EQIX", "EQR", "ESS", "ETR",
    "EVRG", "FAST", "FE", "FITB", "FOX", "FOXA", "FTNT", "GD", "GPC", "GRMN", "HBAN", "HIG",
    "HPQ", "HSY", "HST", "IEX", "INCY", "IP", "IQV", "IR", "IT", "JBHT", "JKHY", "JCI", "KEY",
    "KEYS", "KIM", "KLAC", "KR", "L", "LDOS", "LEN", "LH", "LKQ", "LNT", "LUV", "LYB", "MCHP",
    "MKC", "MLM", "MO", "MPWR", "MTB", "MTCH", "MTD", "NDAQ", "NEM", "NTRS", "NUE", "NVCR",
    "NVR", "OGN", "OKE", "OMC", "ON", "OTIS", "PENN", "PKG", "PNC", "PNR", "PODD", "POOL",
    "PRU", "PSA", "PTC", "PWR", "QRVO", "RCL", "RJF", "RMD", "RSG", "SBAC", "SEDG", "SHW",
    "SJM", "SLB", "SNA", "SNPS", "STT", "STZ", "SWK", "SWKS", "SYF", "TDG", "TEL", "TFX",
    "TROW", "TSCO", "TT", "TYL", "UAL", "UDR", "UHS", "ULTA", "VICI", "VMC", "VRSK", "VTR",
    "VTRS", "WAB", "WAT", "WBD", "WEC", "WMB", "WY", "YUM",
]

LEVERAGED = [
    "AAPU", "AVL", "GGLL", "LLYX", "METU", "MSFU", "NFXL", "NVDL", "ORCX", "TQQQ", "UPRO",
]

ETF = [
    "GLD", "MAGS", "QQQ", "IBIT", "SCHD", "SLV", "SMH", "SPY", "TOPT", "XLF", "XLK",
]

OTHERS = ["BSX", "BULL", "DJT", "INFY", "SOFI"]

FOR_TESTING = ["WFC", "AIG", "NDAQ", "OMC", "IQV"]

def get_all_tickers():
    """Returns combined list of all stock tickers"""
    return (
        SP500_NASDAQ_OVER_200B
        + SP500_NASDAQ_BETWEEN_100B_200B
        + SP500_NASDAQ_BETWEEN_50B_100B
        + SP500_NASDAQ_BETWEEN_10B_50B
        + LEVERAGED
        + ETF
        + OTHERS
    )

def get_test_tickers():
    """Returns small test set of tickers for quick testing"""
    return FOR_TESTING
