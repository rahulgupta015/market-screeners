from dataclasses import dataclass


@dataclass
class Display:
    """Formatted and colorized values for one console table row."""

    stock: str
    market_cap: str = "-"
    cmp: str = "-"
    dma_bo: str = ""
    car_bo: str = ""
    mac_bo: str = ""
    rsi: str = "-"
    ema_8: str = "-"
    dma_30: str = "-"
    dma_50: str = "-"
    dma_100: str = "-"
    dma_200: str = "-"
    shift_pct: str = "-"
    car: str = "-"
    zone: str = "-"
    high_date: str = "-"
    low_date: str = "-"
    days_since_low: str = "-"
    high_price: str = "-"
    low_price: str = "-"

    _FIELDS = {
        "Stock": "stock",
        "Market Cap ($B)": "market_cap",
        "CMP": "cmp",
        "DMA BO": "dma_bo",
        "CAR BO": "car_bo",
        "MAC BO": "mac_bo",
        "RSI": "rsi",
        "EMA 8": "ema_8",
        "30 DMA": "dma_30",
        "50 DMA": "dma_50",
        "100 DMA": "dma_100",
        "200 DMA": "dma_200",
        "Shift %": "shift_pct",
        "CAR": "car",
        "Zone": "zone",
        "52W High": "high_date",
        "52W Low": "low_date",
        "Days Since 52W Low": "days_since_low",
        "52W High Price": "high_price",
        "52W Low Price": "low_price",
    }

    def __getitem__(self, key):
        return getattr(self, self._FIELDS[key])

    def __setitem__(self, key, value):
        setattr(self, self._FIELDS[key], value)
