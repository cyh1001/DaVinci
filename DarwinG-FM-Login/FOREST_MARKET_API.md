# Forest Market API Documentation

## Overview
Forest Market is a crypto-based e-commerce platform that uses tRPC API with **Dynamic.xyz** for MetaMask authentication. Forest Market outsources wallet authentication to Dynamic's secure infrastructure.

## Authentication Architecture

Forest Market uses a **three-party authentication system** with **Dynamic.xyz** as the authentication provider:
1. **Your Application** ↔ **Forest Market API** (for product listings, etc.)
2. **Your Application** ↔ **Dynamic.xyz API** (for wallet authentication)
3. **Dynamic.xyz** ↔ **Forest Market** (JWT validation)

**CRITICAL:** Forest Market authentication **requires proper session cookie management** to successfully retrieve the final `__Secure-next-auth.session-token`. This is why a backend proxy server is essential for integration.

### Complete Authentication Flow

#### Step 1: Get CSRF Token from Forest Market
```python
GET https://forestmarket.net/api/auth/csrf

Response:
{
    "csrfToken": "96f6af953dd7af2e95bcf855be1a34559f53dd64e86ebf1ff53b1ee4940623ae"
}

# IMPORTANT: This call also sets an invisible HttpOnly cookie:
# __Host-next-auth.csrf-token={csrf_cookie_value}
# Your session MUST preserve this cookie for Step 5 to succeed!
```

#### Step 2: Get Nonce from Dynamic
```python
GET https://app.dynamicauth.com/api/v0/sdk/02e5c99f-a7aa-4841-b64a-df128fa8e08f/nonce

Headers:
{
    "Content-Type": "application/json",
    "Origin": "https://forestmarket.net"
}

Response:
{
    "nonce": "42d19a8fd4f849xxxxxxxxxxxxxx"
}
```

#### Step 3: User Signs Message (Frontend)
```javascript
// Message format that user must sign
const messageToSign = `forestmarket.net wants you to sign in with your Ethereum account:
${walletAddress}

Welcome to Forest Market. Signing is the only way we can truly know that you are the owner of the wallet you are connecting. Signing is a safe, gas-less transaction that does not in any way give Forest Market permission to perform any transactions with your wallet.

URI: https://forestmarket.net/en-HK
Version: 1
Chain ID: 1
Nonce: ${nonce}
Issued At: ${new Date().toISOString()}
Request ID: 02e5c99f-a7aa-4841-b64a-df128fa8e08f`;

// User signs with MetaMask
const signature = await ethereum.request({
    method: 'personal_sign',
    params: [messageToSign, walletAddress]
});
```

#### Step 4: Verify Signature with Dynamic
```python
POST https://app.dynamicauth.com/api/v0/sdk/02e5c99f-a7aa-4841-b64a-df128fa8e08f/verify

Headers:
{
    "Content-Type": "application/json",
    "Origin": "https://forestmarket.net"
}

Payload:
{
    "signedMessage": "0x6ce911e69fa06ac3fab24845977a75493a66cd98ea542d811bafd810be8d59b25d495a1014c9d61efcf2a511dccfeb9591ac6614e9b1fc400c30b2a1999531b71c",
    "messageToSign": "forestmarket.net wants you to sign in with your Ethereum account...",
    "publicWalletAddress": "0x63A3020AcE23d32C5dE5f7009fA8e35e1D9F45c3",
    "chain": "EVM",
    "walletName": "metamask",
    "walletProvider": "browserExtension",
    "network": "1",
    "additionalWalletAddresses": []
}

Response:
{
    "jwt": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIs...",
    "user": { ... },
    "expiresAt": 1756551804
}
```

#### Step 5: Exchange JWT for Forest Market Session
```python
POST https://forestmarket.net/api/auth/callback/Dynamic

Headers:
{
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://forestmarket.net",
    # CRITICAL: Must include CSRF cookie from Step 1
    "Cookie": "__Host-next-auth.csrf-token={csrf_cookie_from_step1}"
}

Payload (URL-encoded):
token={jwt_from_dynamic}&redirect=false&callbackUrl=https%3A%2F%2Fforestmarket.net%2Fen-HK&csrfToken={csrf_token}&json=true

Response Headers:
Set-Cookie: __Secure-next-auth.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0...; Path=/; HttpOnly; Secure

Response Body:
{
    "url": "https://forestmarket.net/en-HK"
}

# SUCCESS: Extract session token from Set-Cookie header
# This is the token you need for all subsequent API calls!
```

