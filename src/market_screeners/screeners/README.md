# Scanner compatibility command

The implementation now lives under `market_screeners.model`,
`market_screeners.service`, and `market_screeners.cli`. This directory retains
`dma_car_mac.py` as a direct-execution
compatibility wrapper:

```bash
uv run src/market_screeners/screeners/dma_car_mac.py
uv run src/market_screeners/screeners/dma_car_mac.py --test
uv run src/market_screeners/screeners/dma_car_mac.py --my
```

Use `uv run python -m market_screeners` for the primary project entry point.
