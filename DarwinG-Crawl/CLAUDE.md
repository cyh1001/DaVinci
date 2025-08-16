# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DarwinG-Crawl is a web scraping project focused on crawling and extracting product data from the Forest Market website (forestmarket.net). The project uses multiple Python-based crawling approaches with different libraries and strategies.

## Architecture

The project is organized with crawler utilities in `src/crawler/` and uses a modular approach with different scripts for different crawling strategies:

### **URL Crawlers (Get Product URLs)**
- **crawl_fm_url.py**: Basic single-location URL crawler (legacy)
- **crawl_fm_url_enhanced.py**: Multi-location URL crawler with country selection

### **Detailed Data Crawlers (Extract Product Information)**
- **crawl_fm_detailed.py**: Comprehensive product data extraction with interactive elements
- **crawl_fm.py**: General product discovery and extraction (legacy)

### **Legacy Crawlers**
- **legacy/crawl.py**: Basic crawl4ai crawler for link discovery
- **legacy/crawl_manual_pause.py**: Playwright-based crawler with manual intervention

## Core Dependencies

The project relies on these main libraries:
- `crawl4ai` - Primary crawling framework with browser automation
- `playwright` - Alternative browser automation for manual intervention scenarios
- `asyncio` - Asynchronous programming for efficient crawling
- Standard libraries: `csv`, `json`, `re`, `urllib.parse`, `datetime`

## Project Setup with uv

This project uses `uv` for fast dependency management. Install dependencies:

```bash
# Install dependencies
uv sync

# Install with development dependencies
uv sync --extra dev

# Install browser for Playwright
uv run playwright install chromium
```

## Running Crawlers

### **Step 1: Get Product URLs (Multi-Location)**
```bash
# Get URLs for all countries → ../fm_data/fm_url_YYYYMMDD_HHMMSS.csv
uv run crawl-multi-url

# Get URLs for specific countries
uv run crawl-multi-url --locations "United States" Japan
uv run crawl-multi-url --locations en-US en-SG en-HK

# List available countries
uv run crawl-multi-url --list-locations

# Custom output location
uv run crawl-multi-url --output custom_urls.csv
```

### **Step 2: Extract Detailed Product Information**
```bash
# Extract details from CSV with URLs
uv run python crawler/crawl_fm_detailed.py --input fm_data/url/fm_url_20240129_143052.csv

# Extract from specific countries only
uv run python crawler/crawl_fm_detailed.py --input fm_data/url/fm_url_20240129_143052.csv --countries en-US en-SG

# Limit number of products
uv run python crawler/crawl_fm_detailed.py --input fm_data/url/fm_url_20240129_143052.csv --max-products 10

# Custom output filename
uv run python crawler/crawl_fm_detailed.py --input fm_data/url/fm_url_20240129_143052.csv --output detailed_products.json

# Extract single product URL (NEW)
uv run python crawler/crawl_fm_detailed.py --url "https://www.forestmarket.net/en-US/product/ABC123"
uv run python crawler/crawl_fm_detailed.py --url "https://www.forestmarket.net/product/XYZ789" --output single_product.json
```

### **Using convenience scripts:**
```bash
# URL crawlers
uv run crawl-url          # Basic URL crawler (legacy)
uv run crawl-multi-url    # Enhanced multi-location URL crawler

# Detailed data crawlers  
uv run crawl-detailed     # Detailed product extraction

# Legacy crawlers
uv run crawl-basic        # Basic crawl4ai crawler
uv run crawl-fm           # Forest Market comprehensive crawler
uv run crawl-manual       # Interactive crawler with manual intervention
```

## Crawler Strategies

### **1. Multi-Location URL Discovery** (`crawl_fm_url_enhanced.py`)
- Crawls 5 supported countries: United States, Singapore, Hong Kong, South Korea, Japan
- Automated "View More" button clicking to load all products 
- Outputs structured CSV with product IDs as rows and countries as columns
- Saves to `../fm_data/fm_url_{timestamp}.csv` by default

### **2. Interactive Detailed Extraction** (`crawl_fm_detailed.py`)
- Takes multi-location CSV as input
- Automatically clicks interactive elements: "Read More", "Product Condition", "Shipping & Return"
- Extracts comprehensive product data including size, color, payment methods
- Supports country-specific extraction from multi-location CSV
- Rate limiting and error handling for reliable extraction

