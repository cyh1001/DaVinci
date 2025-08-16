# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Forest Market MCP (Model Context Protocol) server that provides e-commerce product listing functionality. The server integrates draft management with product listing upload capabilities in a unified MCP server.

## Architecture

### Core Components

- **`integrated_mcp_server_structured_auto.py`** - Main production server with bulk processing, structured parameters, and Excel image extraction
- **`integrated_mcp_server.py`** - Basic MCP server with draft management and product listing tools  
- **`integrated_mcp_server_oauth.py`** - OAuth-enabled version of the main server
- **`integrated_mcp_server_remote_oauth.py`** - Remote OAuth implementation
- **`utils/models.py`** - Data models for ProductDraft, Variation, and ShippingPrice classes
- **`utils/storage.py`** - DraftStorage class for JSON file-based draft persistence
- **`utils/tools.py`** - Utility functions including Excel image extraction, data parsing, and validation
- **`utils/internal_tools.py`** - Internal API integration tools
- **`drafts.json`** - JSON storage file for product drafts

### Server Variants

The codebase includes multiple server implementations:
1. **Production server** (`integrated_mcp_server_structured_auto.py`) - **RECOMMENDED** - Full-featured server with:
   - Bulk CSV/Excel/JSON processing with embedded image extraction  
   - User confirmation requirements for live listing creation
   - Advanced data parsing with Python-style array/object handling
   - Structured parameters with comprehensive validation
   - Process-to-products direct upload functionality
2. **Basic server** (`integrated_mcp_server.py`) - Standard MCP server for simple use cases
3. **Structured server** (`integrated_mcp_server_structured.py`) - Enhanced server with structured parameters
4. **OAuth server** (`integrated_mcp_server_oauth.py`) - Includes OAuth authentication
5. **Remote OAuth server** (`integrated_mcp_server_remote_oauth.py`) - Remote OAuth implementation

### Data Flow

1. **Draft Management**: Create, read, update, delete product drafts stored in `drafts.json`
2. **Product Upload**: Convert drafts to actual product listings with image upload to S3
3. **Bulk Processing**: Process CSV/Excel/JSON files with multiple products automatically
4. **API Integration**: Communicates with Forest Market API for product creation

## Development Commands

### Running the Server

```bash
# Production server with full features (recommended)
uv run integrated_mcp_server_structured_auto.py mcp

# Basic server
uv run integrated_mcp_server.py mcp

# Using the startup script
./start_mcp.sh

# Using the Python runner
python run_mcp_server.py mcp
```

### Dependencies

Install dependencies using uv:
```bash
uv sync
```

Key dependencies include:
- `pandas>=1.5.0` - Data processing and CSV/Excel handling
- `openpyxl>=3.1.0` - Excel file processing with embedded image extraction
- `Pillow>=11.3.0` - Image processing for extracted Excel images
- `fastmcp>=2.0.0` - MCP server framework
- `openai>=1.0.0` - AI integration
- `requests>=2.25.0` - HTTP requests for file downloads

Or using pip:
```bash
pip install -r requirements.txt
```

### Environment Setup

The server requires environment variables loaded from `../.env`:
- OpenAI API configuration
- Forest Market API endpoints and authentication
- S3 upload configuration

## Key MCP Tools

### Draft Management Tools
- `create_draft` - Create new product drafts
- `get_draft` - Read existing drafts (replaces `read_draft`)
- `update_draft` - Update draft contents
- `delete_draft` - Remove drafts
- `list_drafts` - List all drafts with filtering options

### Product Upload Tools  
- `upload_listing` - Upload product with images to Forest Market API
- `draft_to_listing` - **REQUIRES USER CONFIRMATION** - Complete workflow to convert draft to live listing
- `process_to_products` - **REQUIRES USER CONFIRMATION** - Direct bulk upload from processed dataframe to live listings

### Bulk Processing Tools (Production Server)
- `check_file` - Download and analyze file structure, extract embedded Excel images, prepare for processing
- `execute_pandas_code` - Execute pandas transformations on loaded dataframes with safety checks
- `get_dataframe_status` - Check current dataframe status, column info, and upload readiness
- **Excel Image Extraction** - Automatically extracts embedded images from .xlsx files using `process_excel_with_images()`:
  - Detects floating images in Excel worksheets
  - Saves images to disk with proper file extensions (PNG, JPG, GIF, etc.)
  - Maps images to corresponding data rows
  - Adds `image_file_paths` column with local file paths

### Data Processing Features
- **Python-style Array Parsing** - Handles `"['item1', 'item2']"` format from CSV/Excel
- **Flexible Data Types** - Converts strings to proper types (arrays, objects, numbers)
- **Category Normalization** - Validates and normalizes product categories
- **Price Extraction** - Handles various price formats ($99.99, ¥100, etc.)
- **User Confirmation Protection** - Prevents accidental live listing creation without explicit approval

