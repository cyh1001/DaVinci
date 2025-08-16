@echo off
REM Windows batch file to run Forest Market detailed crawler
REM Edit the settings below directly in this file

echo Forest Market Detailed Crawler - Windows
echo ========================================

REM === EDIT THESE SETTINGS ===
set INPUT_FILE=fm_data\url\fm_url.csv
@REM set MAX_PRODUCTS=10
set CONCURRENT_WORKERS=3
REM === END SETTINGS ===

REM Check if input file exists
if not exist "%INPUT_FILE%" (
    echo Error: Input file "%INPUT_FILE%" not found
    pause
    exit /b 1
)

echo Input file: %INPUT_FILE%
@REM echo Max products: %MAX_PRODUCTS%
echo Concurrent workers: %CONCURRENT_WORKERS%
echo Output: Default (fm_data/json/fm_detail_timestamp.json)
echo.

REM Run the crawler
echo Starting crawler...
uv run python crawler/crawl_fm_detailed.py --input "%INPUT_FILE%" --concurrent %CONCURRENT_WORKERS%

if %ERRORLEVEL% neq 0 (
    echo.
    echo Crawler failed with error code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Crawler completed successfully!
echo Check fm_data/json/ for output files
pause