### **3. Legacy Strategies**
- **Basic Link Discovery**: `legacy/crawl.py` - Simple URL extraction with "View More" automation
- **General Extraction**: `crawl_fm.py` - Combined URL discovery and product extraction
- **Manual Intervention**: `legacy/crawl_manual_pause.py` - Playwright-based with user interaction

## Data Output

### **URL Crawler Output** (`crawl_fm_url_enhanced.py`)
- **Main file**: `../fm_data/fm_url_YYYYMMDD_HHMMSS.csv` 
  - Product IDs as rows, countries as columns
  - Format: `product_id,en-US,en-SG,en-HK,en-KR,en-JP`
- **Failed locations**: `../fm_data/fm_url_YYYYMMDD_HHMMSS_failed_locations.csv`

### **Detailed Crawler Output** (`crawl_fm_detailed.py`)
- **Main file**: `forest_market_detailed_products.csv` (or custom name)
  - Comprehensive product data with 50+ fields
  - Size, color, payment methods, seller info, shipping details
- **Failed URLs**: `forest_market_detailed_products_failed_urls.csv`

### **Extracted Data Fields**
- **Basic**: Product name, description, price, images, brand, category
- **Variants**: Available sizes, colors, product conditions  
- **Commerce**: Payment methods, shipping info, return policy, availability
- **Seller**: Name, rating, location, profile links
- **Interactive**: Expanded descriptions, condition details, shipping terms

## Helper Tools

The project includes utility tools in the `helper/` directory for data processing and analysis:

### **JSON to Markdown Converter** (`helper/json_to_markdown.py`)
Converts JSON crawler output to readable markdown format with complete data preservation.

```bash
# Convert JSON to markdown with all data preserved
uv run python helper/json_to_markdown.py --input fm_data/json/fm_detail_20250730_170122.json

# Specify custom output file
uv run python helper/json_to_markdown.py --input fm_data/json/fm_detail_20250730_170122.json --output products.md

# Limit to first N products for testing
uv run python helper/json_to_markdown.py --input fm_data/json/fm_detail_20250730_170122.json --max-products 10

# Print to console instead of file
uv run python helper/json_to_markdown.py --input fm_data/json/fm_detail_20250730_170122.json --print
```

**Features:**
- **Complete Data Preservation**: No images or information lost during conversion
- **All Images Included**: Shows every image with both markdown display and raw URLs  
- **Rich Formatting**: Organized sections with proper markdown structure
- **Product Separators**: Each product separated by "---" for easy reading
- **Availability Matrix**: Visual indicators for country-specific availability
- **Comprehensive Coverage**: Automatically captures any additional data fields

### **URL Comparison Tool** (`helper/check_urls.py`)  
Compares URLs between CSV input and JSON output to verify completeness.

```bash
# Check if all CSV URLs are present in JSON output
uv run python helper/check_urls.py --input fm_data/json/fm_detail_20250730_170122.json

# Results show:
# - Total URLs in each file
# - Common URLs count  
# - Missing URLs (if any)
# - Extra URLs in JSON
```

**Use Cases:**
- Verify crawling completeness
- Identify failed/missing URLs
- Quality assurance for data extraction

## Key Configuration Patterns

### Browser Configuration
- Chromium browser with specific viewport (1920x1080)
- Custom user agents and headers for US locale
- Rate limiting (1-2 second delays) between requests
- Extended timeouts (300 seconds) for slow-loading pages

### Extraction Strategies
- JsonCssExtractionStrategy for structured data extraction
- Comprehensive CSS selectors covering multiple naming patterns
- Fallback HTML regex parsing when JSON extraction fails
- Data cleaning and validation before CSV export

## Target Website Specifics

The crawlers are specifically designed for forestmarket.net:

### **Supported Countries/Regions**
- **United States**: `en-US` (https://forestmarket.net/en-US)
- **Singapore**: `en-SG` (https://forestmarket.net/en-SG) 
- **Hong Kong**: `en-HK` (https://forestmarket.net/en-HK)
- **South Korea**: `en-KR` (https://forestmarket.net/en-KR)
- **Japan**: `en-JP` (https://forestmarket.net/en-JP)

### **URL Structure**
- Pattern: `/product/{product_id}` or `/{locale}/product/{product_id}`
- Product IDs are unique identifiers (e.g., `k5GQN8LRDaHj`, `jocY8fxxfRzl`)
- Same product may have different availability across regions

### **Technical Handling**
- Locale-specific cookies and headers for each region
- Rate limiting (2-5 second delays) between requests and locations
- Extended timeouts (60-300 seconds) for interactive elements
- Comprehensive error handling and retry logic