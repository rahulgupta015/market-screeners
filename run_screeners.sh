#!/usr/bin/env bash
# run_screeners.sh
#
# Runs all three market-screeners screeners back to back:
#   1. Multi-Indicator Screener
#   2. Institutional Accumulation Scanner
#   3. Option Analysis Scanner
#
# Usage (from the repo root, in Git Bash):
#   ./run_screeners.sh            # defaults to --my (your watch list)
#   ./run_screeners.sh --test     # first 10 symbols
#   ./run_screeners.sh --my       # personal watch list
#   ./run_screeners.sh            # full universe (no flag)
#
# Any flags you pass are forwarded as-is to all three screeners, e.g.:
#   ./run_screeners.sh --export-html data/custom.html

set -e

MODE=("${@:---my}")

# Activate the local .venv if it exists (Git Bash on Windows uses Scripts/,
# macOS/Linux uses bin/). Falls back to `uv run` if no venv is found, which
# manages the environment on its own.
if [ -f ".venv/Scripts/activate" ]; then
    source ".venv/Scripts/activate"
    RUN_CMD="python"
elif [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
    RUN_CMD="python"
else
    echo "No .venv found — falling back to 'uv run python'."
    RUN_CMD="uv run python"
fi

echo "=================================================="
echo "1/3  Multi-Indicator Screener"
echo "=================================================="
$RUN_CMD -m market_screeners.screeners.multi_indicator "${MODE[@]}"

echo
echo "=================================================="
echo "2/3  Institutional Accumulation Scanner"
echo "=================================================="
$RUN_CMD -m market_screeners.screeners.institution "${MODE[@]}"

echo
echo "=================================================="
echo "3/3  Option Analysis Scanner"
echo "=================================================="
$RUN_CMD -m market_screeners.screeners.option_analysis "${MODE[@]}"

echo
echo "All three screeners finished. Check the data/ folder for HTML reports."