#### Step 6: Verify Session
```python
GET https://forestmarket.net/api/auth/session

Headers:
{
    "Cookie": "__Secure-next-auth.session-token={session_token}"
}

Response:
{
    "user": {
        "id": "688b72e3d9b25381443fef67",
        "role": "DEFAULT",
        "publicAddress": null
    },
    "expires": "2025-08-29T11:03:26.643Z"
}
```

### Authentication Constants
```python
# Dynamic.xyz Environment ID (Forest Market's)
DYNAMIC_ENVIRONMENT_ID = "02e5c99f-a7aa-4841-b64a-df128fa8e08f"

# Session token format
session_token = "__Secure-next-auth.session-token"

# Headers for authenticated API calls
headers = {
    "Content-Type": "application/json",
    "trpc-accept": "application/json",
}

# Cookies for authentication
cookies = {
    "__Secure-next-auth.session-token": session_token
}
```

## API Endpoints

### 1. Image Upload Flow

#### Get Presigned URL
```python
POST https://forestmarket.net/api/trpc/upload.getPresignedUrl?batch=1

Payload:
{
    "0": {
        "json": {
            "fileName": "image.jpg",
            "fileType": "image/jpeg"
        }
    }
}

Response:
{
    "presignedUrl": "https://s3.amazonaws.com/...",
    "objectUrl": "https://forestmarket.s3.amazonaws.com/images/image.jpg",
    "fileType": "image/jpeg"
}
```

#### Upload to S3
```python
PUT {presignedUrl}
Headers: {"Content-Type": "image/jpeg"}
Body: File binary data
```

### 2. Create Product Listing
```python
POST https://forestmarket.net/api/trpc/product.uploadListing?batch=1

Payload:
{
    "0": {
        "json": {
            "title": "Product Title",
            "description": "Product description",
            "price": 50.0,
            "images": ["https://forestmarket.s3.amazonaws.com/images/image1.jpg"],
            "currencyCode": "USDT",
            "countryCode": "US",
            "category": "ELECTRONICS",
            "paymentOptions": [
                {
                    "id": "ethereum",
                    "name": "Ether",
                    "symbol": "ETH",
                    "decimals": 18,
                    "chains": [{"contractAddress": None, "id": 1, "name": "Ethereum"}]
                }
            ],
            "shipToCountries": ["US", "SG"],
            "shipPrices": [
                {"countryCode": "US", "price": 0.0, "currencyCode": "USDT"},
                {"countryCode": "SG", "price": 25.0, "currencyCode": "USDT"}
            ],
            "quantity": 10,
            "variations": [
                {"name": "Size", "values": ["S", "M", "L"]}
            ],
            "condition": "NEW"
        }
    }
}
```

## Data Structures

### Payment Options
```python
payment_options_map = {
    "ETH_ETHEREUM": {
        "id": "ethereum", "name": "Ether", "symbol": "ETH", "decimals": 18,
        "chains": [{"contractAddress": None, "id": 1, "name": "Ethereum"}]
    },
    "ETH_BASE": {
        "id": "ethereum", "name": "Ether", "symbol": "ETH", "decimals": 18,
        "chains": [{"id": 8453, "contractAddress": None, "name": "Base"}]
    },
    "SOL_SOLANA": {
        "id": "solana", "name": "Solana", "symbol": "SOL", "decimals": 9,
        "chains": [{"contractAddress": None, "id": 0, "name": "Solana"}]
    },
    "USDC_ETHEREUM": {
        "id": "usd-coin", "name": "USDC", "symbol": "USDC", "decimals": 6,
        "chains": [{"contractAddress": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "id": 1, "name": "Ethereum"}]
    },
    "USDC_BASE": {
        "id": "usd-coin", "name": "USDC", "symbol": "USDC", "decimals": 6,
        "chains": [{"contractAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "id": 8453, "name": "Base"}]
    },
    "USDC_SOLANA": {
        "id": "usd-coin", "name": "USDC", "symbol": "USDC", "decimals": 6,
        "chains": [{"contractAddress": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "id": 0, "name": "Solana"}]
    },
    "USDT_ETHEREUM": {
        "id": "tether", "name": "Tether", "symbol": "USDT", "decimals": 6,
        "chains": [{"contractAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7", "id": 1, "name": "Ethereum"}]
    }
}
```

### Categories
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

## Validation Rules

### Images
- **Minimum:** 1 image required
- **Formats:** JPG, JPEG, PNG, GIF, WebP
- **Size:** Recommended < 10MB per image

### Shipping
- **DIGITAL_GOODS:** No shipping required
- **Physical products:** ship_from_country and ship_to_countries required
- **Maximum:** 5 ship-to countries

### Discounts
- **PERCENTAGE:** 0.1-0.5 (10%-50%)
- **FIXED_AMOUNT:** Positive value

