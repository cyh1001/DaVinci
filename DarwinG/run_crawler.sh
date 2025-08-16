#!/bin/bash
# Linux shell script to run Forest Market detailed crawler
# Edit the settings below directly in this file

echo "Forest Market Detailed Crawler - Linux"
echo "======================================"

# === EDIT THESE SETTINGS ===
INPUT_FILE="fm_data/url/fm_url.csv"
# MAX_PRODUCTS=10
CONCURRENT_WORKERS=3
# === END SETTINGS ===

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' not found"
    exit 1
fi

echo "Input file: $INPUT_FILE"
# echo "Max products: $MAX_PRODUCTS"
echo "Concurrent workers: $CONCURRENT_WORKERS"
echo "Output: Default (fm_data/json/fm_detail_timestamp.json)"
echo

# Run the crawler
echo "Starting crawler..."
uv run python crawler/crawl_fm_detailed.py \
  --input "$INPUT_FILE" \
  --concurrent "$CONCURRENT_WORKERS"

# Check exit status
if [ $? -ne 0 ]; then
    echo
    echo "Crawler failed with error code $?"
    exit $?
fi

echo
echo "Crawler completed successfully!"
echo "Check fm_data/json/ for output files"