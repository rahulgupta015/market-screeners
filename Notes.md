## Staged Collar – Technical Steps

1. **Open Long ITM Put**
    - Buy an in‑the‑money put (e.g., strike = 100 when stock ≈ 102–105).
    - This establishes downside protection *before* owning shares.

2. **Place Limit Buy Order at Put Strike**
    - Set a limit order to go long the stock at the same strike as the put.
    - If price reaches the strike, the stock position is opened at your chosen level.

3. **Position Becomes Married Put**
    - Once the limit order fills, you now hold:
        - Long shares
        - Long ITM put
    - This locks in a defined maximum loss.

4. **Sell OTM Covered Call**
    - After owning shares, sell an out‑of‑the‑money call (e.g., strike = 110).
    - This converts the position into a **covered call short**, reducing or offsetting the put cost.

5. **Completed Collar Structure**
    - Long Stock
    - Long ITM Put
    - Short OTM Covered Call
    - Result: capped downside, capped upside, no stop loss required.

6. **If Limit Order Never Fills**
    - You simply keep or sell the ITM put.
    - If the stock drops, the put gains value and can be closed for profit.