### Product Condition
- **Required for:** Physical products (except DIGITAL_GOODS, CUSTOM)
- **Values:** "NEW" or "USED"

## Complete Proxy Server Implementation

```python
import requests
import urllib.parse
from typing import Dict, Any, Optional
from datetime import datetime

class ForestMarketProxyAuth:
    def __init__(self):
        self.dynamic_base_url = "https://app.dynamicauth.com/api/v0/sdk"
        self.dynamic_environment_id = "02e5c99f-a7aa-4841-b64a-df128fa8e08f"
        self.forest_market_base_url = "https://forestmarket.net"
        # CRITICAL: Use single session to preserve cookies throughout the flow
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })
        
    def get_csrf_token(self) -> str:
        """Step 1: Get CSRF token from Forest Market and store CSRF cookie"""
        url = f"{self.forest_market_base_url}/api/auth/csrf"
        response = self.session.get(url)
        
        if response.status_code == 200:
            # The session automatically stores the __Host-next-auth.csrf-token cookie
            return response.json()["csrfToken"]
        else:
            raise Exception(f"Failed to get CSRF token: {response.status_code}")
    
    def get_nonce(self) -> str:
        """Step 2: Get nonce from Dynamic"""
        url = f"{self.dynamic_base_url}/{self.dynamic_environment_id}/nonce"
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://forestmarket.net"
        }
        
        response = self.session.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()["nonce"]
        else:
            raise Exception(f"Failed to get nonce: {response.status_code}")
    
    def create_sign_message(self, wallet_address: str, nonce: str) -> str:
        """Step 3: Create the message format for user to sign"""
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        message = f"""forestmarket.net wants you to sign in with your Ethereum account:
{wallet_address}

Welcome to Forest Market. Signing is the only way we can truly know that you are the owner of the wallet you are connecting. Signing is a safe, gas-less transaction that does not in any way give Forest Market permission to perform any transactions with your wallet.

URI: https://forestmarket.net/en-HK
Version: 1
Chain ID: 1
Nonce: {nonce}
Issued At: {timestamp}
Request ID: {self.dynamic_environment_id}"""
        
        return message
    
    def verify_signature(self, wallet_address: str, message: str, signature: str) -> Dict[str, Any]:
        """Step 4: Verify signature with Dynamic and get JWT"""
        url = f"{self.dynamic_base_url}/{self.dynamic_environment_id}/verify"
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://forestmarket.net"
        }
        
        payload = {
            "signedMessage": signature,
            "messageToSign": message,
            "publicWalletAddress": wallet_address,
            "chain": "EVM",
            "walletName": "metamask",
            "walletProvider": "browserExtension",
            "network": "1",
            "additionalWalletAddresses": []
        }
        
        response = self.session.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to verify signature: {response.status_code} - {response.text}")
    
    def exchange_jwt_for_session(self, jwt_token: str, csrf_token: str) -> str:
        """Step 5: Exchange JWT for Forest Market session token using stored CSRF cookie"""
        url = f"{self.forest_market_base_url}/api/auth/callback/Dynamic"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://forestmarket.net"
        }
        # The session automatically includes the __Host-next-auth.csrf-token cookie
        
        # URL-encode the payload
        payload_data = {
            "token": jwt_token,
            "redirect": "false",
            "callbackUrl": "https://forestmarket.net/en-HK",
            "csrfToken": csrf_token,
            "json": "true"
        }
        payload = urllib.parse.urlencode(payload_data)
        
        response = self.session.post(url, data=payload, headers=headers)
        
        if response.status_code == 200:
            # Extract session token from Set-Cookie header
            set_cookie = response.headers.get("Set-Cookie", "")
            if "__Secure-next-auth.session-token=" in set_cookie:
                # Parse the session token from Set-Cookie header
                start = set_cookie.find("__Secure-next-auth.session-token=") + len("__Secure-next-auth.session-token=")
                end = set_cookie.find(";", start)
                session_token = set_cookie[start:end if end != -1 else None]
                return session_token
            else:
                raise Exception("No session token found in response - CSRF cookie may be missing")
        else:
            raise Exception(f"Failed to exchange JWT: {response.status_code} - {response.text}")
    
    def verify_session(self, session_token: str) -> Dict[str, Any]:
        """Step 6: Verify the session token works"""
        url = f"{self.forest_market_base_url}/api/auth/session"
        headers = {
            "Cookie": f"__Secure-next-auth.session-token={session_token}"
        }
        
        response = self.session.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to verify session: {response.status_code}")
    
    def complete_login_flow(self, wallet_address: str, signature: str) -> Dict[str, Any]:
        """Complete login flow - call this from your proxy endpoint"""
        try:
            # Step 1: Get CSRF token
            csrf_token = self.get_csrf_token()
            
            # Step 2: Get nonce
            nonce = self.get_nonce()
            
            # Step 3: Create message (return to frontend for signing)
            message = self.create_sign_message(wallet_address, nonce)
            
            # Note: Steps 4-6 would be called after user signs the message
            # This is split because the user needs to sign the message in the frontend
            
            return {
                "success": True,
                "message_to_sign": message,
                "nonce": nonce,
                "csrf_token": csrf_token
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def complete_verification_flow(self, wallet_address: str, message: str, signature: str, csrf_token: str) -> Dict[str, Any]:
        """Complete verification after user signs message"""
        try:
            # Step 4: Verify signature with Dynamic
            jwt_response = self.verify_signature(wallet_address, message, signature)
            jwt_token = jwt_response["jwt"]
            
            # Step 5: Exchange JWT for Forest Market session
            session_token = self.exchange_jwt_for_session(jwt_token, csrf_token)
            
            # Step 6: Verify session works
            session_info = self.verify_session(session_token)
            
            return {
                "success": True,
                "session_token": session_token,
                "user_info": session_info,
                "jwt_info": jwt_response
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Usage Example for FastAPI/Flask
def create_forest_market_proxy_endpoints():
    auth = ForestMarketProxyAuth()
    
    # Endpoint 1: Start login process
    @app.post("/my-api/start-login")
    def start_login(wallet_address: str):
        return auth.complete_login_flow(wallet_address, None)
    
    # Endpoint 2: Complete login after signature
    @app.post("/my-api/complete-login")
    def complete_login(wallet_address: str, message: str, signature: str, csrf_token: str):
        result = auth.complete_verification_flow(wallet_address, message, signature, csrf_token)
        
        if result["success"]:
            # Store session_token securely (database, cache, etc.)
            store_user_session(wallet_address, result["session_token"])
        
        return result

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
    
    def create_listing(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a product listing"""
        url = f"{self.base_url}/product.uploadListing?batch=1"
        
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
                    "variations": listing_data.get("variations", [])
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
    
    def _build_shipping_prices(self, shipping_prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build shipping prices for API payload"""
        return [
            {
                "countryCode": sp["country_code"],
                "price": sp["price"],
                "currencyCode": sp.get("currency_code", "USDT")
            }
            for sp in shipping_prices
        ]

# Usage Example
def main():
    # Initialize API client
    session_token = "your_session_token_here"
    api = ForestMarketAPI(session_token)
    
    # Upload images
    image_paths = ["/path/to/image1.jpg", "/path/to/image2.png"]
    image_urls = []
    
    for image_path in image_paths:
        url = api.upload_image(image_path)
        image_urls.append(url)
    
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
            {"name": "Color", "values": ["Black", "White", "Red"]}
        ],
        "shipping_prices": [
            {"country_code": "US", "price": 0.0, "currency_code": "USDT"},
            {"country_code": "SG", "price": 25.0, "currency_code": "USDT"}
        ]
    }
    
    result = api.create_listing(listing_data)
    print(f"Listing created: {result}")

if __name__ == "__main__":
    main()
```

