import os
from dotenv import load_dotenv
import requests
from typing import Any, Dict, List, Optional, Literal
from utils.tools import download_image_from_url, is_url, is_user_confirmed, get_presigned_url, upload_file_to_s3
from utils.custom_data_structure import Variation, ShippingPrice

load_dotenv("../.env")

from utils.custom_data_structure import *

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
    session_token: str = os.getenv('FM_SESSION_TOKEN'),
    trpc_endpoint: str = "https://forestmarket.net/api/trpc/product.uploadListing?batch=1",
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