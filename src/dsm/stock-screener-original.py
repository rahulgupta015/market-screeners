# -------------------------------------------------------------------------
# CAR (Cumulative Average) + 30, 50, 200 DMA Super Breakout Scanner
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# -------------------------------------------------------------------------

import yfinance as yf          # Downloads historical stock data from Yahoo Finance
import pandas as pd            # Used for table-like data manipulation
import warnings                # Suppresses unnecessary warnings
import logging                 # Controls background process logs
from datetime import datetime  # Used to get today's date

# Suppress unnecessary Yahoo Finance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

# -------------------------------------------------------------------------
# Main Scanner Logic
# -------------------------------------------------------------------------

def advanced_stock_scanner(ticker_list):
    """
    Runs the breakout scanner on a list of stock tickers.
    Returns a DataFrame of stocks that meet all breakout conditions.
    """

    results = []  # Stores stocks that pass the breakout conditions
    today_date = datetime.now().strftime("%d-%m-%Y")

    print(f"Scanning {len(ticker_list)} stocks... Please wait.\n")

    for ticker in ticker_list:
        try:
            # 1. Download 2 years of daily data
            data = yf.download(ticker, period="2y", interval="1d", progress=False)

            # Skip stocks with insufficient data
            if data.empty or len(data) < 200:
                continue

            close_prices = data['Close'].squeeze()

            # 2. Calculate DMAs
            dma_30 = close_prices.rolling(window=30).mean().iloc[-1]
            dma_50 = close_prices.rolling(window=50).mean().iloc[-1]
            dma_200 = close_prices.rolling(window=200).mean().iloc[-1]

            # Current Market Price
            cmp = close_prices.iloc[-1]

            # 3. Distance from 200 DMA (%)
            dist_200_dma = ((cmp - dma_200) / dma_200) * 100

            # 4. Find 52-week high date (approx 252 trading days)
            last_1y_data = data.tail(252)
            high_date = last_1y_data['High'].squeeze().idxmax()

            # 5. CAR (Cumulative Average)
            car_data = close_prices.loc[high_date:]

            # Need at least 10 days after the high
            if len(car_data) < 10:
                continue

            car_values = car_data.expanding().mean()
            last_10_car = car_values.tail(10)

            # 6. Trend Check — CAR must be rising for last 10 days
            if last_10_car.is_monotonic_increasing:
                car_status = 'Positive'
            else:
                car_status = 'Negative'

            # 7. Breakout Conditions
            if (cmp > dma_30) and (cmp > dma_50) and (cmp > dma_200) and (car_status == 'Positive'):
                action = 'Positive Breakout'
            else:
                action = 'Avoid/Hold'

            # 8. Store only breakout stocks
            if action == 'Positive Breakout':
                results.append({
                    'Date': today_date,
                    'Stock': ticker.replace('.NS', ''),
                    'CMP': round(cmp, 2),
                    '30 DMA': round(dma_30, 2),
                    '50 DMA': round(dma_50, 2),
                    '200 DMA': round(dma_200, 2),
                    '200 DMA Dist %': round(dist_200_dma, 2),
                    'CAR Status': car_status,
                    'Action': action
                })

        except Exception:
            # Skip stock if any error occurs
            pass

    # Convert results to DataFrame
    df_positive = pd.DataFrame(results)

    # Sort by distance from 200 DMA
    if not df_positive.empty:
        df_positive = df_positive.sort_values(by='200 DMA Dist %', ascending=True)

    return df_positive

# -------------------------------------------------------------------------
# Execution
# -------------------------------------------------------------------------

