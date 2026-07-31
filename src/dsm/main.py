from pathlib import Path
from runpy import run_path

def main():
    """Run the DMA and CAR scanner used by every project entry point."""
    scanner = Path(__file__).parent / "screeners" / "dma-and-car.py"
    run_path(scanner, run_name="__main__")


if __name__ == "__main__":
    main()
