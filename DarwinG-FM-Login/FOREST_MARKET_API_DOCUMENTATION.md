# Forest Market API Documentation

## Table of Contents
1. [Authentication](#authentication)
2. [API Base URLs](#api-base-urls)
3. [Image Upload Flow](#image-upload-flow)
4. [Product Listing API](#product-listing-api)
5. [Data Structures](#data-structures)
6. [Validation Rules](#validation-rules)
7. [Error Handling](#error-handling)
8. [Complete Integration Examples](#complete-integration-examples)
9. [API Endpoints Reference](#api-endpoints-reference)

---

## Authentication

### MetaMask Authentication Flow

Forest Market uses **NextAuth.js** with **Dynamic.xyz** as the authentication provider for MetaMask wallet integration.

**CRITICAL:** Authentication requires proper session cookie management to retrieve the final `__Secure-next-auth.session-token`. A backend proxy server with persistent session handling is essential for successful integration.

#### Frontend MetaMask Connection
```javascript
const connectWallet = async () => {
    if (typeof window.ethereum !== 'undefined') {
        try {
            const accounts = await window.ethereum.request({
                method: 'eth_requestAccounts'
            });
            return accounts[0]; // Returns wallet address
        } catch (error) {
            console.error('MetaMask connection failed:', error);
        }
    }
};
```

#### Complete Authentication Process
The authentication process involves 6 distinct steps with Dynamic.xyz:

1. **Get CSRF Token**: Retrieve CSRF token and store invisible CSRF cookie
2. **Get Nonce**: Fetch fresh nonce from Dynamic.xyz API  
3. **Sign Message**: User signs SIWE message with MetaMask
4. **Verify Signature**: Validate signature with Dynamic.xyz to get JWT
5. **Exchange JWT**: Trade JWT + CSRF token for Forest Market session token
6. **Verify Session**: Confirm session token works

#### Session Token Format
```python
# Session token is stored in cookies (extracted from Set-Cookie header)
session_token = "__Secure-next-auth.session-token"

# Headers for all API calls
headers = {
    "Content-Type": "application/json",
    "trpc-accept": "application/json",
}

# Cookies for authentication
cookies = {
    "__Secure-next-auth.session-token": session_token
}

# Authentication endpoints
DYNAMIC_BASE_URL = "https://app.dynamicauth.com/api/v0/sdk"
DYNAMIC_ENVIRONMENT_ID = "02e5c99f-a7aa-4841-b64a-df128fa8e08f"
FOREST_MARKET_AUTH_BASE = "https://forestmarket.net/api/auth"
```

---

## API Base URLs

### Production
```
Base URL: https://forestmarket.net/api/trpc
```

### Development (if available)
```
Base URL: https://dev.forestmarket.net/api/trpc
```

---

## Image Upload Flow

### Step 1: Get Presigned URL

**Endpoint:** `POST /upload.getPresignedUrl?batch=1`

**Purpose:** Get a presigned URL from Forest Market's S3 bucket for direct file upload.

```python
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
```

**Response Format:**
```json
{
    "presignedUrl": "https://s3.amazonaws.com/...",
    "objectUrl": "https://forestmarket.s3.amazonaws.com/images/filename.jpg",
    "fileType": "image/jpeg"
}
```

### Step 2: Upload to S3

**Purpose:** Upload file directly to S3 using the presigned URL.

```python
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
```

### Complete Image Upload Process

```python
def upload_images_to_forest_market(image_paths: List[str], session_token: str) -> List[str]:
    """Complete image upload workflow"""
    uploaded_urls = []
    
    for image_path in image_paths:
        # Get file info
        file_name = os.path.basename(image_path)
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
        
        # Step 1: Get presigned URL
        presigned_data = get_presigned_url(file_name, file_type, session_token)
        
        # Step 2: Upload to S3
        upload_success = upload_file_to_s3(image_path, presigned_data["presignedUrl"], file_type)
        
        if not upload_success:
            raise Exception(f"Failed to upload image: {image_path}")
        
        # Step 3: Collect uploaded URL
        uploaded_urls.append(presigned_data["objectUrl"])
    
    return uploaded_urls
```

---

## Product Listing API

### Create Product Listing

**Endpoint:** `POST /product.uploadListing?batch=1`

**Purpose:** Create a new product listing on Forest Market.

```python
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
        raise ValueError("Fixed amount discount must be a positive value")
    
    # Build payment options
    selected_payments = build_payment_options(payment_options)
    
    # Build shipping prices
    ship_prices = build_shipping_prices(shipping_prices, ship_to_countries, currency_code)
    
    # Build variations
    variations_payload = build_variations_payload(variations)
    
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
    
    response = requests.post(trpc_endpoint, json=payload, headers=headers, cookies=cookies)
    
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
```

---

## Data Structures

### Payment Options Mapping

```python
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
```

### Product Categories

```python
categories = [
    "DIGITAL_GOODS",  # Software, courses, digital content
    "DEPIN",          # Blockchain hardware
    "ELECTRONICS",    # Phones, computers, gadgets
    "FASHION",        # Clothing, accessories
    "COLLECTIBLES",   # Rare items, collectibles
    "CUSTOM",         # Personalized items
    "OTHER"           # Everything else
]
```

### Supported Countries

```python
supported_countries = ["US", "SG", "HK", "KR", "JP"]
```

### Product Variations

```python
@dataclass
class Variation:
    """Product variation data class"""
    name: str
    values: List[str]

# Example:
variations = [
    Variation(name="Size", values=["S", "M", "L", "XL"]),
    Variation(name="Color", values=["Black", "White", "Red"])
]
```

### Shipping Prices

```python
@dataclass
class ShippingPrice:
    """Shipping price data class"""
    country_code: str
    price: float
    currency_code: str = "USDT"

# Example:
shipping_prices = [
    ShippingPrice(country_code="US", price=0.0, currency_code="USDT"),
    ShippingPrice(country_code="SG", price=25.0, currency_code="USDT")
]
```

---

## Validation Rules

### Image Requirements
- **Minimum:** At least 1 image required
- **Maximum:** No explicit limit (recommended: 5-10 images)
- **Supported formats:** JPG, JPEG, PNG, GIF, WebP
- **File size:** No explicit limit (recommended: < 10MB per image)

### Shipping Requirements
- **DIGITAL_GOODS:** No shipping required (auto-cleared)
- **Physical products:** Both `ship_from_country` and `ship_to_countries` required
- **Maximum ship-to countries:** 5 countries
- **Supported countries:** US, SG, HK, KR, JP

### Price Requirements
- **Currency:** USDT (default)
- **Minimum:** 0.0 (free items allowed)
- **Maximum:** No explicit limit

### Discount Validation
- **PERCENTAGE:** Must be between 0.1-0.5 (10%-50%)
- **FIXED_AMOUNT:** Must be positive value (e.g., 50.0 for $50 discount)
- **Required:** If `discount_type` is specified, `discount_value` is required

### Product Condition
- **Required for:** All physical products except DIGITAL_GOODS and CUSTOM
- **Values:** "NEW" or "USED"

### Payment Options
- **Minimum:** At least one payment method required
- **Supported:** Multiple chains per token
- **Format:** Must use exact payment option keys from mapping

---

## Error Handling

### Common Error Responses

#### Authentication Errors
```json
{
    "success": false,
    "error": "Authentication failed",
    "status_code": 401
}
```

#### Validation Errors
```json
{
    "success": false,
    "error": "Validation failed: At least 1 image is required",
    "status_code": 400
}
```

#### Server Errors
```json
{
    "success": false,
    "error": "Internal server error",
    "status_code": 500
}
```

### Error Handling in Code

```python
def handle_api_response(response):
    """Handle API response and extract data or error"""
    if response.status_code == 200:
        result = response.json()
        return result[0]["result"]["data"]["json"]
    else:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")

def validate_listing_data(data):
    """Validate listing data before API call"""
    errors = []
    
    if not data.get("title"):
        errors.append("Title is required")
    
    if not data.get("images") or len(data["images"]) == 0:
        errors.append("At least 1 image is required")
    
    if data.get("category") not in ["DIGITAL_GOODS", "CUSTOM"]:
        if not data.get("condition"):
            errors.append("Condition is required for physical products")
    
    if errors:
        raise ValueError("Validation errors: " + "; ".join(errors))
```

---

## Complete Integration Examples

### Python Integration Class

```python
import requests
import os
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass

@dataclass
class Variation:
    name: str
    values: List[str]

@dataclass
class ShippingPrice:
    country_code: str
    price: float
    currency_code: str = "USDT"

class ForestMarketAPI:
    def __init__(self, session_token: str):
        self.session_token = session_token
        self.base_url = "https://forestmarket.net/api/trpc"
        self.headers = {
            "Content-Type": "application/json",
            "trpc-accept": "application/json",
        }
        self.cookies = {
            "__Secure-next-auth.session-token": session_token
        }
    
    def get_presigned_url(self, file_name: str, file_type: str) -> Dict[str, Any]:
        """Get presigned URL for image upload"""
        url = f"{self.base_url}/upload.getPresignedUrl?batch=1"
        
        payload = {
            "0": {
                "json": {
                    "fileName": file_name,
                    "fileType": file_type
                }
            }
        }
        
        response = requests.post(url, json=payload, headers=self.headers, cookies=self.cookies)
        
        if response.status_code == 200:
            result = response.json()
            return result[0]["result"]["data"]["json"]
        else:
            raise Exception(f"Failed to get presigned URL: {response.status_code} - {response.text}")
    
    def upload_image(self, file_path: str) -> str:
        """Upload single image and return URL"""
        file_name = os.path.basename(file_path)
        file_extension = file_name.split('.')[-1].lower()
        
        mime_types = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'
        }
        
        file_type = mime_types.get(file_extension, 'image/jpeg')
        
        # Get presigned URL
        presigned_data = self.get_presigned_url(file_name, file_type)
        
        # Upload to S3
        with open(file_path, 'rb') as file:
            upload_response = requests.put(
                presigned_data["presignedUrl"],
                data=file,
                headers={"Content-Type": file_type}
            )
            
            if upload_response.status_code not in [200, 204]:
                raise Exception(f"Failed to upload image: {upload_response.status_code}")
        
        return presigned_data["objectUrl"]
    
    def upload_images(self, image_paths: List[str]) -> List[str]:
        """Upload multiple images and return URLs"""
        uploaded_urls = []
        
        for image_path in image_paths:
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            url = self.upload_image(image_path)
            uploaded_urls.append(url)
        
        return uploaded_urls
    
    def create_listing(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a product listing"""
        url = f"{self.base_url}/product.uploadListing?batch=1"
        
        # Validate required fields
        required_fields = ["title", "description", "price", "images", "category", "payment_options"]
        for field in required_fields:
            if not listing_data.get(field):
                raise ValueError(f"Required field missing: {field}")
        
        # Build payload
        payload = {
            "0": {
                "json": {
                    "title": listing_data["title"],
                    "description": listing_data["description"],
                    "price": listing_data["price"],
                    "images": listing_data["images"],
                    "currencyCode": listing_data.get("currency_code", "USDT"),
                    "countryCode": listing_data.get("ship_from_country"),
                    "category": listing_data["category"],
                    "paymentOptions": self._build_payment_options(listing_data["payment_options"]),
                    "shipToCountries": listing_data.get("ship_to_countries", []),
                    "shipPrices": self._build_shipping_prices(listing_data.get("shipping_prices", [])),
                    "quantity": listing_data.get("quantity", 1),
                    "variations": self._build_variations(listing_data.get("variations", []))
                }
            }
        }
        
        # Add optional fields
        if listing_data.get("condition"):
            payload["0"]["json"]["condition"] = listing_data["condition"]
        
        if listing_data.get("discount_type") and listing_data.get("discount_value"):
            payload["0"]["json"]["discountType"] = listing_data["discount_type"]
            payload["0"]["json"]["discountValue"] = listing_data["discount_value"]
        
        # Make API call
        response = requests.post(url, json=payload, headers=self.headers, cookies=self.cookies)
        
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
    
    def _build_payment_options(self, payment_options: List[str]) -> List[Dict[str, Any]]:
        """Build payment options for API payload"""
        payment_options_map = {
            "ETH_ETHEREUM": {
                "id": "ethereum", "name": "Ether", "symbol": "ETH", "decimals": 18,
                "chains": [{"contractAddress": None, "id": 1, "name": "Ethereum"}]
            },
            "USDC_BASE": {
                "id": "usd-coin", "name": "USDC", "symbol": "USDC", "decimals": 6,
                "chains": [{"contractAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "id": 8453, "name": "Base"}]
            }
            # Add more payment options as needed
        }
        
        selected_payments = []
        for payment_id in payment_options:
            if payment_id in payment_options_map:
                payment_data = payment_options_map[payment_id]
                existing = next((p for p in selected_payments if p["id"] == payment_data["id"]), None)
                if existing:
                    existing["chains"].extend(payment_data["chains"])
                else:
                    selected_payments.append(payment_data.copy())
        
        return selected_payments
    
    def _build_shipping_prices(self, shipping_prices: List[ShippingPrice]) -> List[Dict[str, Any]]:
        """Build shipping prices for API payload"""
        return [
            {
                "countryCode": sp.country_code,
                "price": sp.price,
                "currencyCode": sp.currency_code
            }
            for sp in shipping_prices
        ]
    
    def _build_variations(self, variations: List[Variation]) -> List[Dict[str, Any]]:
        """Build variations for API payload"""
        return [
            {"name": var.name, "values": var.values}
            for var in variations
        ]

# Usage Example
def main():
    # Initialize API client
    session_token = "your_session_token_here"
    api = ForestMarketAPI(session_token)
    
    # Upload images
    image_paths = ["/path/to/image1.jpg", "/path/to/image2.png"]
    image_urls = api.upload_images(image_paths)
    
    # Create listing
    listing_data = {
        "title": "Wireless Gaming Mouse",
        "description": "High-performance wireless gaming mouse with RGB lighting",
        "price": 50.0,
        "images": image_urls,
        "category": "ELECTRONICS",
        "condition": "NEW",
        "payment_options": ["ETH_ETHEREUM", "USDC_BASE"],
        "ship_from_country": "US",
        "ship_to_countries": ["US", "SG"],
        "quantity": 10,
        "variations": [
            Variation(name="Color", values=["Black", "White", "Red"])
        ],
        "shipping_prices": [
            ShippingPrice(country_code="US", price=0.0),
            ShippingPrice(country_code="SG", price=25.0)
        ]
    }
    
    result = api.create_listing(listing_data)
    print(f"Listing created: {result}")
```

### JavaScript/TypeScript Integration

```typescript
interface ForestMarketAPI {
    sessionToken: string;
    baseUrl: string;
}

interface ListingData {
    title: string;
    description: string;
    price: number;
    images: string[];
    category: string;
    condition?: string;
    paymentOptions: string[];
    shipFromCountry?: string;
    shipToCountries?: string[];
    quantity: number;
    variations?: Variation[];
    shippingPrices?: ShippingPrice[];
}

interface Variation {
    name: string;
    values: string[];
}

interface ShippingPrice {
    countryCode: string;
    price: number;
    currencyCode: string;
}

class ForestMarketClient {
    private sessionToken: string;
    private baseUrl: string;

    constructor(sessionToken: string) {
        this.sessionToken = sessionToken;
        this.baseUrl = "https://forestmarket.net/api/trpc";
    }

    private async makeRequest(endpoint: string, payload: any): Promise<any> {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'trpc-accept': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} - ${response.statusText}`);
        }

        return response.json();
    }

    async getPresignedUrl(fileName: string, fileType: string): Promise<any> {
        const payload = {
            "0": {
                "json": {
                    fileName,
                    fileType
                }
            }
        };

        const result = await this.makeRequest('/upload.getPresignedUrl?batch=1', payload);
        return result[0].result.data.json;
    }

    async uploadImage(file: File): Promise<string> {
        const presignedData = await this.getPresignedUrl(file.name, file.type);
        
        const uploadResponse = await fetch(presignedData.presignedUrl, {
            method: 'PUT',
            headers: {
                'Content-Type': file.type,
            },
            body: file
        });

        if (!uploadResponse.ok) {
            throw new Error('Failed to upload image to S3');
        }

        return presignedData.objectUrl;
    }

    async createListing(listingData: ListingData): Promise<any> {
        const payload = {
            "0": {
                "json": {
                    title: listingData.title,
                    description: listingData.description,
                    price: listingData.price,
                    images: listingData.images,
                    currencyCode: "USDT",
                    countryCode: listingData.shipFromCountry,
                    category: listingData.category,
                    paymentOptions: this.buildPaymentOptions(listingData.paymentOptions),
                    shipToCountries: listingData.shipToCountries || [],
                    shipPrices: this.buildShippingPrices(listingData.shippingPrices || []),
                    quantity: listingData.quantity,
                    variations: this.buildVariations(listingData.variations || [])
                }
            }
        };

        if (listingData.condition) {
            payload[0].json.condition = listingData.condition;
        }

        const result = await this.makeRequest('/product.uploadListing?batch=1', payload);
        return result[0].result.data.json;
    }

    private buildPaymentOptions(paymentOptions: string[]): any[] {
        // Implementation similar to Python version
        return [];
    }

    private buildShippingPrices(shippingPrices: ShippingPrice[]): any[] {
        return shippingPrices.map(sp => ({
            countryCode: sp.countryCode,
            price: sp.price,
            currencyCode: sp.currencyCode
        }));
    }

    private buildVariations(variations: Variation[]): any[] {
        return variations.map(v => ({
            name: v.name,
            values: v.values
        }));
    }
}

// Usage Example
async function createProductListing() {
    const client = new ForestMarketClient('your_session_token');
    
    // Upload images
    const imageFiles = document.querySelectorAll('input[type="file"]');
    const imageUrls = [];
    
    for (const file of imageFiles) {
        const url = await client.uploadImage(file);
        imageUrls.push(url);
    }
    
    // Create listing
    const listingData: ListingData = {
        title: "Wireless Gaming Mouse",
        description: "High-performance wireless gaming mouse with RGB lighting",
        price: 50.0,
        images: imageUrls,
        category: "ELECTRONICS",
        condition: "NEW",
        paymentOptions: ["ETH_ETHEREUM", "USDC_BASE"],
        shipFromCountry: "US",
        shipToCountries: ["US", "SG"],
        quantity: 10,
        variations: [
            { name: "Color", values: ["Black", "White", "Red"] }
        ],
        shippingPrices: [
            { countryCode: "US", price: 0.0, currencyCode: "USDT" },
            { countryCode: "SG", price: 25.0, currencyCode: "USDT" }
        ]
    };
    
    const result = await client.createListing(listingData);
    console.log('Listing created:', result);
}
```

---

## API Endpoints Reference

### Image Upload Endpoints

| Endpoint | Method | Purpose | Parameters |
|----------|--------|---------|------------|
| `/upload.getPresignedUrl?batch=1` | POST | Get presigned URL for S3 upload | `fileName`, `fileType` |

### Product Management Endpoints

| Endpoint | Method | Purpose | Parameters |
|----------|--------|---------|------------|
| `/product.uploadListing?batch=1` | POST | Create new product listing | Full product data |

### Authentication Endpoints

| Endpoint | Method | Purpose | Parameters |
|----------|--------|---------|------------|
| `/auth/signin` | POST | MetaMask authentication | `address`, `signature` |
| `/auth/session` | GET | Get current session | None |

### Response Formats

#### Success Response
```json
{
    "success": true,
    "eid": "listing_id",
    "post_listing": "listing_url",
    "license_key": "license_key",
    "response": {
        "0": {
            "result": {
                "data": {
                    "json": {
                        "eid": "listing_id",
                        "postListing": "listing_url",
                        "licenseKey": "license_key"
                    }
                }
            }
        }
    }
}
```

#### Error Response
```json
{
    "success": false,
    "status_code": 400,
    "error": "Validation failed: At least 1 image is required"
}
```

---

## Best Practices

### 1. Error Handling
- Always check response status codes
- Implement retry logic for transient failures (especially for SSL/network errors)
- Log detailed error information for debugging
- Handle nonce expiration gracefully with fresh authentication flows

### 2. Image Optimization
- Compress images before upload (recommended: < 1MB per image)
- Use appropriate formats (JPEG for photos, PNG for graphics)
- Implement progressive loading for multiple images

### 3. Rate Limiting
- Implement delays between API calls
- Handle rate limit responses gracefully
- Use exponential backoff for retries

### 4. Security
- Never expose session tokens in client-side code
- Never expose Dynamic.xyz environment ID in frontend
- Validate all input data before API calls
- Use HTTPS for all API communications

### 5. Data Validation
- Validate all required fields before API calls
- Check file types and sizes for images
- Ensure payment options are valid

### 6. Session Management (CRITICAL)
- Use single `requests.Session()` object throughout authentication flow
- Never manually manage CSRF cookies - let session handle automatically
- Complete authentication flow (Steps 1-6) within 2-3 minutes to avoid nonce expiration
- Test session tokens with `/api/auth/session` before using for API calls

---

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
**Problem:** 401 Unauthorized errors
**Solution:** 
- Verify session token is valid and properly formatted
- Check if token has expired (tokens are time-limited)
- Re-authenticate with MetaMask using fresh nonce
- Ensure CSRF cookie was preserved during authentication flow

**Problem:** "No session token found in response"
**Root Cause:** Missing CSRF cookie in Step 5 of authentication
**Solution:**
- Use single `requests.Session()` object for entire flow
- Don't create new session between Steps 1 and 5
- Let session automatically manage `__Host-next-auth.csrf-token` cookie

**Problem:** "Invalid signature - did not pass verification"
**Root Cause:** Nonce expiration (nonces are single-use and expire quickly)
**Solution:**
- Generate fresh nonce immediately before signing
- Complete entire authentication flow within 2-3 minutes
- Never reuse signatures from previous attempts

#### 2. Image Upload Failures
**Problem:** S3 upload errors
**Solution:**
- Check file size and format
- Verify presigned URL is not expired
- Ensure proper Content-Type headers

#### 3. Validation Errors
**Problem:** 400 Bad Request errors
**Solution:**
- Check all required fields are present
- Validate data types and formats
- Ensure business rules are followed

#### 4. Network Errors
**Problem:** Connection timeouts, SSL errors
**Solution:**
- Implement retry logic with exponential backoff (2-3 retries)
- Handle `SSLEOFError` and similar network exceptions
- Use appropriate timeouts (10-15 seconds)
- Check network connectivity

---

This documentation provides a complete reference for integrating with Forest Market's API. Use this as a guide for building your own applications and tools that interact with the Forest Market platform.

## Proven Test Suite

A complete, working test suite that demonstrates the authentication flow is available in the `test-fm-login` directory:

- **`test_full_login_flow.py`**: Complete authentication test with session token extraction
- **`signer.html`**: Browser-based MetaMask signing tool
- **`README.md`**: Instructions for using the test suite

This test suite has been **verified to work** and successfully extracts valid Forest Market session tokens. Use it as a reference implementation for your own integration. 