my_stocks = [
    '360ONE.NS', 'ABB.NS', 'APLAPOLLO.NS', 'AUBANK.NS', 'ADANIENSOL.NS',
    'ADANIENT.NS', 'ADANIGREEN.NS', 'ADANIPORTS.NS', 'ADANIPOWER.NS', 'ABCAPITAL.NS',
    'ALKEM.NS', 'AMBER.NS', 'AMBUJACEM.NS', 'ANGELONE.NS', 'APOLLOHOSP.NS',
    'ASHOKLEY.NS', 'ASIANPAINT.NS', 'ASTRAL.NS', 'AUROPHARMA.NS', 'DMART.NS',
    'AXISBANK.NS', 'BSE.NS', 'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS',
    'BAJAJHLDNG.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BANKINDIA.NS', 'BDL.NS',
    'BEL.NS', 'BHARATFORG.NS', 'BHEL.NS', 'BPCL.NS', 'BHARTIARTL.NS',
    'BIOCON.NS', 'BLUESTARCO.NS', 'BOSCHLTD.NS', 'BRITANNIA.NS', 'CGPOWER.NS',
    'CANBK.NS', 'CDSL.NS', 'CHOLAFIN.NS', 'CIPLA.NS', 'COALINDIA.NS',
    'COCHINSHIP.NS', 'COFORGE.NS', 'COLPAL.NS', 'CAMS.NS', 'CONCOR.NS',
    'CROMPTON.NS', 'CUMMINSIND.NS', 'DLF.NS', 'DABUR.NS', 'DALBHARAT.NS',
    'DELHIVERY.NS', 'DIVISLAB.NS', 'DIXON.NS', 'DRREDDY.NS', 'ETERNAL.NS',
    'EICHERMOT.NS', 'EXIDEIND.NS', 'FORCEMOT.NS', 'NYKAA.NS', 'FORTIS.NS',
    'GAIL.NS', 'GVT&D.NS', 'GMRAIRPORT.NS', 'GLENMARK.NS', 'GODFRYPHLP.NS',
    'GODREJCP.NS', 'GODREJPROP.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCAMC.NS',
    'HDFCBANK.NS', 'HDFCLIFE.NS', 'HAVELLS.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS',
    'HAL.NS', 'HINDPETRO.NS', 'HINDUNILVR.NS', 'HINDZINC.NS', 'POWERINDIA.NS',
    'HYUNDAI.NS', 'ICICIBANK.NS', 'ICICIGI.NS', 'ICICIPRULI.NS', 'IDFCFIRSTB.NS',
    'ITC.NS', 'INDIANB.NS', 'IEX.NS', 'IOC.NS', 'IRFC.NS', 'IREDA.NS',
    'INDUSTOWER.NS', 'INDUSINDBK.NS', 'NAUKRI.NS', 'INFY.NS', 'INOXWIND.NS',
    'INDIGO.NS', 'JINDALSTEL.NS', 'JSWENERGY.NS', 'JSWSTEEL.NS', 'JIOFIN.NS',
    'JUBLFOOD.NS', 'KEI.NS', 'KPITTECH.NS', 'KALYANKJIL.NS', 'KAYNES.NS',
    'KFINTECH.NS', 'KOTAKBANK.NS', 'LTF.NS', 'LICHSGFIN.NS', 'LTM.NS',
    'LT.NS', 'LAURUSLABS.NS', 'LICI.NS', 'LODHA.NS', 'LUPIN.NS',
    'M&M.NS', 'MANAPPURAM.NS', 'MANKIND.NS', 'MARICO.NS', 'MARUTI.NS',
    'MFSL.NS', 'MAXHEALTH.NS', 'MAZDOCK.NS', 'MOTILALOFS.NS', 'MPHASIS.NS',
    'MCX.NS', 'MUTHOOTFIN.NS', 'NBCC.NS', 'NHPC.NS', 'NMDC.NS',
    'NTPC.NS', 'NATIONALUM.NS', 'NESTLEIND.NS', 'NAM-INDIA.NS', 'NUVAMA.NS',
    'OBEROIRLTY.NS', 'ONGC.NS', 'OIL.NS', 'PAYTM.NS', 'OFSS.NS',
    'POLICYBZR.NS', 'PGEL.NS', 'PIIND.NS', 'PNBHOUSING.NS', 'PAGEIND.NS',
    'PATANJALI.NS', 'PERSISTENT.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'POLYCAB.NS',
    'PFC.NS', 'POWERGRID.NS', 'PREMIERENE.NS', 'PRESTIGE.NS', 'PNB.NS',
    'RBLBANK.NS', 'RECLTD.NS', 'RADICO.NS', 'RVNL.NS', 'RELIANCE.NS',
    'SBICARD.NS', 'SBILIFE.NS', 'SHREECEM.NS', 'SRF.NS', 'MOTHERSON.NS',
    'SHRIRAMFIN.NS', 'SIEMENS.NS', 'SOLARINDS.NS', 'SONACOMS.NS', 'SBIN.NS',
    'SAIL.NS', 'SUNPHARMA.NS', 'SUPREMEIND.NS', 'SUZLON.NS', 'SWIGGY.NS',
    'TATACONSUM.NS', 'TVSMOTOR.NS', 'TCS.NS', 'TATAELXSI.NS', 'TMPV.NS',
    'TATAPOWER.NS', 'TATASTEEL.NS', 'TECHM.NS', 'FEDERALBNK.NS', 'INDHOTEL.NS',
    'PHOENIXLTD.NS', 'TITAN.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'TIINDIA.NS',
    'UNOMINDA.NS', 'UPL.NS', 'ULTRACEMCO.NS', 'UNIONBANK.NS', 'UNITDSPR.NS',
    'VBL.NS', 'VEDL.NS', 'VMM.NS', 'IDEA.NS', 'VOLTAS.NS',
    'WAAREEENER.NS', 'WIPRO.NS', 'YESBANK.NS', 'ZYDUSLIFE.NS'
]

positive_breakout_data = advanced_stock_scanner(my_stocks)

print("\n--- Final List: POSITIVE BREAKOUT Stocks ---")
if positive_breakout_data.empty:
    print("No stock passed all breakout conditions today.")
else:
    print(positive_breakout_data.to_string(index=False))
    positive_breakout_data.to_excel("Final_Breakout_List.xlsx", index=False)
    print("\nSaved as 'Final_Breakout_List.xlsx'")
