#!/bin/bash

# Clear all files in the data folder except base screener files (screener_MON, screener_TUE, etc.)

DATA_DIR="data"

if [ ! -d "$DATA_DIR" ]; then
    echo "Error: $DATA_DIR directory not found"
    exit 1
fi

echo "Clearing files in $DATA_DIR (preserving screener_MON.html ... screener_SUN.html and preview_dark.html)..."

# Explicit list of checked-in files to preserve
PRESERVE_FILES=(
    "screener_MON.html"
    "screener_TUE.html"
    "screener_WED.html"
    "screener_THU.html"
    "screener_FRI.html"
    "screener_SAT.html"
    "screener_SUN.html"
    "preview_dark.html"
)

for f in "$DATA_DIR"/*; do
    [ -f "$f" ] || continue
    fname="$(basename "$f")"
    keep=false
    for p in "${PRESERVE_FILES[@]}"; do
        if [ "$fname" == "$p" ]; then
            keep=true
            break
        fi
    done
    if [ "$keep" = false ]; then
        rm -f "$f"
    fi
done

echo "Done! Preserved: ${PRESERVE_FILES[*]}"