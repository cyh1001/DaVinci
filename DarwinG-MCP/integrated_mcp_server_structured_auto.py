#!/usr/bin/env python3
"""
Integrated MCP Server for Forest Market Draft Management and Product Listing Upload (OAuth Version)

This MCP server combines two previously separate tools:
1. Draft management tools (create, read, update, delete drafts)
2. Product listing upload tool (upload images and create listings)

This provides a complete workflow in a single MCP server with OAuth authentication.

OAUTH CONFIGURATION (WorkOS AuthKit):
This version uses OAuth authentication with WorkOS AuthKit. Configure the following environment variables:

Required Environment Variables:
- AUTHKIT_DOMAIN: Your AuthKit domain (default: https://auth-forestmarket.authkit.app)
- BASE_URL: Your server's base URL (default: http://localhost:8000)

Setup Steps:
1. Create a WorkOS account and AuthKit instance
2. Enable Dynamic Client Registration in WorkOS Dashboard
3. Set AUTHKIT_DOMAIN to your AuthKit domain URL
4. Set BASE_URL to where this server will run

CLIENT USAGE:
To use this server, clients need to:
1. Obtain a JWT token from your AuthKit domain
2. Include the token in requests as a Bearer token: Authorization: Bearer <token>
3. Ensure the token is valid and not expired

DEMO CONFIGURATION:
The default configuration uses a demo AuthKit domain.
For production use, replace with your own WorkOS AuthKit instance.

FALLBACK:
If OAuth configuration fails, the server will run without authentication for development.
"""

import os
import sys
import json
import requests
import pandas as pd
import openpyxl
import tempfile
import shutil
import traceback
from typing import List, Dict, Optional, Annotated, Literal, Any
from fastmcp import FastMCP
from pydantic import Field
from dotenv import load_dotenv

# Coinbase CDP SDK imports
try:
    import cdp
    from cdp import CdpClient
    from cdp.evm_token_balances import ListEvmTokenBalancesNetwork
    CDP_AVAILABLE = True
except ImportError:
    print("Warning: Coinbase CDP SDK not installed. Install with: pip install cdp-sdk", file=sys.stderr)
    CDP_AVAILABLE = False

# Load environment variables
load_dotenv("../.env")

from utils.custom_data_structure import *

# Import models and storage

from utils.models import ProductDraft
from utils.storage import DraftStorage
from utils.tools import download_image_from_url, extract_price, is_url, is_user_confirmed, get_presigned_url, normalize_category, parse_array_field, parse_object_field, upload_file_to_s3, DifyParamParser, process_excel_with_images, validate_product_row

from utils.internal_tools import create_product_listing_internal

# Initialize storage
storage = DraftStorage()

# Configure Coinbase CDP
cdp_client = None
if CDP_AVAILABLE:
    try:
        # Try to configure CDP from environment variables
        api_key_name = os.getenv("CDP_API_KEY_NAME")
        api_key_private_key = os.getenv("CDP_API_KEY_PRIVATE_KEY")
        
        if api_key_name and api_key_private_key:
            cdp_client = CdpClient(api_key_name=api_key_name, private_key=api_key_private_key)
            print("✅ Coinbase CDP configured successfully", file=sys.stderr)
        else:
            print("⚠️ CDP API keys not found in environment variables", file=sys.stderr)
            print("   Set CDP_API_KEY_NAME and CDP_API_KEY_PRIVATE_KEY to enable CDP features", file=sys.stderr)
    except Exception as e:
        print(f"❌ Failed to configure CDP: {e}", file=sys.stderr)

# OAuth-based authentication using WorkOS AuthKit
from fastmcp.server.auth.providers.workos import AuthKitProvider

# AuthKit configuration
authkit_domain = os.getenv("AUTHKIT_DOMAIN", "https://valuable-dawn-13-staging.authkit.app/")
base_url = os.getenv("BASE_URL", "https://darwing-mcp.onrender.com")

# Create AuthKit provider
auth_provider = AuthKitProvider(
    authkit_domain=authkit_domain,
    base_url=base_url
)

import sys
print(f"OAuth authentication configured with AuthKit domain: {authkit_domain}", file=sys.stderr)
print(f"Base URL: {base_url}", file=sys.stderr)
print("To use this server, obtain a JWT token from the AuthKit domain and include it as a Bearer token", file=sys.stderr)

# Initialize the integrated MCP server with AuthKit authentication
mcp = FastMCP("Forest Market MCP Server", auth=auth_provider)