## Error Handling

### Common Error Responses
```json
// Authentication Error
{
    "success": false,
    "error": "Authentication failed",
    "status_code": 401
}

// Validation Error
{
    "success": false,
    "error": "Validation failed: At least 1 image is required",
    "status_code": 400
}

// Success Response
{
    "success": true,
    "eid": "listing_id",
    "post_listing": "listing_url",
    "license_key": "license_key"
}
```

## Best Practices

1. **Error Handling**: Always check response status codes and implement retry logic for network issues
2. **Image Optimization**: Compress images before upload
3. **Rate Limiting**: Implement delays between API calls
4. **Security**: Never expose session tokens in client-side code
5. **Validation**: Validate all input data before API calls
6. **Session Management**: Use a single requests.Session() throughout the entire authentication flow
7. **Cookie Preservation**: Never manually manage CSRF cookies - let the session handle them automatically

## Critical Troubleshooting

### Authentication Failures

#### Problem: "No session token found in response"
**Root Cause:** Missing CSRF cookie from Step 1
**Solution:** 
- Ensure you use the same `requests.Session()` object for Steps 1 and 5
- Never create new session objects between CSRF token retrieval and JWT exchange
- The session automatically manages the invisible `__Host-next-auth.csrf-token` cookie

#### Problem: "Invalid signature - did not pass verification" 
**Root Cause:** Nonce expiration (nonces are single-use and expire quickly)
**Solution:**
- Generate fresh nonce immediately before signing
- Complete the entire flow (Steps 1-6) within ~2-3 minutes
- Never reuse signatures from previous login attempts

