# Scanner compatibility command

The implementation now lives under `dsm.model`, `dsm.service`, and
`dsm.cli`. This directory retains `dma-and-car.py` as a direct-execution
compatibility wrapper:

```bash
uv run src/dsm/screeners/dma-and-car.py
uv run src/dsm/screeners/dma-and-car.py --test
uv run src/dsm/screeners/dma-and-car.py --my
```

Use `uv run python -m dsm` for the primary project entry point.
