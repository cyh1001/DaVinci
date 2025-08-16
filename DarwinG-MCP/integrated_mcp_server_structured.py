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
import json
from xxlimited import Str
import requests
import tempfile
import urllib.parse
from typing import List, Dict, Optional, Annotated, Literal, Any
from fastmcp import FastMCP
from pydantic import Field, BaseModel
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv("../.env")

from utils.custom_data_structure import *

# Import models and storage

from utils.models import ProductDraft
from utils.storage import DraftStorage
from utils.tools import download_image_from_url, is_url, is_user_confirmed, get_presigned_url, upload_file_to_s3, DifyParamParser

from utils.internal_tools import create_product_listing_internal

# Initialize storage
storage = DraftStorage()


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

print(f"OAuth authentication configured with AuthKit domain: {authkit_domain}")
print(f"Base URL: {base_url}")
print("To use this server, obtain a JWT token from the AuthKit domain and include it as a Bearer token")

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
                'webp': 'image/webp'
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


def upload_listing(
    title: str,
    description: str,
    category: Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "FASHION", "COLLECTIBLES", "CUSTOM", "OTHER"],
    image_file_paths: List[str],
    price: float,
    quantity: int,
    payment_options: List[str],
    session_token: str,
    ship_from_country: Optional[Literal["US", "SG", "HK", "KR", "JP"]] = None,
    ship_to_countries: Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]] = None,
    variations_data: Optional[List[VariationData]] = None,
    shipping_prices_data: Optional[List[ShippingPriceData]] = None,
    condition: Optional[Literal["NEW", "USED"]] = None,
    currency_code: str = "USDT",
    discount_type: Optional[Literal["PERCENTAGE", "FIXED_AMOUNT"]] = None,
    discount_value: Optional[float] = None,
    trpc_endpoint: str = "https://forestmarket.net/api/trpc/product.uploadListing?batch=1"
) -> str:
    """
    Create an e-commerce product listing with image upload.
    
    This tool handles the complete flow:
    1. Upload images to S3 using presigned URLs
    2. Create the product listing with uploaded image URLs
    
    VALIDATION RULES:
    - DIGITAL_GOODS: ship_from_country and ship_to_countries are OPTIONAL, condition is OPTIONAL
    - CUSTOM: ship_from_country and ship_to_countries are REQUIRED, condition is OPTIONAL  
    - Physical goods (DEPIN, ELECTRONICS, FASHION, COLLECTIBLES): ship_from_country, ship_to_countries, and condition are REQUIRED
    - Discount PERCENTAGE: must be between 0.1-0.5 (10%-50%)
    - Discount FIXED_AMOUNT: must be positive dollar amount (e.g., 50.0 for $50)
    """
    return _upload_listing_internal(
        title=title,
        description=description,
        category=category,
        image_file_paths=image_file_paths,
        price=price,
        quantity=quantity,
        payment_options=payment_options,
        session_token=session_token,
        ship_from_country=ship_from_country,
        ship_to_countries=ship_to_countries,
        variations_data=variations_data,
        shipping_prices_data=shipping_prices_data,
        condition=condition,
        currency_code=currency_code,
        discount_type=discount_type,
        discount_value=discount_value,
        trpc_endpoint=trpc_endpoint
    )

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