#### Problem: SSL/Network errors during authentication
**Root Cause:** Temporary network instability
**Solution:**
- Implement retry logic with exponential backoff (2-3 retries)
- Add appropriate timeouts (10-15 seconds)
- Handle `SSLEOFError` and similar network exceptions gracefully

### Session Token Verification

#### Problem: Session token not working for API calls
**Symptom:** 401 Unauthorized on authenticated endpoints
**Solution:**
- Verify token format: `__Secure-next-auth.session-token=eyJhbGciOiJka...`
- Test with `/api/auth/session` endpoint first
- Check token extraction logic from Set-Cookie header

## Summary: Building Your Custom Open WebUI with Forest Market Integration

### Architecture Overview
Your custom Open WebUI will need:

1. **Frontend (React/Next.js)**: Handles MetaMask connection and user interface
2. **Backend Proxy (FastAPI/Flask)**: Orchestrates authentication with Dynamic.xyz and Forest Market
3. **Forest Market API**: Product listing and e-commerce functionality

### Key Implementation Steps

1. **Set up the proxy server** using the `ForestMarketProxyAuth` class above
2. **Implement two main endpoints**:
   - `POST /my-api/start-login` - Initiates login flow, returns message to sign
   - `POST /my-api/complete-login` - Completes login after user signs message
3. **Store session tokens securely** in your backend (database, Redis, etc.)
4. **Proxy all Forest Market API calls** through your backend using stored session tokens

### Critical Security Notes

- **Never expose Dynamic.xyz environment ID** in frontend code (already done in documentation)
- **Always validate signatures server-side** before making API calls
- **Store session tokens securely** and associate them with users
- **Implement session expiration** and refresh mechanisms

### Testing Your Implementation

1. **Start with our proven test script**: Use the `test_full_login_flow.py` in the `test-fm-login` directory
2. **Test the complete flow**: CSRF token → nonce → message signing → verification → session creation
3. **Verify session tokens**: Test with `/api/auth/session` and then with product listing endpoints
4. **Use developer tools**: Compare your proxy's network calls with real Forest Market site behavior

### Proven Implementation Path

1. **Use our test suite** (`test-fm-login/test_full_login_flow.py`) to verify the authentication flow works
2. **Extract the working session token** and save it for API testing
3. **Build your proxy server** using the `ForestMarketProxyAuth` class above as a foundation
4. **Implement frontend** to handle MetaMask connection and signature requests
5. **Test product listing** using the extracted session token

This documentation provides the complete, **tested and verified** technical blueprint for integrating Forest Market's authentication and API system into your custom Open WebUI. The authentication methodology has been proven to work and successfully extract valid session tokens. 

```sequenceDiagram
    participant WebUI Frontend
    participant WebUI Backend (Proxy)
    participant Dynamic.co API
    participant Forest Market API
    participant MetaMask

    Note over WebUI Frontend, Forest Market API: The Complete & Accurate Login Flow
    WebUI Frontend->>WebUI Backend (Proxy): 1. User wants to log in

    WebUI Backend (Proxy)->>Forest Market API: 2. GET /api/auth/csrf
    Forest Market API-->>WebUI Backend (Proxy): 3. Returns csrfToken

    WebUI Backend (Proxy)->>Dynamic.co API: 4. GET /nonce
    Dynamic.co API-->>WebUI Backend (Proxy): 5. Returns nonce

    WebUI Backend (Proxy)-->>WebUI Frontend: 6. Sends nonce to frontend

    WebUI Frontend->>MetaMask: 7. Asks user to sign message with nonce
    MetaMask-->>WebUI Frontend: 8. Returns signature

    WebUI Frontend->>WebUI Backend (Proxy): 9. Sends signature back

    WebUI Backend (Proxy)->>Dynamic.co API: 10. POST /verify with signature
    Dynamic.co API-->>WebUI Backend (Proxy): 11. Returns a JWT (Proof of Auth)

    WebUI Backend (Proxy)->>Forest Market API: 12. POST /api/auth/callback/Dynamic <br/>(Payload: JWT from Dynamic + CSRF Token)
    Forest Market API-->>WebUI Backend (Proxy): 13. SUCCESS! Returns the final <br/> __Secure-next-auth.session-token

    WebUI Backend (Proxy)->>WebUI Backend (Proxy): 14. Securely stores the Forest Market session token
    WebUI Backend (Proxy)-->>WebUI Frontend: 15. Confirms login is complete
```