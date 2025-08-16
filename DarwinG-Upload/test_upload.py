import os
import requests
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv("../../.env")

session_token = os.getenv("SESSION_TOKEN")

upload_image_url = "https://forestmarket.net/api/trpc/upload.getPresignedUrl?batch=1"

# Method 1: Using cookies parameter
cookies = {"__Secure-next-auth.session-token": session_token}


@dataclass
class Variation:
    name: str
    values: List[str]

@dataclass
class ShippingPrice:
    country_code: str
    price: float
    currency_code: str = "USDT"

def get_presigned_url(file_name: str, file_type: str, session_token: str):
    """Get presigned URL from the tRPC API"""
    
    # Replace with the actual tRPC endpoint URL from network tab
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

def upload_file_to_s3(file_path: str, presigned_url: str, file_type: str):
    """Upload file directly to S3 using presigned URL"""
    
    with open(file_path, 'rb') as file:
        # For S3 presigned URLs, usually just PUT the file content
        headers = {
            "Content-Type": file_type,
        }
        
        response = requests.put(
            presigned_url,
            data=file,
            headers=headers
        )
        
        if response.status_code in [200, 204]:
            print("✅ File uploaded successfully!")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

def create_product_listing(
    # Required fields
    title: str,
    description: str,
    category: Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "FASHION", "COLLECTIBLES", "CUSTOM", "OTHER"],
    image_urls: List[str],
    ship_from_country: str,
    ship_to_countries: Literal["US", "SG", "HK", "KR", "JP"],
    price: float,
    quantity: int,
    payment_options: Literal["ETH_ETHEREUM", "SOL_SOLANA", "USDC_BASE", "USDC_ETHEREUM", "USDT_ETHEREUM", "USDC_SOLANA", "ETH_BASE"],  # e.g., ["ETH_ETHEREUM", "SOL_SOLANA", "USDC_BASE"]
    session_token: str,
    trpc_endpoint: str,
    
    # Optional fields
    condition: Optional[Literal["NEW", "USED"]] = None,
    variations: Optional[List[Variation]] = None,
    shipping_prices: Optional[List[ShippingPrice]] = None,
    currency_code: str = "USDT",
    discount_type: Optional[Literal["PERCENTAGE", "FIXED"]] = None,
    discount_value: Optional[float] = None
) -> Dict:
    """
    Create a product listing with all the options from the website
    
    Args:
        title: Product title
        description: Product description
        category: Product category
        image_urls: List of uploaded S3 image URLs
        ship_from_country: Country code to ship from (e.g., "US")
        ship_to_countries: List of country codes to ship to (max 5)
        price: Product price
        quantity: Available quantity
        payment_options: List of payment method IDs
        session_token: Authentication session token
        trpc_endpoint: The tRPC endpoint URL
        condition: Product condition (required unless DIGITAL_GOODS or CUSTOM)
        variations: List of product variations (optional)
        shipping_prices: Custom shipping prices per country (optional)
        currency_code: Currency for pricing (default: USDT)
        discount_type: Type of discount (optional)
        discount_value: Discount amount/percentage (optional)
    
    Returns:
        Dict with success status and response data
    """
    
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
            
            # Check if this payment method already exists in selected_payments
            existing = next((p for p in selected_payments if p["id"] == payment_data["id"]), None)
            if existing:
                # Add chain to existing payment method
                existing["chains"].extend(payment_data["chains"])
            else:
                # Add new payment method
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
        # Default: free shipping to all countries
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
    
    try:
        print(f"📤 Creating listing: {title}")
        print(f"📂 Category: {category}")
        print(f"💰 Price: {price} {currency_code}")
        print(f"📦 Quantity: {quantity}")
        print(f"🚚 Ship from {ship_from_country} to {ship_to_countries}")
        print(f"💳 Payment options: {payment_options}")
        
        response = requests.post(
            trpc_endpoint,
            json=payload,
            headers=headers,
            cookies=cookies
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            listing_data = result[0]["result"]["data"]["json"]
            
            print("✅ Listing created successfully!")
            print(f"🆔 EID: {listing_data['eid']}")
            
            return {
                "success": True,
                "eid": listing_data["eid"],
                "post_listing": listing_data["postListing"],
                "license_key": listing_data["licenseKey"],
                "payload_sent": payload,
                "response": result
            }
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "payload_sent": payload
            }
            
    except Exception as e:
        print(f"💥 Exception occurred: {e}")
        return {
            "success": False,
            "error": str(e),
            "payload_sent": payload
        }

# Example usage functions
def test_simple_electronics():
    """Test with simple electronics product"""
    return create_product_listing(
        title="iPhone 15 Pro",
        description="Brand new iPhone 15 Pro in excellent condition",
        category="ELECTRONICS",
        image_urls=["https://forest-market-public-images-prod.s3.us-west-2.amazonaws.com/uploads/your-image.png"],
        ship_from_country="US",
        ship_to_countries=["US", "CA"],
        price=999.99,
        quantity=1,
        payment_options=["USDT_ETHEREUM", "ETH_ETHEREUM"],
        session_token="your_session_token",
        trpc_endpoint="https://forestmarket.net/api/trpc/listings.create",
        condition="NEW"
    )

def test_with_variations_and_discount():
    """Test with variations and discount"""
    variations = [
        Variation(name="Color", values=["Red", "Blue", "Green"]),
        Variation(name="Size", values=["S", "M", "L"])
    ]
    
    shipping_prices = [
        ShippingPrice("US", 5.99),
        ShippingPrice("SG", 12.99)
    ]

    presigned_data = get_presigned_url("/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg", "image/jpeg", session_token)
    presigned_url = presigned_data["presignedUrl"]
    upload_file_to_s3("/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg", presigned_url, "image/jpeg")
    image_urls = [presigned_data["objectUrl"]]

    return create_product_listing(
        title="Test T-shirt",
        description="Testing API for T-shirt",
        category="FASHION",
        image_urls=image_urls,
        ship_from_country="US",
        ship_to_countries=["US", "SG"],
        price=29.99,
        quantity=50,
        payment_options=["USDC_BASE", "SOL_SOLANA"],
        session_token=session_token,
        trpc_endpoint="https://forestmarket.net/api/trpc/product.uploadListing?batch=1",
        condition="NEW",
        variations=variations,
        shipping_prices=shipping_prices,
        discount_type="PERCENTAGE",
        discount_value=0.15  # 15% discount
    )

def test_digital_goods():
    """Test digital goods (no condition or shipping needed)"""
    return create_product_listing(
        title="Premium Software License",
        description="Lifetime license for premium software",
        category="DIGITAL_GOODS",
        image_urls=["https://forest-market-public-images-prod.s3.us-west-2.amazonaws.com/uploads/software.png"],
        ship_from_country="US",  # Still needed for currency/legal reasons
        ship_to_countries=["US"],  # Digital delivery
        price=199.99,
        quantity=100,
        payment_options=["ETH_ETHEREUM", "USDC_ETHEREUM"],
        session_token="your_session_token",
        trpc_endpoint="https://forestmarket.net/api/trpc/listings.create"
        # No condition needed for digital goods
    )

# Run tests
if __name__ == "__main__":
    # Test the example from your payload
    result = test_with_variations_and_discount()
    print(f"\n🏁 Final result: {result}")