## Data Models

### ProductDraft
Contains all product information including title, description, price, category, variations, shipping options, and metadata.

### Variation
Represents product variations (e.g., size, color, switch types) with name and values.

### ShippingPrice
Defines shipping costs per country with currency support (defaults to USDT).

## Testing

Test files include:
- `ai_agent_mcp_test.py` - AI agent testing
- `test_authkit.py` - Authentication testing  
- `test_full_login_flow.py` - Full OAuth login flow testing

## Bulk Upload File Format

The production server supports CSV, Excel (.xlsx), and JSON file formats. **Excel files with embedded images are automatically processed to extract images.**

### Required Fields
- `title` - Product name/title
- `description` - Detailed product description  
- `price` - Product price (numeric, e.g., 99.99)
- `category` - Must be one of: DIGITAL_GOODS, DEPIN, ELECTRONICS, COLLECTIBLES, FASHION, CUSTOM, OTHER

### Optional Fields
- `condition` - NEW or USED (defaults to NEW)
- `quantity` - Stock quantity (defaults to 1)
- `contact_email` - Seller email (defaults to seller@example.com)
- `tags` - JSON array or comma-separated: `["gaming","wireless"]` or `"gaming,wireless"` 
- `specifications` - JSON object: `{"Brand":"Apple","Model":"iPhone"}`
- `payment_options` - JSON array: `["ETH_ETHEREUM","USDC_BASE"]`
- `image_file_paths` - JSON array of image URLs/paths (auto-populated from Excel images)
- `ship_from_country` - US, SG, HK, KR, or JP (defaults to US)
- `ship_to_countries` - JSON array: `["US","SG"]` (defaults to ["US"])
- `shipping_prices_data` - JSON array of shipping price objects
- `variations_data` - JSON array for product variations
- `discount_type` - PERCENTAGE or FIXED_AMOUNT
- `discount_value` - Discount amount (0.15 for 15% or 50.0 for $50)
- `currency_code` - Defaults to USDT

### Python-Style Array Support
The server handles Python-style arrays from CSV/Excel:
```csv
"['item1', 'item2', 'item3']"  # Single quotes - automatically converted
"[\"item1\", \"item2\"]"       # Double quotes - JSON format
"item1,item2,item3"           # Comma-separated - converted to array
```

### Excel Image Extraction
- **Embedded images are automatically extracted** from .xlsx files
- Images are saved to temporary directories with proper file extensions
- The `image_file_paths` column is automatically populated with local file paths
- Supports PNG, JPG, GIF, WebP, BMP, and other common formats

### Example CSV Row
```csv
title,description,price,category,condition,quantity,tags,specifications,image_file_paths
"Gaming Mouse","RGB gaming mouse with high DPI",89.99,ELECTRONICS,NEW,10,"['gaming','rgb']","{""DPI"":""16000""}","['/tmp/image1.png']"
```

## File Structure

- **`integrated_mcp_server_structured_auto.py`** - Main production server (recommended)
- **`utils/`** - Utility modules directory
  - `tools.py` - Data processing, Excel image extraction, validation functions
  - `models.py` - Data model definitions
  - `storage.py` - Draft persistence layer
  - `internal_tools.py` - API integration utilities
- **`temp_files/`** - Temporary file storage for processing
- **`debug_csv/`** - Debug output and processed dataframes
- **Configuration files**:
  - `pyproject.toml` and `uv.lock` - Dependency management
  - `requirements.txt` - Python dependencies
  - `drafts.json` - Draft storage (auto-created)
- **Environment**: Configuration loaded from `../.env`
- **Encoding**: UTF-8 for all files, supporting international characters

## Important Notes

### User Confirmation Requirements
Both `draft_to_listing` and `process_to_products` tools **require explicit user confirmation** before creating live listings. This prevents accidental publication and ensures users understand they're creating real marketplace listings.

### Excel Image Processing
The `process_excel_with_images()` function in `utils/tools.py` provides comprehensive Excel image extraction:
- Detects embedded/floating images in Excel worksheets
- Automatically maps images to data rows
- Handles multiple image formats with proper file extension detection
- Creates temporary file paths for uploaded images

### Data Type Conversion
The server includes robust data parsing to handle various input formats:
- Python-style arrays: `"['item1', 'item2']"` → `['item1', 'item2']`
- JSON objects: `"{\"key\": \"value\"}"` → `{"key": "value"}`
- Price normalization: `"$99.99"` → `99.99`
- Category validation with fallbacks to `"OTHER"`