# Register all draft management tools
@mcp.tool(
    name="create_draft",
    description="Create a Forest Market product draft with structured parameters"
)
def create_draft(
    user_id: Annotated[str, Field(description="User identifier for draft ownership. Use provided user ID or 'ai_agent' if generating automatically.")],
    title: Annotated[str, Field(description="Product name extracted from user input. Examples: 'wireless gaming mouse', 'vintage leather jacket', 'Python programming course'")] = "",
    description: Annotated[str, Field(description="Detailed product description extracted from user input. Include features, benefits, use cases, and selling points mentioned by user.")] = "",
    price: Annotated[str, Field(description="Product price in USDT. Extract numerical value from user input (e.g., '$99.99' becomes 99.99, '50 dollars' becomes 50.0). Must be >= 0.")] = "0.0",
    category: Annotated[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"], Field(description="Product category classification. Map user input to exact values: software/courses/digital content = DIGITAL_GOODS, phones/computers/gadgets = ELECTRONICS, clothing/accessories = FASHION, rare items/collectibles = COLLECTIBLES, blockchain hardware = DEPIN, personalized items = CUSTOM, everything else = OTHER")] = "OTHER",
    condition: Annotated[Literal["NEW", "USED"], Field(description="Product condition. Extract from user input: new/unused/fresh/mint = NEW, used/pre-owned/second-hand/refurbished = USED")] = "NEW",
    variations_data: Annotated[Optional[str], Field(description='''Product variations extracted from user input. EXACT FORMAT REQUIRED: null OR array matching VariationData class:
        class VariationData(BaseModel):
            name: str  # Required string field
            values: List[str]  # Required list of strings, must have at least 1 item
        
        MUST BE EXACTLY LIKE: [
          {"name": "Size", "values": ["S", "M", "L", "XL"]},
          {"name": "Color", "values": ["Black", "White", "Red"]},
          {"name": "Style", "values": ["Standard", "Premium"]}
        ]
     Only include variations explicitly mentioned by user. You must provide an array or null, not a stringified json.''')] = None,
    image_file_paths: Annotated[Optional[str], Field(description="An Array of Image file paths provided by user or system. Accept absolute file paths like '/path/to/image.jpg'. Leave empty if no images specified.")] = None,
    contact_email: Annotated[str, Field(description="Seller contact email extracted from user input or use default like 'seller@example.com' if generating automatically")] = "",
    ship_from_country: Annotated[Optional[Literal["US", "SG", "HK", "KR", "JP"]], Field(description="Shipping origin country. Extract from user input: United States/America/USA = US, Singapore = SG, Hong Kong = HK, South Korea/Korea = KR, Japan = JP. Automatically set to null for DIGITAL_GOODS category.")] = None,
    ship_to_countries: Annotated[Optional[str], Field(description="A list of Countries where product can be shipped. Extract from user input and map to valid codes: US, SG, HK, KR, JP. Example: 'ships to US and Singapore' becomes ['US','SG']. Automatically cleared for DIGITAL_GOODS.")] = None,
    shipping_prices_data: Annotated[Optional[str], Field(description='''Shipping costs per country.  
    must be null OR array matching ShippingPriceData class:
        class ShippingPriceData(BaseModel):
            country_code: str  # Required, must be one of ["US", "SG", "HK", "KR", "JP"]
            price: float  # Required, must be >= 0.0
            currency_code: str = "USDT"  # Optional, defaults to "USDT"
        
        MUST BE EXACTLY LIKE: [
          {"country_code": "US", "price": 0.0, "currency_code": "USDT"},
          {"country_code": "SG", "price": 25.0, "currency_code": "USDT"},
        ]
    Extract from user input like 'free shipping to US, $25 to Singapore' becomes [{'country_code': 'US', 'price': 0.0, 'currency_code': 'USDT'}, {'country_code': 'SG', 'price': 25.0, 'currency_code': 'USDT'}].
    Automatically cleared for DIGITAL_GOODS.''')] = None,
    quantity: Annotated[str, Field(description="Stock quantity extracted from user input. Examples: '10 available' = 10, '5 in stock' = 5, 'limited quantity' = 1-5, 'plenty available' = 20-50. Minimum value is 1.")] = "1",
    discount_type: Annotated[Optional[Literal["", "FIXED_AMOUNT", "PERCENTAGE"]], Field(description="Discount type extracted from user input. Map: 'X% off' or 'X percent discount' = PERCENTAGE, '$X off' or 'X dollars off' = FIXED_AMOUNT, no discount mentioned = empty string or None")] = None,
    discount_value: Annotated[str, Field(description="Discount amount extracted from user input. For PERCENTAGE: convert percentage to decimal (15% = 0.15, must be 0.1-0.5). For FIXED_AMOUNT: dollar amount (5.0-50.0). No discount = 0.0.")] = "0.0",
    payment_options: Annotated[Optional[str], Field(description="An Array of Cryptocurrency payment methods. Map user input: 'ETH' or 'Ethereum' = ETH_ETHEREUM, 'ETH Base' = ETH_BASE, 'SOL' or 'Solana' = SOL_SOLANA, 'USDC' = USDC_ETHEREUM, 'USDC Base' = USDC_BASE, 'USDC Solana' = USDC_SOLANA, 'USDT' = USDT_ETHEREUM. Forexample: ['ETH_ETHEREUM', 'SOL_SOLANA']. Default to common options if not specified: ['ETH_ETHEREUM', 'USDC_BASE']")] = None,
    tags: Annotated[Optional[str], Field(description="An array of Search tags extracted from user input. Include product features, keywords, and relevant terms mentioned. Examples: gaming mouse -> ['gaming', 'wireless', 'rgb'], vintage jacket -> ['vintage', 'leather', 'fashion'], course -> ['programming', 'education', 'beginner']")] = None,
    specifications: Annotated[Optional[str], Field(description="Technical specifications extracted from user input. Format as key-value pairs dictionary: {'Brand': 'Apple', 'Model': 'iPhone 15', 'Storage': '128GB', 'Color': 'Blue'}. Extract any technical details, dimensions, materials, features mentioned by user.")] = None
) -> Dict[str, Any]:
    """Create a draft using structured parameters"""
    variations_data = DifyParamParser.parse_variation_data(variations_data)
    shipping_prices_data = DifyParamParser.parse_shipping_price_data(shipping_prices_data)
    tags = DifyParamParser.parse_tags(tags)
    specifications = DifyParamParser.parse_specifications(specifications)
    ship_to_countries = DifyParamParser.parse_ship_to_countries(ship_to_countries)
    payment_options = DifyParamParser.parse_payment_options(payment_options)
    discount_value = float(discount_value)
    quantity = int(quantity)
    price = float(price)
    category = category.upper()
    condition = condition.upper()
    ship_from_country = ship_from_country.upper()
    image_file_paths = DifyParamParser.parse_image_file_paths(image_file_paths)
    return _create_draft_internal(
        user_id=user_id,
        title=title,
        description=description,
        price=price,
        category=category,
        condition=condition,
        variations_data=variations_data,
        image_file_paths=image_file_paths,
        contact_email=contact_email,
        ship_from_country=ship_from_country,
        ship_to_countries=ship_to_countries,
        shipping_prices_data=shipping_prices_data,
        quantity=quantity,
        discount_type=discount_type,
        discount_value=discount_value,
        payment_options=payment_options,
        tags=tags,
        specifications=specifications
    )

@mcp.tool(
    name="get_draft",
    description="Retrieve draft information with flexible output modes: full details, summary, or batch processing"
)
def get_draft(
    draft_id: Annotated[Optional[str], Field(description="Draft ID to retrieve (required unless using batch_ids)")] = None,
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification and access control")] = None,
    summary_only: Annotated[str, Field(description="Return summary instead of full draft details")] = "false",
    batch_ids: Annotated[Optional[str], Field(description="Multiple draft IDs for batch retrieval (overrides draft_id)")] = None
) -> Dict[str, Any]:
    """Unified draft retrieval tool with multiple modes"""
    
    # Parse string parameters
    summary_only = summary_only.lower() in ['true', '1', 'yes'] if isinstance(summary_only, str) else bool(summary_only)
    batch_ids = json.loads(batch_ids) if batch_ids else None
    
    # Batch processing mode
    if batch_ids:
        results = []
        for bid in batch_ids:
            draft = storage.get_draft(bid)
            if not draft:
                results.append({"draft_id": bid, "error": "Not found"})
                continue
            
            # User permission check
            if user_id and draft.user_id and draft.user_id != user_id:
                results.append({"draft_id": bid, "error": "Access denied"})
                continue
            
            if summary_only:
                results.append({
                    "draft_id": draft.draft_id,
                    "user_id": draft.user_id,
                    "title": draft.title,
                    "price": draft.price,
                    "category": draft.category,
                    "condition": draft.condition,
                    "quantity": draft.quantity,
                    "ship_from_country": draft.ship_from_country,
                    "last_updated": draft.updated_at,
                    "version": draft.version
                })
            else:
                results.append(draft.to_dict())
        
        return {
            "total_processed": len(batch_ids),
            "successful": len([r for r in results if "error" not in r]),
            "results": results
        }
    
    # Single draft mode
    if not draft_id:
        return {"error": "draft_id is required when not using batch_ids"}
    
    draft = storage.get_draft(draft_id)
    if not draft:
        return {"error": f"Product draft {draft_id} not found"}
    
    # User permission check
    if user_id and draft.user_id and draft.user_id != user_id:
        return {"error": "Access denied: Draft belongs to different user"}
    
    # Return summary or full details
    if summary_only:
        return {
            "draft_id": draft.draft_id,
            "user_id": draft.user_id,
            "title": draft.title,
            "price": draft.price,
            "category": draft.category,
            "condition": draft.condition,
            "quantity": draft.quantity,
            "ship_from_country": draft.ship_from_country,
            "ship_to_count": len(draft.ship_to_countries),
            "has_shipping_fees": bool(draft.shipping_prices_data),
            "variations_count": len(draft.variations_data),
            "tags_count": len(draft.tags),
            "images_count": len(draft.image_file_paths),
            "payment_options_count": len(draft.payment_options),
            "has_description": bool(draft.description),
            "has_contact_email": bool(draft.contact_email),
            "has_discount": bool(draft.discount_type),
            "has_specifications": bool(draft.specifications),
            "last_updated": draft.updated_at,
            "version": draft.version
        }
    else:
        return draft.to_dict()

@mcp.tool(
    name="update_draft",
    description="Update Forest Market draft with structured parameters"
)
def update_draft(
    draft_id: Annotated[str, Field(description="Draft ID to update (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    title: Annotated[Optional[str], Field(description="Updated product title/name")] = None,
    description: Annotated[Optional[str], Field(description="Updated product description")] = None,
    price: Annotated[Optional[str], Field(description="Updated price in USDT (>= 0)")] = None,
    category: Annotated[Optional[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]], Field(description="Updated Forest Market category")] = None,
    condition: Annotated[Optional[Literal["NEW", "USED"]], Field(description="Updated product condition")] = None,
    variations_data: Annotated[Optional[str], Field(description="Updated variations (replaces existing): [{'name': 'Size', 'values': ['S','M','L']}]")] = None,
    image_file_paths: Annotated[Optional[str], Field(description="Updated image file paths (replaces existing list)")] = None,
    contact_email: Annotated[Optional[str], Field(description="Updated seller contact email")] = None,
    ship_from_country: Annotated[Optional[Literal["US", "SG", "HK", "KR", "JP"]], Field(description="Updated shipping origin (auto-cleared for DIGITAL_GOODS)")] = None,
    ship_to_countries: Annotated[Optional[str], Field(description="Updated shipping destinations (auto-cleared for DIGITAL_GOODS)")] = None,
    shipping_prices_data: Annotated[Optional[str], Field(description="Updated shipping fees (auto-cleared for DIGITAL_GOODS): [{'country_code': 'US', 'price': 15.0, 'currency_code': 'USDT'}]")] = None,
    quantity: Annotated[Optional[str], Field(description="Updated stock quantity (>= 1)")] = None,
    discount_type: Annotated[Optional[Literal["", "FIXED_AMOUNT", "PERCENTAGE"]], Field(description="Updated discount type (empty string removes discount)")] = None,
    discount_value: Annotated[Optional[str], Field(description="Updated discount value (USDT for FIXED_AMOUNT, 0.1-0.5 for PERCENTAGE)")] = None,
    payment_options: Annotated[Optional[str], Field(description="Updated crypto payment methods (replaces existing)")] = None,
    tags: Annotated[Optional[str], Field(description="Updated search tags (replaces existing list)")] = None,
    specifications: Annotated[Optional[str], Field(description="Updated technical specs (replaces existing dict)")] = None
) -> Dict[str, Any]:
    """Update a Forest Market product draft with structured parameters"""
    variations_data = DifyParamParser.parse_variation_data(variations_data) if variations_data else None
    shipping_prices_data = DifyParamParser.parse_shipping_price_data(shipping_prices_data) if shipping_prices_data else None
    tags = DifyParamParser.parse_tags(tags) if tags else None
    specifications = DifyParamParser.parse_specifications(specifications) if specifications else None
    ship_to_countries = DifyParamParser.parse_ship_to_countries(ship_to_countries) if ship_to_countries else None
    payment_options = DifyParamParser.parse_payment_options(payment_options) if payment_options else None
    image_file_paths = DifyParamParser.parse_image_file_paths(image_file_paths) if image_file_paths else None
    discount_value = float(discount_value) if discount_value else None
    quantity = int(quantity) if quantity else None
    price = float(price) if price else None
    return _update_draft_internal(
        draft_id=draft_id,
        user_id=user_id,
        title=title,
        description=description,
        price=price,
        category=category,
        condition=condition,
        variations_data=variations_data,
        image_file_paths=image_file_paths,
        contact_email=contact_email,
        ship_from_country=ship_from_country,
        ship_to_countries=ship_to_countries,
        shipping_prices_data=shipping_prices_data,
        quantity=quantity,
        discount_type=discount_type,
        discount_value=discount_value,
        payment_options=payment_options,
        tags=tags,
        specifications=specifications
    )

@mcp.tool(
    name="list_drafts",
    description="Search and filter Forest Market drafts with advanced querying capabilities"
)
def list_drafts(
    user_id: Annotated[Optional[str], Field(description="Filter by user ID (leave empty for all users)")] = None,
    query: Annotated[Optional[str], Field(description="Search term for title, description, tags, and specifications")] = None,
    category: Annotated[Optional[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]], Field(description="Filter by Forest Market category")] = None,
    condition: Annotated[Optional[Literal["NEW", "USED"]], Field(description="Filter by product condition")] = None,
    min_price: Annotated[Optional[str], Field(description="Minimum price filter (>= 0)")] = None,
    max_price: Annotated[Optional[str], Field(description="Maximum price filter (>= 0)")] = None,
    limit: Annotated[Optional[str], Field(description="Max results to return (1-100)")] = None,
    offset: Annotated[Optional[str], Field(description="Results to skip for pagination (>= 0)")] = None,
    with_stats: Annotated[str, Field(description="Include user statistics (requires user_id)")] = "false"
) -> Dict[str, Any]:
    """Search and filter drafts with comprehensive query capabilities"""
    
    # Parse string parameters
    min_price = float(min_price) if min_price else None
    max_price = float(max_price) if max_price else None
    limit = int(limit) if limit else None
    offset = int(offset) if offset else None
    with_stats = with_stats.lower() in ['true', '1', 'yes'] if isinstance(with_stats, str) else bool(with_stats)
    
    drafts = storage.list_drafts()
    
    # Filter by user ID if provided
    if user_id:
        drafts = [draft for draft in drafts if draft.user_id == user_id]
    
    # Filter by category
    if category:
        drafts = [draft for draft in drafts if draft.category == category]
    
    # Filter by condition
    if condition:
        drafts = [draft for draft in drafts if draft.condition == condition]
    
    # Filter by price range
    if min_price is not None:
        drafts = [draft for draft in drafts if draft.price >= min_price]
    if max_price is not None:
        drafts = [draft for draft in drafts if draft.price <= max_price]
    
    # Text search across multiple fields
    if query:
        search_results = []
        query_lower = query.lower()
        
        for draft in drafts:
            matches = []
            score = 0
            
            # Search title (highest weight)
            if query_lower in draft.title.lower():
                matches.append("title")
                score += 3
            
            # Search description
            if query_lower in draft.description.lower():
                matches.append("description")
                score += 2
            
            # Search tags
            for tag in draft.tags:
                if query_lower in tag.lower():
                    matches.append("tags")
                    score += 2
                    break
            
            # Search specifications
            for spec_key, spec_value in draft.specifications.items():
                if query_lower in spec_key.lower() or query_lower in str(spec_value).lower():
                    matches.append("specifications")
                    score += 1
                    break
            
            # Add to results if matches found
            if matches:
                search_results.append((draft, score, matches))
        
        # Sort by relevance score
        search_results.sort(key=lambda x: x[1], reverse=True)
        drafts = [result[0] for result in search_results]
    
    # Apply pagination
    total_count = len(drafts)
    if offset:
        drafts = drafts[offset:]
    if limit:
        drafts = drafts[:limit]
    
    # Build response data
    draft_list = []
    for draft in drafts:
        draft_info = {
            "draft_id": draft.draft_id,
            "user_id": draft.user_id,
            "title": draft.title,
            "category": draft.category,
            "condition": draft.condition,
            "price": draft.price,
            "quantity": draft.quantity,
            "ship_from_country": draft.ship_from_country,
            "has_variations": len(draft.variations_data) > 0,
            "has_discount": bool(draft.discount_type),
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "version": draft.version
        }
        
        # Add search match info if applicable
        if query:
            for result in search_results:
                if result[0].draft_id == draft.draft_id:
                    draft_info["search_score"] = result[1]
                    draft_info["search_matches"] = result[2]
                    break
        
        draft_list.append(draft_info)
    
    result = {
        "total_count": total_count,
        "returned_count": len(draft_list),
        "drafts": draft_list
    }
    
    # Add user statistics if requested
    if with_stats and user_id:
        user_drafts = [draft for draft in storage.list_drafts() if draft.user_id == user_id]
        if user_drafts:
            categories = {}
            total_value = 0
            conditions = {}
            
            for draft in user_drafts:
                categories[draft.category] = categories.get(draft.category, 0) + 1
                total_value += draft.price * draft.quantity
                conditions[draft.condition] = conditions.get(draft.condition, 0) + 1
            
            result["statistics"] = {
                "total_inventory_value": total_value,
                "categories": categories,
                "conditions": conditions,
                "avg_price": total_value / sum(draft.quantity for draft in user_drafts) if user_drafts else 0
            }
    
    return result

@mcp.tool(
    name="delete_draft", 
    description="Permanently delete a Forest Market draft with ownership verification"
)
def delete_draft(
    draft_id: Annotated[str, Field(description="Draft ID to delete permanently (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification (recommended)")] = None
) -> Dict[str, Any]:
    """Delete a specific product draft permanently"""
    
    # User permission check if provided
    if user_id:
        draft = storage.get_draft(draft_id)
        if not draft:
            return {"error": f"Product draft {draft_id} not found"}
        if draft.user_id and draft.user_id != user_id:
            return {"error": "Access denied: Draft belongs to different user"}
    
    success = storage.delete_draft(draft_id)
    
    if success:
        return {
            "status": "deleted",
            "draft_id": draft_id
        }
    else:
        return {
            "error": f"Product draft {draft_id} not found or deletion failed"
        }

@mcp.tool(
    name="remove_from_draft",
    description="Remove specific options from draft with structured parameters"
)
def remove_from_draft(
    draft_id: Annotated[str, Field(description="Draft ID to update selectively (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    variation_options: Annotated[Optional[str], Field(description="Remove specific variation options: [{'name': 'Size', 'values': ['S','M']}] (keeps other sizes)")] = None,
    variation_types: Annotated[Optional[str], Field(description="Remove entire variation categories: ['Color'] (removes all colors)")] = None,
    image_file_paths: Annotated[Optional[str], Field(description="Remove specific image file paths from existing list")] = None,
    tags: Annotated[Optional[str], Field(description="Remove specific tags from existing list")] = None,
    specifications: Annotated[Optional[str], Field(description="Remove spec keys: ['Weight'] (removes key-value pairs)")] = None,
    ship_to_countries: Annotated[Optional[str], Field(description="Remove shipping destinations from existing list")] = None,
    shipping_prices_data: Annotated[Optional[str], Field(description="Remove shipping fees for countries: ['Canada'] (removes fee entries)")] = None,
    payment_options: Annotated[Optional[str], Field(description="Remove payment methods from existing list")] = None
) -> Dict[str, Any]:
    """Remove specific options from a Forest Market product draft using structured parameters"""
    # Parse string parameters for remove_from_draft
    variation_options = json.loads(variation_options) if variation_options else None
    variation_types = json.loads(variation_types) if variation_types else None
    image_file_paths = json.loads(image_file_paths) if image_file_paths else None
    tags = json.loads(tags) if tags else None
    specifications = json.loads(specifications) if specifications else None
    ship_to_countries = json.loads(ship_to_countries) if ship_to_countries else None
    shipping_prices_data = json.loads(shipping_prices_data) if shipping_prices_data else None
    payment_options = json.loads(payment_options) if payment_options else None
    return _remove_from_draft_internal(
        draft_id=draft_id,
        user_id=user_id,
        variation_options=variation_options,
        variation_types=variation_types,
        image_file_paths=image_file_paths,
        tags=tags,
        specifications=specifications,
        ship_to_countries=ship_to_countries,
        shipping_prices_data=shipping_prices_data,
        payment_options=payment_options
    )

@mcp.tool(
    name="export_draft",
    description="Export draft in Forest Market format for listing integration and final review"
)
def export_draft(
    draft_id: Annotated[str, Field(description="Draft ID to export for listing (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    export_format: Annotated[Literal["forest_market", "json"], Field(description="Export format: forest_market (optimized) or json (raw)")] = "forest_market",
    include_mapping_info: Annotated[str, Field(description="Include field mapping information for upload tool compatibility")] = "false"
) -> Dict[str, Any]:
    """Export draft data for integration with listing MCP services"""
    include_mapping_info = include_mapping_info.lower() in ['true', '1', 'yes'] if isinstance(include_mapping_info, str) else bool(include_mapping_info)
    return _export_draft_internal(draft_id, user_id, export_format, include_mapping_info)

def _add_to_draft_internal(
    draft_id: Annotated[str, Field(description="Draft ID to update incrementally (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    variations_data: Annotated[Optional[List[VariationData]], Field(description="Add variation options: [{'name': 'Size', 'values': ['XXL']}] (merges with existing)")] = None,
    image_file_paths: Annotated[Optional[List[str]], Field(description="Add image file paths to existing list (no duplicates)")] = None,
    tags: Annotated[Optional[List[str]], Field(description="Add search tags to existing list (no duplicates)")] = None,
    specifications: Annotated[Optional[Dict[str, str]], Field(description="Add specs to existing dict: {'RAM': '32GB'} (merges keys)")] = None,
    ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Add shipping destinations to existing list")] = None,
    shipping_prices_data: Annotated[Optional[List[ShippingPriceData]], Field(description="Add/update shipping fees: [{'country_code': 'Canada', 'price': 20.0, 'currency_code': 'USDT'}] (merges with existing)")] = None,
    payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Add payment methods to existing list (no duplicates)")] = None
) -> Dict[str, Any]:
    """Internal function to add new options/items to existing draft fields"""
    
    draft = storage.get_draft(draft_id)
    if not draft:
        return {"error": f"Product draft {draft_id} not found"}
    
    # User permission check
    if user_id and draft.user_id and draft.user_id != user_id:
        return {"error": "Access denied: Draft belongs to different user"}
    
    updates = {}
    
    # Handle variations_data - add new options to existing variation types
    if variations_data:
        current_variations = [vars(v) for v in draft.variations_data]  # Convert to dict format
        for new_var in variations_data:
            var_name = new_var.name
            new_values = new_var.values
            
            # Find existing variation type
            existing_var = next((v for v in current_variations if v["name"] == var_name), None)
            if existing_var:
                # Merge options, remove duplicates
                combined_values = list(set(existing_var["values"] + new_values))
                existing_var["values"] = combined_values
            else:
                # New variation type
                current_variations.append({"name": var_name, "values": new_values})
        # Convert back to Variation objects
        variations_objects = [Variation(name=v['name'], values=v['values']) for v in current_variations]
        updates["variations_data"] = variations_objects
    
    # Handle image_file_paths - add to existing list
    if image_file_paths:
        current_images = draft.image_file_paths.copy()
        for img in image_file_paths:
            if img not in current_images:
                current_images.append(img)
        updates["image_file_paths"] = current_images
    
    # Handle tags - add to existing list, remove duplicates
    if tags:
        current_tags = draft.tags.copy()
        for tag in tags:
            if tag not in current_tags:
                current_tags.append(tag)
        updates["tags"] = current_tags
    
    # Handle specifications - add/update specs
    if specifications:
        current_specs = draft.specifications.copy()
        current_specs.update(specifications)
        updates["specifications"] = current_specs
    
    # Handle ship_to_countries - add new destinations
    if ship_to_countries:
        current_ship_to = draft.ship_to_countries.copy()
        for destination in ship_to_countries:
            if destination not in current_ship_to:
                current_ship_to.append(destination)
        updates["ship_to_countries"] = current_ship_to
    
    # Handle shipping_prices_data - add new fees
    if shipping_prices_data:
        current_fees = [vars(f) for f in draft.shipping_prices_data]  # Convert to dict format
        for new_fee in shipping_prices_data:
            country_code = new_fee.country_code
            # Find existing fee entry
            existing_fee = next((f for f in current_fees if f["country_code"] == country_code), None)
            if existing_fee:
                # Update existing fee
                existing_fee.update(vars(new_fee))
            else:
                # Add new fee
                current_fees.append(vars(new_fee))
        # Convert back to ShippingPrice objects
        shipping_objects = [
            ShippingPrice(
                country_code=f['country_code'],
                price=f['price'],
                currency_code=f.get('currency_code', 'USDT')
            )
            for f in current_fees
        ]
        updates["shipping_prices_data"] = shipping_objects
    
    # Handle payment_options - add new payment methods
    if payment_options:
        current_methods = draft.payment_options.copy()
        for method in payment_options:
            if method not in current_methods:
                current_methods.append(method)
        updates["payment_options"] = current_methods
    
    if not updates:
        return {"error": "No valid fields provided to add"}
    
    success = storage.update_draft(draft_id, **updates)
    
    if success:
        updated_draft = storage.get_draft(draft_id)
        return {
            "status": "added",
            "draft_id": draft_id,
            "version": updated_draft.version,
            "updated_at": updated_draft.updated_at,
            "added_fields": list(updates.keys())
        }
    else:
        return {"error": "Add operation failed"}

@mcp.tool(
    name="add_to_draft",
    description="Add new options to draft with structured parameters"
)
def add_to_draft(
    draft_id: Annotated[str, Field(description="Draft ID to update incrementally (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    variations_data: Annotated[Optional[str], Field(description="Add variation options: [{'name': 'Size', 'values': ['XXL']}] (merges with existing)")] = None,
    image_file_paths: Annotated[Optional[str], Field(description="Add image file paths to existing list (no duplicates)")] = None,
    tags: Annotated[Optional[str], Field(description="Add search tags to existing list (no duplicates)")] = None,
    specifications: Annotated[Optional[str], Field(description="Add specs to existing dict: {'RAM': '32GB'} (merges keys)")] = None,
    ship_to_countries: Annotated[Optional[str], Field(description="Add shipping destinations to existing list")] = None,
    shipping_prices_data: Annotated[Optional[str], Field(description="Add/update shipping fees: [{'country_code': 'Canada', 'price': 20.0, 'currency_code': 'USDT'}] (merges with existing)")] = None,
    payment_options: Annotated[Optional[str], Field(description="Add payment methods to existing list (no duplicates)")] = None
) -> Dict[str, Any]:
    """Add new options to a Forest Market product draft using structured parameters"""
    variations_data = DifyParamParser.parse_variation_data(variations_data) if variations_data else None
    shipping_prices_data = DifyParamParser.parse_shipping_price_data(shipping_prices_data) if shipping_prices_data else None
    tags = DifyParamParser.parse_tags(tags) if tags else None
    specifications = DifyParamParser.parse_specifications(specifications) if specifications else None
    ship_to_countries = DifyParamParser.parse_ship_to_countries(ship_to_countries) if ship_to_countries else None
    payment_options = DifyParamParser.parse_payment_options(payment_options) if payment_options else None
    image_file_paths = DifyParamParser.parse_image_file_paths(image_file_paths) if image_file_paths else None
    return _add_to_draft_internal(
        draft_id=draft_id,
        user_id=user_id,
        variations_data=variations_data,
        image_file_paths=image_file_paths,
        tags=tags,
        specifications=specifications,
        ship_to_countries=ship_to_countries,
        shipping_prices_data=shipping_prices_data,
        payment_options=payment_options
    )

@mcp.tool(
    name="draft_to_listing",
    description="CONFIRMATION REQUIRED: Complete workflow to export draft and create live listing. This will upload images and create a REAL listing on Forest Market. ALWAYS ask user for explicit confirmation before calling this tool. Never call this automatically after create_draft."
)
def draft_to_listing(
    draft_id: Annotated[str, Field(description="Draft ID to convert to live listing")],
    user_confirmed: Annotated[str, Field(description="User explicit confirmation to proceed with live listing creation. Can be boolean True or string 'true'/'yes'. AI should ask user: 'Do you want to create a live listing on Forest Market?' and get explicit yes/no confirmation.")] = "false",
    session_token: Annotated[str, Field(description="Authentication session token for Forest Market, if not provided, use default")] = os.getenv('FM_SESSION_TOKEN'),
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    trpc_endpoint: str = "https://forestmarket.net/api/trpc/product.uploadListing?batch=1"
) -> str:
    """
    Complete workflow: Export a draft and create a live listing in one step.
    
    This tool combines export_draft and upload_listing for seamless draft-to-listing conversion.
    """
    
    # Check for user confirmation (flexible checking for various input types)
    if not is_user_confirmed(user_confirmed):
        return json.dumps({
            "success": False,
            "error": "User confirmation required before creating live listing",
            "message": "Please confirm: Do you want to create a live listing on Forest Market? This will upload images and publish your product.",
            "next_step": "Call this tool again with user_confirmed=True (or 'true', 'yes', 'confirm') after getting user approval",
            "received_confirmation": str(user_confirmed),
            "accepted_values": ["True", "true", "yes", "1", "confirm", "confirmed", "ok", "proceed"]
        }, indent=2)
    
    try:
        # Step 1: Export the draft using the shared internal function
        export_result = _export_draft_internal(draft_id, user_id, "forest_market", False)
        
        if "error" in export_result:
            return json.dumps(export_result, indent=2)
        
        product_data = export_result["product_data"]
        
        # Step 2: Convert exported data to upload parameters
        # Convert variations_data from dict to VariationData objects
        variations_data = None
        if product_data["variations_data"]:
            variations_data = [
                VariationData(name=v["name"], values=v["values"]) 
                for v in product_data["variations_data"]
            ]
        
        # Convert shipping_prices_data from dict to ShippingPriceData objects  
        shipping_prices_data = None
        if product_data["shipping_prices_data"]:
            shipping_prices_data = [
                ShippingPriceData(
                    country_code=sp["country_code"],
                    price=sp["price"],
                    currency_code=sp.get("currency_code", "USDT")
                )
                for sp in product_data["shipping_prices_data"]
            ]
        
        upload_params = {
            "title": product_data["title"],
            "description": product_data["description"],
            "category": product_data["category"],
            "image_file_paths": product_data["image_file_paths"],
            "price": product_data["price"],
            "quantity": product_data["quantity"],
            "payment_options": product_data["payment_options"],
            "session_token": session_token,
            "variations_data": variations_data,
            "shipping_prices_data": shipping_prices_data,
            "currency_code": "USDT",
            "trpc_endpoint": trpc_endpoint
        }
        
        # Add optional fields only if they have valid values
        if product_data["ship_from_country"]:
            upload_params["ship_from_country"] = product_data["ship_from_country"]
        if product_data["ship_to_countries"]:
            upload_params["ship_to_countries"] = product_data["ship_to_countries"]
        if product_data["condition"]:
            upload_params["condition"] = product_data["condition"]
        if product_data["discount_type"]:
            upload_params["discount_type"] = product_data["discount_type"]
        if product_data["discount_value"]:
            upload_params["discount_value"] = product_data["discount_value"]
        
        # Step 3: Create the listing using the internal function
        print(f"Debug - upload_params being passed to _upload_listing_internal:")
        for key, value in upload_params.items():
            print(f"  {key}: {value} (type: {type(value)})")
        
        upload_result_str = _upload_listing_internal(**upload_params)
        upload_result = json.loads(upload_result_str)
        
        # Step 4: Add draft information to response
        upload_result["source_draft"] = {
            "draft_id": draft_id,
            "version": export_result["metadata"]["version"],
            "created_at": export_result["metadata"]["created_at"],
            "updated_at": export_result["metadata"]["updated_at"]
        }
        
        return json.dumps(upload_result, indent=2)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Draft to listing error traceback:\n{error_traceback}")
        return json.dumps({
            "success": False,
            "error": f"Draft to listing conversion failed: {str(e)}",
            "traceback": error_traceback
        }, indent=2)


# Internal function for export logic that can be shared
def _export_draft_internal(
    draft_id: str,
    user_id: Optional[str] = None,
    export_format: str = "forest_market",
    include_mapping_info: bool = False
) -> Dict[str, Any]:
    """Internal export draft function that can be called from other functions"""
    
    draft = storage.get_draft(draft_id)
    if not draft:
        return {"error": f"Product draft {draft_id} not found"}
    
    # User permission check
    if user_id and draft.user_id and draft.user_id != user_id:
        return {"error": "Access denied: Draft belongs to different user"}
    
    if export_format == "forest_market":
        result = {
            "product_data": {
                "title": draft.title,
                "description": draft.description,
                "price": draft.price,
                "category": draft.category,
                "condition": draft.condition,
                "variations_data": draft.get_variations_data_dict(),
                "image_file_paths": draft.image_file_paths,
                "contact_email": draft.contact_email,
                "ship_from_country": draft.ship_from_country,
                "ship_to_countries": draft.ship_to_countries,
                "shipping_prices_data": draft.get_shipping_prices_data_dict(),
                "quantity": draft.quantity,
                "discount_type": draft.discount_type,
                "discount_value": draft.discount_value,
                "payment_options": draft.payment_options,
                "tags": draft.tags,
                "specifications": draft.specifications
            },
            "metadata": {
                "draft_id": draft.draft_id,
                "version": draft.version,
                "created_at": draft.created_at,
                "updated_at": draft.updated_at
            },
            "export_format": "forest_market",
            "ready_for_listing": True,
            "note": "Images exported as URLs. Convert to local file paths before using with upload_listing tool."
        }
        
        if include_mapping_info:
            result["upload_tool_mapping"] = {
                "field_mappings": {
                    "title": "title",
                    "description": "description", 
                    "category": "category",
                    "image_file_paths": "image_file_paths",
                    "price": "price",
                    "quantity": "quantity",
                    "payment_options": "payment_options",
                    "ship_from_country": "ship_from_country",
                    "ship_to_countries": "ship_to_countries",
                    "variations_data": "variations_data (ready to use)",
                    "shipping_prices_data": "shipping_prices_data (ready to use)",
                    "condition": "condition",
                    "discount_type": "discount_type",
                    "discount_value": "discount_value"
                },
                "required_transformations": [
                    "Convert image URLs to local file paths for image_file_paths parameter",
                    "Ensure discount_value follows validation: PERCENTAGE (0.1-0.5), FIXED_AMOUNT (positive value)"
                ]
            }
        
        return result
    elif export_format == "json":
        return {
            "export_data": draft.to_dict(),
            "export_format": "json"
        }
    else:
        return {"error": f"Unsupported export format: {export_format}"}

# Internal function for upload listing logic that can be shared
def _upload_listing_internal(
    title: str,
    description: str,
    category: str,
    image_file_paths: List[str],
    price: float,
    quantity: int,
    payment_options: List[str],
    session_token: str = os.getenv('FM_SESSION_TOKEN'),
    ship_from_country: Optional[str] = None,
    ship_to_countries: Optional[List[str]] = None,
    variations_data: Optional[List[VariationData]] = None,
    shipping_prices_data: Optional[List[ShippingPriceData]] = None,
    condition: Optional[str] = None,
    currency_code: str = "USDT",
    discount_type: Optional[str] = None,
    discount_value: Optional[float] = None,
    trpc_endpoint: str = "https://forestmarket.net/api/trpc/product.uploadListing?batch=1"
) -> str:
    """Internal upload listing function that can be called from other functions"""
    
    try:
        # Step 1: Upload images and collect URLs
        image_urls = []
        
        for file_path in image_file_paths:
            # Handle both URLs and local file paths
            if is_url(file_path):
                # Download image from URL to temporary file
                try:
                    local_file_path = download_image_from_url(file_path)
                    print(f"Downloaded image from URL: {file_path} -> {local_file_path}")
                except Exception as e:
                    return json.dumps({
                        "success": False,
                        "error": f"Failed to download image from URL {file_path}: {str(e)}"
                    }, indent=2)
            else:
                # Use local file path
                local_file_path = file_path
                if not os.path.exists(local_file_path):
                    return json.dumps({
                        "success": False,
                        "error": f"Image file not found: {file_path}"
                    }, indent=2)
            
            # Get file name and type
            file_name = os.path.basename(local_file_path)
            file_extension = file_name.split('.')[-1].lower()
            
            # Map file extensions to MIME types
            mime_types = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg', 
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'bmp': 'image/bmp',
                'ico': 'image/x-icon',
                'jp2': 'image/jp2',
                'svg': 'image/svg+xml'
            }
            
            file_type = mime_types.get(file_extension, 'image/jpeg')
            
            # Get presigned URL
            presigned_data = get_presigned_url(file_name, file_type, session_token)
            presigned_url = presigned_data["presignedUrl"]
            
            # Upload file to S3
            upload_success = upload_file_to_s3(local_file_path, presigned_url, file_type)
            
            if not upload_success:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to upload image: {file_path}"
                }, indent=2)
            
            # Add uploaded image URL
            image_urls.append(presigned_data["objectUrl"])
            
            # Clean up temporary file if it was downloaded from URL
            if is_url(file_path) and local_file_path.startswith('/tmp/'):
                try:
                    os.remove(local_file_path)
                    print(f"Cleaned up temporary file: {local_file_path}")
                except OSError:
                    pass  # Ignore cleanup errors
        
        # Step 2: Handle category-specific shipping requirements
        if category == "DIGITAL_GOODS":
            # For digital goods, set default shipping if not provided
            if ship_from_country is None:
                ship_from_country = "US"  # Default for digital goods
            if ship_to_countries is None:
                ship_to_countries = ["US"]  # Default for digital goods
        elif category == "CUSTOM":
            # For custom goods, both ship_from_country and ship_to_countries are required
            if ship_from_country is None or ship_to_countries is None:
                return json.dumps({
                    "success": False,
                    "error": "Both ship_from_country and ship_to_countries are required for CUSTOM category"
                }, indent=2)
        else:
            # For physical goods, both are required
            if ship_from_country is None or ship_to_countries is None:
                return json.dumps({
                    "success": False,
                    "error": "Both ship_from_country and ship_to_countries are required for physical products"
                }, indent=2)
        
        # Step 3: Prepare variations and shipping prices
        variations = None
        if variations_data:
            variations = [
                Variation(name=var.name, values=var.values)
                for var in variations_data
            ]
        
        shipping_prices = None
        if shipping_prices_data:
            shipping_prices = [
                ShippingPrice(
                    country_code=sp.country_code,
                    price=sp.price,
                    currency_code=sp.currency_code
                )
                for sp in shipping_prices_data
            ]
        
        # Step 4: Create product listing
        result = create_product_listing_internal(
            title=title,
            description=description,
            category=category,
            image_urls=image_urls,
            ship_from_country=ship_from_country,
            ship_to_countries=ship_to_countries,
            price=price,
            quantity=quantity,
            payment_options=payment_options,
            session_token=session_token,
            trpc_endpoint=trpc_endpoint,
            condition=condition,
            variations=variations,
            shipping_prices=shipping_prices,
            currency_code=currency_code,
            discount_type=discount_type,
            discount_value=discount_value
        )
        
        # Add uploaded image URLs to response
        result["uploaded_images"] = image_urls
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Upload listing internal error traceback:\n{error_traceback}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "traceback": error_traceback
        }, indent=2)

# Internal function for create_draft logic that can be shared
def _create_draft_internal(
    user_id: Annotated[str, Field(description="User identifier for draft ownership. Use provided user ID or 'ai_agent' if generating automatically.")],
    title: Annotated[str, Field(description="Product name extracted from user input. Examples: 'wireless gaming mouse', 'vintage leather jacket', 'Python programming course'")] = "",
    description: Annotated[str, Field(description="Detailed product description extracted from user input. Include features, benefits, use cases, and selling points mentioned by user.")] = "",
    price: Annotated[float, Field(description="Product price in USDT. Extract numerical value from user input (e.g., '$99.99' becomes 99.99, '50 dollars' becomes 50.0). Must be >= 0.", ge=0)] = 0.0,
    category: Annotated[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"], Field(description="Product category classification. Map user input to exact values: software/courses/digital content = DIGITAL_GOODS, phones/computers/gadgets = ELECTRONICS, clothing/accessories = FASHION, rare items/collectibles = COLLECTIBLES, blockchain hardware = DEPIN, personalized items = CUSTOM, everything else = OTHER")] = "OTHER",
    condition: Annotated[Literal["NEW", "USED"], Field(description="Product condition. Extract from user input: new/unused/fresh/mint = NEW, used/pre-owned/second-hand/refurbished = USED")] = "NEW",
    variations_data: Annotated[Optional[str], Field(description='''Product variations extracted from user input. EXACT FORMAT REQUIRED: null OR array matching VariationData class:
        class VariationData(BaseModel):
            name: str  # Required string field
            values: List[str]  # Required list of strings, must have at least 1 item
        
        MUST BE EXACTLY LIKE: [
          {"name": "Size", "values": ["S", "M", "L", "XL"]},
          {"name": "Color", "values": ["Black", "White", "Red"]},
          {"name": "Style", "values": ["Standard", "Premium"]}
        ]
     Only include variations explicitly mentioned by user.''')] = None,
    image_file_paths: Annotated[Optional[List[str]], Field(description="Image file paths provided by user or system. Accept absolute file paths like '/path/to/image.jpg'. Leave empty if no images specified.")] = None,
    contact_email: Annotated[str, Field(description="Seller contact email extracted from user input or use default like 'seller@example.com' if generating automatically")] = "",
    ship_from_country: Annotated[Optional[Literal["US", "SG", "HK", "KR", "JP"]], Field(description="Shipping origin country. Extract from user input: United States/America/USA = US, Singapore = SG, Hong Kong = HK, South Korea/Korea = KR, Japan = JP. Automatically set to null for DIGITAL_GOODS category.")] = None,
    ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Countries where product can be shipped. Extract from user input and map to valid codes: US, SG, HK, KR, JP. Example: 'ships to US and Singapore' becomes ['US','SG']. Automatically cleared for DIGITAL_GOODS.")] = None,
    shipping_prices_data: Annotated[Optional[List[ShippingPriceData]], Field(description='''Shipping costs per country.  
    must be null OR array matching ShippingPriceData class:
        class ShippingPriceData(BaseModel):
            country_code: str  # Required, must be one of ["US", "SG", "HK", "KR", "JP"]
            price: float  # Required, must be >= 0.0
            currency_code: str = "USDT"  # Optional, defaults to "USDT"
        
        MUST BE EXACTLY LIKE: [
          {"country_code": "US", "price": 0.0, "currency_code": "USDT"},
          {"country_code": "SG", "price": 25.0, "currency_code": "USDT"},
        ]
    Extract from user input like 'free shipping to US, $25 to Singapore' becomes [{'country_code': 'US', 'price': 0.0, 'currency_code': 'USDT'}, {'country_code': 'SG', 'price': 25.0, 'currency_code': 'USDT'}].
    Automatically cleared for DIGITAL_GOODS.''')] = None,
    quantity: Annotated[int, Field(description="Stock quantity extracted from user input. Examples: '10 available' = 10, '5 in stock' = 5, 'limited quantity' = 1-5, 'plenty available' = 20-50. Minimum value is 1.", ge=1)] = 1,
    discount_type: Annotated[Optional[Literal["", "FIXED_AMOUNT", "PERCENTAGE"]], Field(description="Discount type extracted from user input. Map: 'X% off' or 'X percent discount' = PERCENTAGE, '$X off' or 'X dollars off' = FIXED_AMOUNT, no discount mentioned = empty string or None")] = None,
    discount_value: Annotated[float, Field(description="Discount amount extracted from user input. For PERCENTAGE: convert percentage to decimal (15% = 0.15, must be 0.1-0.5). For FIXED_AMOUNT: dollar amount (5.0-50.0). No discount = 0.0.", ge=0)] = 0.0,
    payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Cryptocurrency payment methods. Map user input: 'ETH' or 'Ethereum' = ETH_ETHEREUM, 'ETH Base' = ETH_BASE, 'SOL' or 'Solana' = SOL_SOLANA, 'USDC' = USDC_ETHEREUM, 'USDC Base' = USDC_BASE, 'USDC Solana' = USDC_SOLANA, 'USDT' = USDT_ETHEREUM. Default to common options if not specified: ['ETH_ETHEREUM', 'USDC_BASE']")] = None,
    tags: Annotated[Optional[List[str]], Field(description="Search tags extracted from user input. Include product features, keywords, and relevant terms mentioned. Examples: gaming mouse -> ['gaming', 'wireless', 'rgb'], vintage jacket -> ['vintage', 'leather', 'fashion'], course -> ['programming', 'education', 'beginner']")] = None,
    specifications: Annotated[Optional[Dict[str, str]], Field(description="Technical specifications extracted from user input. Format as key-value pairs: {'Brand': 'Apple', 'Model': 'iPhone 15', 'Storage': '128GB', 'Color': 'Blue'}. Extract any technical details, dimensions, materials, features mentioned by user.")] = None
) -> Dict[str, Any]:
    """Internal create draft function that can be called from other functions"""
    
    # Auto-clear shipping fields for DIGITAL_GOODS
    if category == "DIGITAL_GOODS":
        ship_from_country = ""
        ship_to_countries = []
        shipping_prices_data = []
    
    # Convert variations_data to Variation objects if provided
    variations_objects = None
    if variations_data:
        variations_objects = [Variation(name=v.name, values=v.values) for v in variations_data]
    
    # Convert shipping_prices_data to ShippingPrice objects if provided
    shipping_objects = None
    if shipping_prices_data:
        shipping_objects = [
            ShippingPrice(
                country_code=sp.country_code,
                price=sp.price,
                currency_code=sp.currency_code
            )
            for sp in shipping_prices_data
        ]
    
    draft = ProductDraft(
        title=title,
        user_id=user_id,
        description=description,
        price=price,
        category=category,
        condition=condition,
        variations_data=variations_objects,
        image_file_paths=image_file_paths or [],
        contact_email=contact_email,
        ship_from_country=ship_from_country,
        ship_to_countries=ship_to_countries or [],
        shipping_prices_data=shipping_objects,
        quantity=quantity,
        discount_type=discount_type,
        discount_value=discount_value,
        payment_options=payment_options or [],
        tags=tags or [],
        specifications=specifications or {}
    )
    
    draft_id = storage.create_draft(draft)
    
    return {
        "draft_id": draft_id,
        "title": title,
        "created_at": draft.created_at,
        "status": "created"
    }

def _update_draft_internal(
    draft_id: Annotated[str, Field(description="Draft ID to update (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    title: Annotated[Optional[str], Field(description="Updated product title/name")] = None,
    description: Annotated[Optional[str], Field(description="Updated product description")] = None,
    price: Annotated[Optional[float], Field(description="Updated price in USDT (>= 0)", ge=0)] = None,
    category: Annotated[Optional[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]], Field(description="Updated Forest Market category")] = None,
    condition: Annotated[Optional[Literal["NEW", "USED"]], Field(description="Updated product condition")] = None,
    variations_data: Annotated[Optional[List[VariationData]], Field(description="Updated variations (replaces existing): [{'name': 'Size', 'values': ['S','M','L']}]")] = None,
    image_file_paths: Annotated[Optional[List[str]], Field(description="Updated image file paths (replaces existing list)")] = None,
    contact_email: Annotated[Optional[str], Field(description="Updated seller contact email")] = None,
    ship_from_country: Annotated[Optional[Literal["US", "SG", "HK", "KR", "JP"]], Field(description="Updated shipping origin (auto-cleared for DIGITAL_GOODS)")] = None,
    ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Updated shipping destinations (auto-cleared for DIGITAL_GOODS)")] = None,
    shipping_prices_data: Annotated[Optional[List[ShippingPriceData]], Field(description="Updated shipping fees (auto-cleared for DIGITAL_GOODS): [{'country_code': 'US', 'price': 15.0, 'currency_code': 'USDT'}]")] = None,
    quantity: Annotated[Optional[int], Field(description="Updated stock quantity (>= 1)", ge=1)] = None,
    discount_type: Annotated[Optional[Literal["", "FIXED_AMOUNT", "PERCENTAGE"]], Field(description="Updated discount type (empty string removes discount)")] = None,
    discount_value: Annotated[Optional[float], Field(description="Updated discount value (USDT for FIXED_AMOUNT, 0.1-0.5 for PERCENTAGE)", ge=0)] = None,
    payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Updated crypto payment methods (replaces existing)")] = None,
    tags: Annotated[Optional[List[str]], Field(description="Updated search tags (replaces existing list)")] = None,
    specifications: Annotated[Optional[Dict[str, str]], Field(description="Updated technical specs (replaces existing dict)")] = None
) -> Dict[str, Any]:
    """Internal function for updating product draft information with new data"""
    
    draft = storage.get_draft(draft_id)
    if not draft:
        return {"error": f"Product draft {draft_id} not found"}
    
    # User permission check
    if user_id and draft.user_id and draft.user_id != user_id:
        return {"error": "Access denied: Draft belongs to different user"}
    
    # If updating to DIGITAL_GOODS, clear shipping info
    if category == "DIGITAL_GOODS":
        ship_from_country = ""
        ship_to_countries = []
        shipping_prices_data = []
    
    updates = {}
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if price is not None:
        updates["price"] = price
    if category is not None:
        updates["category"] = category
    if condition is not None:
        updates["condition"] = condition
    if variations_data is not None:
        # Convert to Variation objects
        variations_objects = [Variation(name=v.name, values=v.values) for v in variations_data]
        updates["variations_data"] = variations_objects
    if image_file_paths is not None:
        updates["image_file_paths"] = image_file_paths
    if contact_email is not None:
        updates["contact_email"] = contact_email
    if ship_from_country is not None:
        updates["ship_from_country"] = ship_from_country
    if ship_to_countries is not None:
        updates["ship_to_countries"] = ship_to_countries
    if shipping_prices_data is not None:
        # Convert to ShippingPrice objects
        shipping_objects = [
            ShippingPrice(
                country_code=sp.country_code,
                price=sp.price,
                currency_code=sp.currency_code
            )
            for sp in shipping_prices_data
        ]
        updates["shipping_prices_data"] = shipping_objects
    if quantity is not None:
        updates["quantity"] = quantity
    if discount_type is not None:
        updates["discount_type"] = discount_type
    if discount_value is not None:
        updates["discount_value"] = discount_value
    if payment_options is not None:
        updates["payment_options"] = payment_options
    if tags is not None:
        updates["tags"] = tags
    if specifications is not None:
        updates["specifications"] = specifications
    
    success = storage.update_draft(draft_id, **updates)
    
    if success:
        updated_draft = storage.get_draft(draft_id)
        return {
            "status": "updated",
            "draft_id": draft_id,
            "version": updated_draft.version,
            "updated_at": updated_draft.updated_at
        }
    else:
        return {"error": "Update failed"}

def _remove_from_draft_internal(
    draft_id: Annotated[str, Field(description="Draft ID to update selectively (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    variation_options: Annotated[Optional[List[Dict[str, List[str]]]], Field(description="Remove specific variation options: [{'name': 'Size', 'values': ['S','M']}] (keeps other sizes)")] = None,
    variation_types: Annotated[Optional[List[str]], Field(description="Remove entire variation categories: ['Color'] (removes all colors)")] = None,
    image_file_paths: Annotated[Optional[List[str]], Field(description="Remove specific image file paths from existing list")] = None,
    tags: Annotated[Optional[List[str]], Field(description="Remove specific tags from existing list")] = None,
    specifications: Annotated[Optional[List[str]], Field(description="Remove spec keys: ['Weight'] (removes key-value pairs)")] = None,
    ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Remove shipping destinations from existing list")] = None,
    shipping_prices_data: Annotated[Optional[List[str]], Field(description="Remove shipping fees for countries: ['Canada'] (removes fee entries)")] = None,
    payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Remove payment methods from existing list")] = None
) -> Dict[str, Any]:
    """Internal function to remove specific options/items from existing draft fields"""
    
    draft = storage.get_draft(draft_id)
    if not draft:
        return {"error": f"Product draft {draft_id} not found"}
    
    # User permission check
    if user_id and draft.user_id and draft.user_id != user_id:
        return {"error": "Access denied: Draft belongs to different user"}
    
    updates = {}
    
    # Handle variation_options - remove specific options
    if variation_options:
        current_variations = [vars(v) for v in draft.variations_data]  # Convert to dict format
        for var_to_remove in variation_options:
            var_name = var_to_remove["name"]
            options_to_remove = var_to_remove["values"]
            
            # Find existing variation type
            existing_var = next((v for v in current_variations if v["name"] == var_name), None)
            if existing_var:
                remaining_options = [opt for opt in existing_var["values"] if opt not in options_to_remove]
                if remaining_options:
                    existing_var["values"] = remaining_options
                else:
                    # If no remaining options, remove entire variation type
                    current_variations.remove(existing_var)
        # Convert back to Variation objects
        variations_objects = [Variation(name=v['name'], values=v['values']) for v in current_variations]
        updates["variations_data"] = variations_objects
    
    # Handle variation_types - remove entire variation types
    if variation_types:
        current_variations = updates.get("variations_data", [vars(v) for v in draft.variations_data])
        if "variations_data" in updates:
            # If already updated, work with the updated objects
            current_variations = [vars(v) for v in updates["variations_data"]]
        current_variations = [v for v in current_variations if v["name"] not in variation_types]
        # Convert back to Variation objects
        variations_objects = [Variation(name=v['name'], values=v['values']) for v in current_variations]
        updates["variations_data"] = variations_objects
    
    # Handle image_file_paths - remove specific images
    if image_file_paths:
        current_images = [img for img in draft.image_file_paths if img not in image_file_paths]
        updates["image_file_paths"] = current_images
    
    # Handle tags - remove specific tags
    if tags:
        current_tags = [tag for tag in draft.tags if tag not in tags]
        updates["tags"] = current_tags
    
    # Handle specifications - remove specific specs
    if specifications:
        current_specs = draft.specifications.copy()
        for spec_key in specifications:
            if spec_key in current_specs:
                del current_specs[spec_key]
        updates["specifications"] = current_specs
    
    # Handle ship_to_countries - remove destinations
    if ship_to_countries:
        current_ship_to = [dest for dest in draft.ship_to_countries if dest not in ship_to_countries]
        updates["ship_to_countries"] = current_ship_to
    
    # Handle shipping_prices_data - remove specific destination fees
    if shipping_prices_data:
        current_fees_dict = [vars(f) for f in draft.shipping_prices_data]
        current_fees = [f for f in current_fees_dict if f["country_code"] not in shipping_prices_data]
        # Convert back to ShippingPrice objects
        shipping_objects = [
            ShippingPrice(
                country_code=f['country_code'],
                price=f['price'],
                currency_code=f.get('currency_code', 'USDT')
            )
            for f in current_fees
        ]
        updates["shipping_prices_data"] = shipping_objects
    
    # Handle payment_options - remove payment methods
    if payment_options:
        current_methods = [method for method in draft.payment_options if method not in payment_options]
        updates["payment_options"] = current_methods
    
    if not updates:
        return {"error": "No valid fields provided to remove"}
    
    success = storage.update_draft(draft_id, **updates)
    
    if success:
        updated_draft = storage.get_draft(draft_id)
        return {
            "status": "removed",
            "draft_id": draft_id,
            "version": updated_draft.version,
            "updated_at": updated_draft.updated_at,
            "modified_fields": list(updates.keys())
        }
    else:
        return {"error": "Remove operation failed"}


def check_upload_readiness(df: pd.DataFrame) -> Dict[str, Any]:
    """Check if dataframe is ready for product upload"""
    required_fields = ['title', 'description', 'price', 'category', "image_file_paths"]
    
    readiness = {
        'is_ready': True,
        'missing_columns': [],
        'columns_with_nulls': {},
        'data_quality_issues': []
    }
    
    # Check required columns exist
    for field in required_fields:
        if field not in df.columns:
            readiness['missing_columns'].append(field)
            readiness['is_ready'] = False
    
    # Check for null values in existing required columns
    for field in required_fields:
        if field in df.columns:
            null_count = df[field].isnull().sum()
            if null_count > 0:
                readiness['columns_with_nulls'][field] = int(null_count)
                readiness['is_ready'] = False
    
    # Additional quality checks
    if 'price' in df.columns:
        non_numeric_prices = 0
        for val in df['price'].dropna().head(10):
            try:
                float(str(val).replace('$', '').replace(',', ''))
            except:
                non_numeric_prices += 1
        if non_numeric_prices > 0:
            readiness['data_quality_issues'].append('price_column_contains_non_numeric_values')
    
    return readiness

# Global storage for active dataframes during processing sessions
active_dataframes = {}

def get_null_counts(df: pd.DataFrame) -> Dict[str, int]:
    """Safely get null counts for each column"""
    null_counts = {}
    for col in df.columns:
        try:
            # Handle the case where isnull().sum() might return a Series
            null_sum = df[col].isnull().sum()
            if hasattr(null_sum, 'iloc'):
                # It's a Series, get the first value
                null_counts[str(col)] = int(null_sum.iloc[0])
            else:
                # It's a scalar
                null_counts[str(col)] = int(null_sum)
        except Exception as e:
            # Fallback to 0 if there's any issue
            null_counts[str(col)] = 0
    return null_counts

def save_debug_csv(df: pd.DataFrame, session_id: str, operation_description: str) -> str:
    """Save dataframe to CSV for debugging purposes"""
    try:
        import re
        from datetime import datetime
        
        # Create debug directory if it doesn't exist
        debug_dir = "debug_csv"
        os.makedirs(debug_dir, exist_ok=True)
        
        # Create filename with timestamp and sanitized operation description
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sanitize operation description for filename
        safe_operation = re.sub(r'[^a-zA-Z0-9_-]', '_', operation_description)
        safe_operation = safe_operation[:50]  # Limit length
        if not safe_operation:
            safe_operation = "operation"
        
        filename = f"{session_id}_{timestamp}_{safe_operation}.csv"
        filepath = os.path.join(debug_dir, filename)
        
        # Save CSV with UTF-8 encoding to handle Chinese characters
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        print(f"Debug CSV saved: {filepath}", file=sys.stderr)
        print(f"  Shape: {df.shape}", file=sys.stderr)
        print(f"  Columns: {list(df.columns)}", file=sys.stderr)
        
        return filepath
        
    except Exception as e:
        print(f"Warning: Could not save debug CSV: {e}", file=sys.stderr)
        return ""

@mcp.tool(
    name="check_file",
    description="Load file and return raw data sample for LLM analysis."
)
def check_file(
    file_url: Annotated[str, Field(description="URL to downloadable file to analyze")],
    session_id: Annotated[str, Field(description="Unique session ID to track this file processing session")] = "default",
    sample_rows: Annotated[str, Field(description="Number of sample rows to return (5-50)")] = "15"
) -> Dict[str, Any]:
    """Load file and return raw sample data for client-side LLM to analyze"""
    
    try:
        # Convert string parameters to appropriate types
        sample_rows = int(sample_rows)
        sample_rows = max(5, min(50, sample_rows))  # Clamp to valid range
        # Download and parse file
        print(f"Downloading file: {file_url}")
        local_file_path = download_file_from_url(file_url)
        raw_data = parse_file_data(local_file_path, session_id)
        
        if not raw_data:
            return {"error": "No data found in file or file is empty"}
        
        # Convert to DataFrame
        df = pd.DataFrame(raw_data)
        
        # Store dataframe for later processing
        active_dataframes[session_id] = {
            'dataframe': df.copy(),
            'original_file_url': file_url,
            'file_type': local_file_path.split('.')[-1].lower(),
            'processing_history': []
        }
        
        # Return basic metadata and sample data for LLM analysis
        result = {
            'session_id': session_id,
            'file_metadata': {
                'file_url': file_url,
                'file_type': local_file_path.split('.')[-1].lower(),
                'total_rows': len(df),
                'total_columns': len(df.columns)
            },
            'original_columns': list(df.columns),
            'readable_columns': [f"Column_{col}" if isinstance(col, (int, float)) or (isinstance(col, str) and col.isdigit()) else str(col) for col in df.columns],
            'sample_data': df.head(sample_rows).rename(columns={col: f"Column_{col}" if isinstance(col, (int, float)) or (isinstance(col, str) and col.isdigit()) else str(col) for col in df.columns}).to_dict('records'),
            'message_for_llm': f"This file contains {len(df)} rows and {len(df.columns)} columns. The columns are shown with readable names (Column_0, Column_1, etc.) for clarity. When writing pandas code, use the ORIGINAL numeric indices: {list(df.columns)}. Please analyze the sample data to determine what transformations are needed for e-commerce product listing."
        }
        
        # Cleanup downloaded file
        # try:
        #     os.remove(local_file_path)
        # except:
        #     pass
        
        return result
    
    except Exception as e:
        return {
            "error": f"File loading failed: {str(e)}",
            "session_id": session_id,
            "suggestions": [
                "Check if file URL is accessible",
                "Ensure file format is supported (CSV, Excel, JSON)",
                "Verify file contains tabular data"
            ]
        }

@mcp.tool(
    name="execute_pandas_code",
    description="Execute pandas code on stored dataframe to update/correct the dataframe. Only returns success/failure. Use get_dataframe_status to inspect results."
)
def execute_pandas_code(
    session_id: Annotated[str, Field(description="Session ID for the dataframe to transform")],
    pandas_code: Annotated[str, Field(description="Pandas code to execute on the dataframe (string or JSON array of strings)")],
    operation_description: Annotated[str, Field(description="Description of what this operation does")] = ""
) -> Dict[str, Any]:
    """Execute LLM-generated pandas code on stored dataframe"""
    
    if session_id not in active_dataframes:
        return {"error": f"No active dataframe found for session {session_id}. Call check_file first."}
    
    try:
        # Handle both string and JSON array formats for pandas_code
        if pandas_code.strip().startswith('['):
            # Try to parse as JSON array
            try:
                code_array = json.loads(pandas_code)
                if isinstance(code_array, list):
                    pandas_code = '\n'.join(code_array)
                else:
                    return {"error": "JSON parsed but not an array"}
            except json.JSONDecodeError:
                return {"error": "Invalid JSON format for pandas_code array"}
        elif not isinstance(pandas_code, str):
            return {"error": "pandas_code must be a string or JSON array of strings"}
        
        # Get the stored dataframe
        session_data = active_dataframes[session_id]
        df = session_data['dataframe'].copy()
        
        # Prepare safe execution environment
        safe_globals = {
            'df': df,
            'pd': pd,
            'json': json,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'list': list,
            'dict': dict,
            'set': set,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
        }
        
        # Execute the pandas code
        exec(pandas_code, safe_globals)
        
        # Get the modified dataframe
        modified_df = safe_globals['df']
        
        # Update stored dataframe
        active_dataframes[session_id]['dataframe'] = modified_df
        active_dataframes[session_id]['processing_history'].append({
            'operation': operation_description,
            'code': pandas_code,
            'timestamp': pd.Timestamp.now().isoformat()
        })
        
        # Save debug CSV after each operation
        debug_csv_path = save_debug_csv(modified_df, session_id, operation_description)
        
        # Return simple success confirmation without data
        return {
            'success': True,
            'operation_description': operation_description,
            'rows_before': len(df),
            'rows_after': len(modified_df),
            'columns_before': len(df.columns),
            'columns_after': len(modified_df.columns),
            'message': 'Pandas code executed successfully. Use get_dataframe_status to inspect the results.'
        }
    
    except Exception as e:
        error_traceback = traceback.format_exc()
        return {
            'success': False,
            'error': str(e),
            'traceback': error_traceback,
            'code_attempted': pandas_code,
            'operation_description': operation_description
        }

@mcp.tool(
    name="get_dataframe_status", 
    description="Inspect current dataframe status and show sample data of current dataframe."
)
def get_dataframe_status(
    session_id: Annotated[str, Field(description="Session ID to check")]
) -> Dict[str, Any]:
    """Get current status and sample of processed dataframe"""
    
    if session_id not in active_dataframes:
        return {"error": f"No active dataframe found for session {session_id}"}
    
    session_data = active_dataframes[session_id]
    df = session_data['dataframe']
    
    # Prepare sample data in LLM-friendly format
    sample_df = df.head(10).copy()
    readable_columns = [f"Column_{col}" if isinstance(col, (int, float)) or (isinstance(col, str) and col.isdigit()) else str(col) for col in df.columns]
    
    # Print image-related columns to server logs for debugging
    image_columns = ['image_file_paths', 'image_url', 'images', 'image_urls', 'image_path']
    found_image_column = None
    for col in image_columns:
        if col in df.columns:
            found_image_column = col
            break
    
    if found_image_column:
        print(f"{found_image_column} column for session {session_id}:\n{df[found_image_column].head(10).to_string()}", file=sys.stderr)
    else:
        print(f"No image columns found for session {session_id}. Available columns: {list(df.columns)}", file=sys.stderr)
    
    # Rename columns in sample for better LLM understanding  
    column_mapping = {col: f"Column_{col}" if isinstance(col, (int, float)) or (isinstance(col, str) and col.isdigit()) else str(col) for col in df.columns}
    sample_df = sample_df.rename(columns=column_mapping)
    
    return {
        'session_id': session_id,
        'current_shape': df.shape,
        'original_columns': list(df.columns),
        'readable_columns': readable_columns,
        'current_sample': sample_df.to_dict('records'),
        'processing_history': session_data['processing_history'],
        'null_counts': get_null_counts(df),
        'ready_for_upload': check_upload_readiness(df),
        'message_for_llm': f"Current dataframe has {df.shape[0]} rows and {df.shape[1]} columns. Columns are shown with readable names for clarity. When writing pandas code, use the ORIGINAL numeric indices: {list(df.columns)}."
    }


# File processing utilities for auto_listing
def download_file_from_url(file_url: str) -> str:
    """Download file from URL or handle local file path"""
    try:
        # Handle local file paths
        if file_url.startswith('file://'):
            local_path = file_url[7:]  # Remove file:// prefix
            if os.path.exists(local_path):
                return local_path
            else:
                raise Exception(f"Local file not found: {local_path}")
        
        # Handle absolute local paths
        if os.path.isabs(file_url) and os.path.exists(file_url):
            return file_url
        
        # Handle relative local paths
        if not file_url.startswith(('http://', 'https://')):
            # Try as relative path from current directory
            relative_path = os.path.abspath(file_url)
            if os.path.exists(relative_path):
                return relative_path
            else:
                raise Exception(f"Local file not found: {file_url}")
        
        # Handle HTTP/HTTPS URLs
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        
        # Create temporary file
        temp_path = f"/tmp/uploaded_file_{hash(file_url) % 10000}"
        
        # Determine file extension from URL or content-type
        if file_url.lower().endswith('.xlsx'):
            temp_path += '.xlsx'
        elif file_url.lower().endswith('.csv'):
            temp_path += '.csv'
        elif file_url.lower().endswith('.json'):
            temp_path += '.json'
        else:
            # Try to determine from content-type header
            content_type = response.headers.get('content-type', '')
            if 'excel' in content_type or 'spreadsheet' in content_type:
                temp_path += '.xlsx'
            elif 'csv' in content_type:
                temp_path += '.csv'
            elif 'json' in content_type:
                temp_path += '.json'
            else:
                temp_path += '.txt'  # Default
        
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        return temp_path
    except Exception as e:
        raise Exception(f"Failed to access file from {file_url}: {e}")


def parse_file_data(file_path: str, session_id: str) -> List[Dict[str, Any]]:
    """Parse file data from CSV, Excel, or JSON formats with image extraction for Excel"""
    try:
        if file_path.lower().endswith('.csv'):
            # Parse CSV file
            df = pd.read_csv(file_path)
            return df.to_dict('records')
        
        elif file_path.lower().endswith(('.xlsx', '.xls')):
            # Parse Excel file with image extraction
            print("Parsing Excel file and extracting images...", file=sys.stderr)

            # Create session-persistent directory for images  
            import tempfile
            session_images_dir = f"/tmp/excel_images_{session_id}"
            os.makedirs(session_images_dir, exist_ok=True)
            print(f"Creating session images directory: {session_images_dir}", file=sys.stderr)
            
            df = process_excel_with_images(file_path, output_dir=session_images_dir)
            print(f"After processing: image_file_paths column exists = {'image_file_paths' in df.columns}", file=sys.stderr)
            if 'image_file_paths' in df.columns:
                print(f"After processing: sample image_file_paths = {df['image_file_paths'].head().tolist()}", file=sys.stderr)
            else:
                print("COLUMN_MISSING: image_file_paths not found in dataframe", file=sys.stderr)
            
            if not os.path.exists("temp_files"):
                os.makedirs("temp_files")
            df.to_csv("temp_files/processed_excel.csv", index=False)
            return df.to_dict('records')
        
        elif file_path.lower().endswith('.json'):
            # Parse JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both list of objects and single object
            if isinstance(data, list):
                return data
            else:
                return [data]
        
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
    
    except Exception as e:
        raise Exception(f"Failed to parse file {file_path}: {e}")

@mcp.tool(
    name="process_to_products",
    description="CONFIRMATION REQUIRED: Convert processed dataframe to product listings and upload them directly (optimized: skips draft creation). This will create REAL listings on Forest Market. ALWAYS ask user for explicit confirmation before calling this tool."
)
def process_to_products(
    session_id: Annotated[str, Field(description="Session ID with processed dataframe")],
    user_confirmed: Annotated[str, Field(description="User explicit confirmation to proceed with bulk listing creation. Can be boolean True or string 'true'/'yes'. Before using this tool, AI must ask user: 'Do you want to create live listings on Forest Market?' and get explicit yes/no confirmation.")] = "false",
    user_id: Annotated[str, Field(description="User ID for product ownership")] = "bulk_processor",
    max_products: Annotated[str, Field(description="Maximum products to process (1-200)")] = "50"
) -> Dict[str, Any]:
    """Convert processed dataframe to products and upload them directly (skips draft creation)"""
    
    # Check for user confirmation (flexible checking for various input types)
    if not is_user_confirmed(user_confirmed):
        return {
            "success": False,
            "error": "User confirmation required before creating live listings",
            "message": "Please confirm: Do you want to create live listings on Forest Market? This will process your dataframe and publish products.",
            "next_step": "Call this tool again with user_confirmed=True (or 'true', 'yes', 'confirm') after getting user approval",
            "received_confirmation": str(user_confirmed),
            "accepted_values": ["True", "true", "yes", "1", "confirm", "confirmed", "ok", "proceed"]
        }
    
    # Convert string parameters to appropriate types
    try:
        max_products = int(max_products)
        max_products = max(1, min(200, max_products))  # Clamp to valid range
    except ValueError:
        max_products = 50
    
    # Use environment variable if session_token is empty
    session_token = os.getenv('FM_SESSION_TOKEN')
    
    if session_id not in active_dataframes:
        return {"error": f"No active dataframe found for session {session_id}"}
    
    try:
        df = active_dataframes[session_id]['dataframe']
        
        # Check readiness
        readiness = check_upload_readiness(df)
        if not readiness['is_ready']:
            return {
                "error": "Dataframe not ready for upload",
                "readiness_check": readiness,
                "suggestions": [
                    "Use execute_pandas_code to fix missing columns",
                    "Handle null values in required fields",
                    "Ensure data quality issues are resolved"
                ]
            }
        
        # Limit processing
        products_df = df.head(max_products)
        
        results = {
            "total_rows": len(products_df),
            "successful_uploads": 0,
            "successful_listings": 0,  # Keep for backwards compatibility
            "failed_products": [],
            "session_processing": session_id,
            "optimized_workflow": "direct_upload_no_drafts"
        }
        
        # Process each row
        for idx, row in products_df.iterrows():
            try:
                # Convert row to product data (matching create_draft fields)
                product_data = {
                    'user_id': user_id,
                    'title': str(row.get('title', '')).strip(),
                    'description': str(row.get('description', '')).strip(),
                    'price': extract_price(row.get('price', 0)),
                    'category': normalize_category(row.get('category', 'OTHER')),
                    'condition': str(row.get('condition', 'NEW')).upper(),
                    'quantity': int(row.get('quantity', 1)) if pd.notna(row.get('quantity')) else 1,
                    'contact_email': str(row.get('contact_email', 'seller@example.com')),
                    'tags': parse_array_field(row.get('tags', [])),
                    'specifications': parse_object_field(row.get('specifications', {})),
                    'image_file_paths': parse_array_field(row.get('image_file_paths', row.get('image_urls', []))),
                    'payment_options': parse_array_field(row.get('payment_options', ['ETH_ETHEREUM', 'USDC_BASE'])),
                    'variations_data': parse_array_field(row.get('variations_data', [])) if (row.get('variations_data') is not None) and str(row.get('variations_data', '')).strip() and str(row.get('variations_data', '')).lower() not in ['nan', 'none', 'null'] else None,
                    'ship_from_country': str(row.get('ship_from_country', 'US')) if (row.get('ship_from_country') is not None) and str(row.get('ship_from_country', '')).lower() not in ['nan', 'none', 'null'] else 'US',
                    'ship_to_countries': parse_array_field(row.get('ship_to_countries', ['US'])),
                    'shipping_prices_data': parse_array_field(row.get('shipping_prices_data', [])) if (row.get('shipping_prices_data') is not None) and str(row.get('shipping_prices_data', '')).strip() and str(row.get('shipping_prices_data', '')).lower() not in ['nan', 'none', 'null'] else None,
                    'discount_type': str(row.get('discount_type')) if (row.get('discount_type') is not None) and str(row.get('discount_type', '')).lower() not in ['nan', 'none', 'null'] else None,
                    'discount_value': float(row.get('discount_value', 0)) if (row.get('discount_value') is not None) and str(row.get('discount_value', '')).lower() not in ['nan', 'none', 'null'] else 0.0,
                    'currency_code': str(row.get('currency_code', 'USDT'))
                }
                
                # Debug: Check image_file_paths
                print(f"Row {idx}: image_file_paths = {product_data['image_file_paths']}", file=sys.stderr)
                print(f"Row {idx}: raw image data = {row.get('image_file_paths', row.get('image_urls'))}", file=sys.stderr)
                
                # Check if images exist on disk
                valid_image_paths = []
                if product_data['image_file_paths']:
                    for img_path in product_data['image_file_paths']:
                        if isinstance(img_path, str) and os.path.exists(img_path):
                            valid_image_paths.append(img_path)
                        else:
                            print(f"Image not found: {img_path}", file=sys.stderr)
                
                # Skip products without valid images
                if not valid_image_paths:
                    results['failed_products'].append({
                        'row_index': idx,
                        'error': f'No valid image paths found. Original paths: {product_data["image_file_paths"]}. All images missing from disk - likely cleaned up from temporary storage'
                    })
                    continue
                
                # Update with only valid paths
                product_data['image_file_paths'] = valid_image_paths
                print(f"Row {idx}: Using {len(valid_image_paths)} valid images", file=sys.stderr)
                
                # Convert variations_data from dict to VariationData objects (same as draft_to_listing)
                variations_data = None
                if product_data["variations_data"]:
                    variations_data = [
                        VariationData(name=v["name"], values=v["values"]) 
                        for v in product_data["variations_data"]
                    ]
                
                # Convert shipping_prices_data from dict to ShippingPriceData objects (same as draft_to_listing)
                shipping_prices_data = None
                if product_data["shipping_prices_data"]:
                    shipping_prices_data = [
                        ShippingPriceData(
                            country_code=sp["country_code"],
                            price=sp["price"],
                            currency_code=sp.get("currency_code", "USDT")
                        )
                        for sp in product_data["shipping_prices_data"]
                    ]
                
                # Use the same internal function as draft_to_listing
                try:
                    upload_result_str = _upload_listing_internal(
                        title=product_data['title'],
                        description=product_data['description'],
                        category=product_data['category'],
                        image_file_paths=product_data['image_file_paths'],
                        price=product_data['price'],
                        quantity=product_data['quantity'],
                        payment_options=product_data['payment_options'],
                        session_token=session_token,
                        ship_from_country=product_data['ship_from_country'],
                        ship_to_countries=product_data['ship_to_countries'],
                        variations_data=variations_data,
                        shipping_prices_data=shipping_prices_data,
                        condition=product_data['condition'],
                        currency_code=product_data['currency_code'],
                        discount_type=product_data['discount_type'],
                        discount_value=product_data['discount_value'],
                        trpc_endpoint="https://forestmarket.net/api/trpc/product.uploadListing?batch=1"
                    )
                    # Parse upload result same as draft_to_listing
                    upload_result = json.loads(upload_result_str)
                    
                    if upload_result.get('success', False):
                        results['successful_uploads'] += 1
                        results['successful_listings'] += 1  # Keep this for backwards compatibility
                    else:
                        results['failed_products'].append({
                            'row_index': idx,
                            'error': f"Upload failed: {upload_result.get('error', 'Unknown error')}"
                        })
                        
                except Exception as upload_error:
                    results['failed_products'].append({
                        'row_index': idx,
                        'error': f"Direct upload failed: {str(upload_error)}"
                    })
                        
            except Exception as e:
                results['failed_products'].append({
                    'row_index': idx,
                    'error': str(e)
                })
        
        return results
        
    except Exception as e:
        return {
            "error": f"Processing failed: {str(e)}",
            "session_id": session_id
        }

# Coinbase CDP Tools
@mcp.tool(
    name="get_wallet_balance",
    description="Get token balances for a cryptocurrency wallet using Coinbase CDP. Returns ETH and token balances for the specified wallet address."
)
def get_wallet_balance(
    wallet_address: Annotated[str, Field(description="The cryptocurrency wallet address to check (Ethereum format: 0x...)")],
    network: Annotated[Literal["base-sepolia", "ethereum-sepolia"], Field(description="The blockchain network to query. Use 'base-sepolia' for Base testnet or 'ethereum-sepolia' for Ethereum testnet")] = "base-sepolia"
) -> str:
    """
    Get wallet balance using Coinbase CDP SDK
    """
    if not CDP_AVAILABLE:
        return "❌ Coinbase CDP SDK not available. Please install with: pip install cdp-sdk"
    
    if cdp_client is None:
        return "❌ Coinbase CDP not configured. Please set CDP_API_KEY_NAME and CDP_API_KEY_PRIVATE_KEY environment variables"
    
    try:
        # Use CDP Data API to get actual token balances
        from cdp.evm_client import EvmClient
        
        # Convert network name to CDP format
        network_mapping = {
            "base-sepolia": "base-sepolia",
            "ethereum-sepolia": "ethereum-sepolia"
        }
        
        if network not in network_mapping:
            return f"❌ Unsupported network: {network}. Supported: {list(network_mapping.keys())}"
        
        # Create EVM client and get balances
        evm_client = EvmClient(cdp_client)
        
        # Get token balances for the address
        balances = evm_client.list_evm_token_balances(
            network_id=network_mapping[network],
            address=wallet_address
        )
        
        if not balances or not balances.data:
            return f"""
✅ **Wallet Balance Query**
📍 **Address**: {wallet_address}
🌐 **Network**: {network}

💰 **Balances**: No tokens found or wallet is empty
            """.strip()
        
        # Format the results
        result = f"""
✅ **Wallet Balance Query**
📍 **Address**: {wallet_address}
🌐 **Network**: {network}

💰 **Token Balances**:
"""
        
        for balance in balances.data[:10]:  # Limit to top 10 tokens
            token_name = balance.token.name or "Unknown"
            token_symbol = balance.token.symbol or "???"
            amount = balance.amount
            decimals = balance.token.decimals or 18
            
            # Convert from smallest unit to readable format
            readable_amount = float(amount) / (10 ** decimals)
            
            result += f"\n• **{token_symbol}** ({token_name}): {readable_amount:.6f}"
        
        return result.strip()
        
    except Exception as e:
        return f"❌ Error querying wallet balance: {str(e)}"

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        # Run as MCP server
        mcp.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "http":
        # Run as HTTP server for public deployment (Render)
        port = int(os.getenv("PORT", 8000))
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        raise ValueError("Invalid argument. Please specify 'mcp' or 'http'")