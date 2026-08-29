#!/bin/bash

# Clear all files in the data folder except base screener files (screener_MON, screener_TUE, etc.)

DATA_DIR="data"

if [ ! -d "$DATA_DIR" ]; then
    echo "Error: $DATA_DIR directory not found"
    exit 1
fi

echo "Clearing files in $DATA_DIR (preserving screener_MON, screener_TUE, etc. and preview_dark.html)..."

# Define the checked-in files to preserve
PRESERVE_PATTERN="screener_(MON|TUE|WED|THU|FRI|SAT|SUN)|preview_dark\.html$"

# Find all files in data folder and delete them if they don't match the preserve pattern
find "$DATA_DIR" -maxdepth 1 -type f -regextype posix-extended ! -regex ".*/($PRESERVE_PATTERN)" -delete

echo "Done! Preserved base screener files (screener_MON through screener_SUN) and preview_dark.html"