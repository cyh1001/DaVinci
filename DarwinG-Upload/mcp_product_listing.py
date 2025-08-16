#!/usr/bin/env python3
"""
MCP Tool for E-commerce Product Listing Creation

This MCP tool integrates with an e-commerce API to create product listings.
It handles image upload to S3 and product creation in a single operation.
"""

import os
import requests
from typing import List, Dict, Optional, Literal, Any
from dataclasses import dataclass
import json


@dataclass
class Variation:
    """Product variation data class"""
    name: str
    values: List[str]


@dataclass
class ShippingPrice:
    """Shipping price data class"""
    country_code: str
    price: float
    currency_code: str = "USDT"


def get_presigned_url(file_name: str, file_type: str, session_token: str) -> Dict[str, Any]:
    """Get presigned URL from the tRPC API for S3 upload"""
    
    url = "https://forestmarket.net/api/trpc/upload.getPresignedUrl?batch=1"
    
    payload = {
        "0": {
            "json": {
                "fileName": file_name,
                "fileType": file_type
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "trpc-accept": "application/json",
    }
    
    cookies = {
        "__Secure-next-auth.session-token": session_token
    }
    
    response = requests.post(url, json=payload, headers=headers, cookies=cookies)
    
    if response.status_code == 200:
        result = response.json()
        return result[0]["result"]["data"]["json"]
    else:
        raise Exception(f"Failed to get presigned URL: {response.status_code} - {response.text}")


def upload_file_to_s3(file_path: str, presigned_url: str, file_type: str) -> bool:
    """Upload file directly to S3 using presigned URL"""
    
    with open(file_path, 'rb') as file:
        headers = {
            "Content-Type": file_type,
        }
        
        response = requests.put(
            presigned_url,
            data=file,
            headers=headers
        )
        
        return response.status_code in [200, 204]


def create_product_listing_internal(
    title: str,
    description: str,
    category: Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "FASHION", "COLLECTIBLES", "CUSTOM", "OTHER"],
    image_urls: List[str],
    ship_from_country: str,
    ship_to_countries: List[str],
    price: float,
    quantity: int,
    payment_options: List[str],
    session_token: str,
    trpc_endpoint: str,
    condition: Optional[Literal["NEW", "USED"]] = None,
    variations: Optional[List[Variation]] = None,
    shipping_prices: Optional[List[ShippingPrice]] = None,
    currency_code: str = "USDT",
    discount_type: Optional[Literal["PERCENTAGE", "FIXED_AMOUNT"]] = None,
    discount_value: Optional[float] = None
) -> Dict[str, Any]:
    
    # Validation
    if len(ship_to_countries) > 5:
        raise ValueError("Maximum 5 ship-to countries allowed")
    
    if len(image_urls) == 0:
        raise ValueError("At least 1 image is required")
    
    if category not in ["DIGITAL_GOODS", "CUSTOM"] and condition is None:
        raise ValueError("Condition is required for physical products")
    
    if discount_type and not discount_value:
        raise ValueError("Discount value is required when discount type is specified")
    
    if discount_type == "PERCENTAGE" and (discount_value < 0.1 or discount_value > 0.5):
        raise ValueError("Percentage discount must be between 10% (0.1) and 50% (0.5)")
    
    if discount_type == "FIXED_AMOUNT" and discount_value <= 0:
        raise ValueError("Fixed amount discount must be a positive value (e.g., 50.0 for $50 discount)")
    
    # Payment options mapping
    payment_options_map = {
        "ETH_ETHEREUM": {
            "id": "ethereum",
            "name": "Ether",
            "symbol": "ETH",
            "decimals": 18,
            "chains": [{"contractAddress": None, "id": 1, "name": "Ethereum"}]
        },
        "ETH_BASE": {
            "id": "ethereum",
            "name": "Ether", 
            "symbol": "ETH",
            "decimals": 18,
            "chains": [{"id": 8453, "contractAddress": None, "name": "Base"}]
        },
        "SOL_SOLANA": {
            "id": "solana",
            "name": "Solana",
            "symbol": "SOL", 
            "decimals": 9,
            "chains": [{"contractAddress": None, "id": 0, "name": "Solana"}]
        },
        "USDC_ETHEREUM": {
            "id": "usd-coin",
            "name": "USDC",
            "symbol": "USDC",
            "decimals": 6,
            "chains": [{"contractAddress": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "id": 1, "name": "Ethereum"}]
        },
        "USDC_BASE": {
            "id": "usd-coin",
            "name": "USDC",
            "symbol": "USDC", 
            "decimals": 6,
            "chains": [{"contractAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "id": 8453, "name": "Base"}]
        },
        "USDC_SOLANA": {
            "id": "usd-coin",
            "name": "USDC",
            "symbol": "USDC",
            "decimals": 6,
            "chains": [{"contractAddress": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "id": 0, "name": "Solana"}]
        },
        "USDT_ETHEREUM": {
            "id": "tether",
            "name": "Tether",
            "symbol": "USDT",
            "decimals": 6,
            "chains": [{"contractAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7", "id": 1, "name": "Ethereum"}]
        }
    }
    
    # Build payment options for payload
    selected_payments = []
    for payment_id in payment_options:
        if payment_id in payment_options_map:
            payment_data = payment_options_map[payment_id]
            
            existing = next((p for p in selected_payments if p["id"] == payment_data["id"]), None)
            if existing:
                existing["chains"].extend(payment_data["chains"])
            else:
                selected_payments.append(payment_data.copy())
    
    # Build shipping prices
    if shipping_prices:
        ship_prices = [
            {
                "countryCode": sp.country_code,
                "price": sp.price,
                "currencyCode": sp.currency_code
            }
            for sp in shipping_prices
        ]
    else:
        ship_prices = [
            {"countryCode": country, "price": 0, "currencyCode": currency_code}
            for country in ship_to_countries
        ]
    
    # Build variations
    variations_payload = []
    if variations:
        variations_payload = [
            {"name": var.name, "values": var.values}
            for var in variations
        ]
    
    # Build the payload
    payload = {
        "0": {
            "json": {
                "title": title,
                "description": description,
                "price": price,
                "images": image_urls,
                "currencyCode": currency_code,
                "countryCode": ship_from_country,
                "category": category,
                "paymentOptions": selected_payments,
                "shipToCountries": ship_to_countries,
                "shipPrices": ship_prices,
                "quantity": quantity,
                "variations": variations_payload
            }
        }
    }
    
    # Add optional fields
    if condition:
        payload["0"]["json"]["condition"] = condition
    
    if discount_type and discount_value:
        payload["0"]["json"]["discountType"] = discount_type
        payload["0"]["json"]["discountValue"] = discount_value
    
    # Make the request
    headers = {
        "Content-Type": "application/json",
        "trpc-accept": "application/json",
    }
    
    cookies = {
        "__Secure-next-auth.session-token": session_token
    }
    
    response = requests.post(
        trpc_endpoint,
        json=payload,
        headers=headers,
        cookies=cookies
    )
    
    if response.status_code == 200:
        result = response.json()
        listing_data = result[0]["result"]["data"]["json"]
        
        return {
            "success": True,
            "eid": listing_data["eid"],
            "post_listing": listing_data["postListing"],
            "license_key": listing_data["licenseKey"],
            "response": result
        }
    else:
        return {
            "success": False,
            "status_code": response.status_code,
            "error": response.text
        }


def create_product_listing_mcp(
    title: str,
    description: str,
    category: str,
    image_file_paths: List[str],
    price: float,
    quantity: int,
    payment_options: List[str],
    session_token: str,
    ship_from_country: Optional[str] = None,
    ship_to_countries: Optional[List[str]] = None,
    variations_data: Optional[List[Dict[str, Any]]] = None,
    shipping_prices_data: Optional[List[Dict[str, Any]]] = None,
    condition: Optional[str] = None,
    currency_code: str = "USDT",
    discount_type: Optional[str] = None,
    discount_value: Optional[float] = None,
    trpc_endpoint: str = "https://forestmarket.net/api/trpc/product.uploadListing?batch=1"
) -> Dict[str, Any]:
    """
    MCP Tool: Create a product listing with image upload
    
    This tool handles the complete flow:
    1. Upload images to S3 using presigned URLs
    2. Create the product listing with uploaded image URLs
    
    Args:
        title: Product title
        description: Product description  
        category: Product category (DIGITAL_GOODS, DEPIN, ELECTRONICS, FASHION, COLLECTIBLES, CUSTOM, OTHER)
        image_file_paths: List of local file paths to upload as product images
        ship_from_country: Country code to ship from (optional for DIGITAL_GOODS)
        ship_to_countries: List of country codes to ship to (optional for DIGITAL_GOODS and CUSTOM)
        price: Product price
        quantity: Available quantity
        payment_options: List of payment method IDs (ETH_ETHEREUM, SOL_SOLANA, USDC_BASE, etc.)
        session_token: Authentication session token
        variations_data: Optional list of variation dicts with 'name' and 'values' keys
        shipping_prices_data: Optional list of shipping price dicts with 'country_code', 'price', 'currency_code' keys
        condition: Product condition (NEW, USED) - required for physical products
        currency_code: Currency for pricing (default: USDT)
        discount_type: Type of discount (PERCENTAGE, FIXED_AMOUNT)
        discount_value: Discount amount/percentage
        trpc_endpoint: The tRPC endpoint URL
        
    Returns:
        Dict with success status and response data
    """
    
    try:
        # Step 1: Upload images and collect URLs
        image_urls = []
        
        for file_path in image_file_paths:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"Image file not found: {file_path}"
                }
            
            # Get file name and type
            file_name = os.path.basename(file_path)
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
            upload_success = upload_file_to_s3(file_path, presigned_url, file_type)
            
            if not upload_success:
                return {
                    "success": False,
                    "error": f"Failed to upload image: {file_path}"
                }
            
            # Add uploaded image URL
            image_urls.append(presigned_data["objectUrl"])
        
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
                return {
                    "success": False,
                    "error": "Both ship_from_country and ship_to_countries are required for CUSTOM category"
                }
        else:
            # For physical goods, both are required
            if ship_from_country is None or ship_to_countries is None:
                return {
                    "success": False,
                    "error": "Both ship_from_country and ship_to_countries are required for physical products"
                }
        
        # Step 3: Prepare variations and shipping prices
        variations = None
        if variations_data:
            variations = [
                Variation(name=var["name"], values=var["values"])
                for var in variations_data
            ]
        
        shipping_prices = None
        if shipping_prices_data:
            shipping_prices = [
                ShippingPrice(
                    country_code=sp["country_code"],
                    price=sp["price"],
                    currency_code=sp.get("currency_code", "USDT")
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
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# FastMCP Server Integration
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        # FastMCP server mode
        from fastmcp import FastMCP
        from typing import Literal
        
        mcp = FastMCP("Forest Market MCP Server")
        
        @mcp.tool()
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
            variations_data: Optional[List[Dict[str, Any]]] = None,
            shipping_prices_data: Optional[List[Dict[str, Any]]] = None,
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
            
            Args:
                title: Product title
                description: Product description  
                category: Product category
                image_file_paths: List of local file paths to upload as product images
                ship_from_country: Country code to ship from (optional for DIGITAL_GOODS, required for others)
                ship_to_countries: List of country codes to ship to (optional for DIGITAL_GOODS and CUSTOM categories)
                price: Product price
                quantity: Available quantity
                payment_options: List of payment method IDs (ETH_ETHEREUM, SOL_SOLANA, USDC_BASE, etc.)
                session_token: Authentication session token
                variations_data: Optional list of variation dicts with 'name' and 'values' keys
                shipping_prices_data: Optional list of shipping price dicts with 'country_code', 'price', 'currency_code' keys
                condition: Product condition (NEW, USED) - required for physical products, optional for DIGITAL_GOODS and CUSTOM
                currency_code: Currency for pricing (default: USDT)
                discount_type: Type of discount (PERCENTAGE, FIXED_AMOUNT)
                discount_value: Discount amount/percentage (For PERCENTAGE use 0.1-0.5, for FIXED_AMOUNT use absolute price)
                trpc_endpoint: The tRPC endpoint URL
                
            Returns:
                JSON string with success status and response data
            """
            result = create_product_listing_mcp(
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
            return json.dumps(result, indent=2)
        
        # Run the FastMCP server
        mcp.run()