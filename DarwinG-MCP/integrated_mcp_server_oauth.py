#!/usr/bin/env python3
"""
Integrated MCP Server for Forest Market Draft Management and Product Listing Upload

This MCP server combines two previously separate tools:
1. Draft management tools (create, read, update, delete drafts)
2. Product listing upload tool (upload images and create listings)

This provides a complete workflow in a single MCP server.
"""

import os
import json
import requests
import tempfile
import urllib.parse
from typing import List, Dict, Optional, Annotated, Literal, Any
from fastmcp import FastMCP
from pydantic import Field, BaseModel
from dataclasses import dataclass
import openai
from dotenv import load_dotenv

# Load environment variables
# load_dotenv("../.env")

# Data classes for variations and shipping
class VariationData(BaseModel):
    name: str
    values: List[str]

class ShippingPriceData(BaseModel):
    country_code: str
    price: float
    currency_code: str = "USDT"

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

# Import models and storage
try:
    from .models import ProductDraft
    from .storage import DraftStorage
except ImportError:
    from models import ProductDraft
    from storage import DraftStorage

# Initialize storage
storage = DraftStorage()

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

def download_image_from_url(url: str) -> str:
    """Download image from URL and save to temporary file, return local path"""
    try:
        # Parse URL to get filename
        parsed_url = urllib.parse.urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        # If no filename in URL, generate one
        if not filename or '.' not in filename:
            filename = f"downloaded_image_{hash(url) % 10000}.jpg"
        
        # Create temporary file with proper extension
        temp_dir = "/tmp"
        temp_path = os.path.join(temp_dir, filename)
        
        # Download the image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Save to temporary file
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded image from {url} to {temp_path}")
        return temp_path
        
    except Exception as e:
        print(f"Failed to download image from {url}: {e}")
        raise Exception(f"Failed to download image from URL: {url}")

def is_url(path: str) -> bool:
    """Check if a string is a URL"""
    return path.startswith(('http://', 'https://'))

def is_user_confirmed(confirmation_value: Any) -> bool:
    """Check if user confirmation is true, handling various input types"""
    if isinstance(confirmation_value, bool):
        return confirmation_value
    
    if isinstance(confirmation_value, str):
        lower_val = confirmation_value.lower().strip()
        return lower_val in ['true', 'yes', '1', 'confirm', 'confirmed', 'ok', 'proceed']
    
    if isinstance(confirmation_value, (int, float)):
        return confirmation_value > 0
    
    return False

def _extract_schema_from_function(func) -> dict:
    """Extract parameter schema from function annotations and Field descriptions"""
    import inspect
    from typing import get_type_hints
    
    # If it's a FastMCP FunctionTool, get the underlying function
    if hasattr(func, 'fn'):
        func = func.fn
    
    schema = {"properties": {}}
    
    # Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)
    
    for param_name, param in sig.parameters.items():
        if param_name in type_hints:
            param_type = type_hints[param_name]
            
            # Extract Field description from Annotated types
            description = ""
            if hasattr(param_type, '__metadata__'):
                for metadata in param_type.__metadata__:
                    if hasattr(metadata, 'description'):
                        description = metadata.description
                        break
            
            schema["properties"][param_name] = {"description": description}
    
    return schema

def _parse_natural_language_with_ai(user_input: str, tool_schema: dict, user_id: str = "ai_user") -> Dict[str, Any]:
    """Use AI to parse natural language input into structured tool parameters"""
    
    if not openai_client:
        # Fallback if no OpenAI API key
        return {
            "user_id": user_id,
            "title": "Product from natural language",
            "description": user_input,
            "price": 10.0,
            "category": "OTHER"
        }
    
    # Extract parameter descriptions from tool schema
    parameter_info = ""
    if 'properties' in tool_schema:
        parameter_info = "\nPARAMETER DESCRIPTIONS:\n"
        for param_name, param_data in tool_schema['properties'].items():
            if 'description' in param_data:
                parameter_info += f"- {param_name}: {param_data['description']}\n"
    
    system_prompt = f"""You are an AI assistant that converts natural language product descriptions into structured data for e-commerce tools.

TOOL SCHEMA INFORMATION:
{parameter_info}

Your task: Extract relevant information from the user's natural language input and format it according to the parameter requirements.

CRITICAL INSTRUCTIONS:
1. Extract information exactly as described in each field's description
2. For variations_data: Use format [{{"name": "Size", "values": ["S", "M", "L"]}}]
3. For shipping_prices_data: Use format [{{"country_code": "US", "price": 0.0, "currency_code": "USDT"}}]
4. For price: Extract numeric values (e.g., "$99.99" becomes 99.99)
5. For category: Map to exact values (ELECTRONICS, FASHION, DIGITAL_GOODS, etc.)
6. For payment_options: Use exact values like ["ETH_ETHEREUM", "USDC_BASE"]
7. Always include user_id field
8. If information is missing, use reasonable defaults

Return ONLY a valid JSON object with the extracted parameters."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse this product description: {user_input}"}
            ],
            temperature=0,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Clean up formatting
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        parsed_params = json.loads(content)
        
        # Ensure user_id is set
        parsed_params["user_id"] = user_id
        
        return parsed_params
        
    except Exception as e:
        print(f"AI parsing failed: {e}")
        # Fallback parameters
        return {
            "user_id": user_id,
            "title": "Product from natural language",
            "description": user_input,
            "price": 10.0,
            "category": "OTHER",
            "condition": "NEW",
            "quantity": 1,
            "payment_options": ["ETH_ETHEREUM"]
        }

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

# Upload functionality from mcp_product_listing.py
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


# OAuth 2.1 authentication implementation
import jwt
import time
import secrets
import hashlib
import base64
from urllib.parse import urlencode, parse_qs
from typing import Dict, Optional, List, Tuple
from fastmcp.server.auth import OAuthProvider

class OAuth21Provider(OAuthProvider):
    """OAuth 2.1 Authentication Provider for MCP Server
    
    Implements OAuth 2.1 with security best practices:
    - PKCE (Proof Key for Code Exchange) required for all clients
    - Short-lived access tokens with refresh token rotation
    - JWT tokens with proper validation
    - Secure token storage and management
    """
    
    def __init__(self):
        # OAuth 2.1 Configuration
        self.client_id = os.getenv("OAUTH_CLIENT_ID", "darwing-mcp-server")
        self.client_secret = os.getenv("OAUTH_CLIENT_SECRET", secrets.token_urlsafe(32))
        self.jwt_secret = os.getenv("JWT_SECRET", secrets.token_urlsafe(64))
        self.access_token_expiry = int(os.getenv("ACCESS_TOKEN_EXPIRY_SECONDS", "900"))  # 15 minutes (OAuth 2.1 recommendation)
        self.refresh_token_expiry = int(os.getenv("REFRESH_TOKEN_EXPIRY_SECONDS", "86400"))  # 24 hours
        self.authorization_code_expiry = 600  # 10 minutes (OAuth 2.1 requirement: ≤ 10 minutes)
        self.required_scopes = ["read"]  # Default required scopes for FastMCP compatibility
        
        # FastMCP OAuthProvider interface requirements
        self.issuer_url = os.getenv("OAUTH_ISSUER_URL", "https://darwing-mcp.onrender.com")
        self.auth_url = f"{self.issuer_url}/oauth/authorize"
        self.token_url = f"{self.issuer_url}/oauth/token"
        self.userinfo_url = f"{self.issuer_url}/oauth/userinfo"
        self.jwks_url = f"{self.issuer_url}/oauth/jwks"
        
        # In-memory storage (use Redis/DB in production)
        self.authorization_codes: Dict[str, Dict] = {}
        self.access_tokens: Dict[str, Dict] = {}
        self.refresh_tokens: Dict[str, Dict] = {}
        self.registered_clients: Dict[str, Dict] = {}
        self.pkce_challenges: Dict[str, Dict] = {}
        self.users: Dict[str, Dict] = {}  # User database
        self.auth_sessions: Dict[str, Dict] = {}  # Temporary auth sessions
        
        # Register default client and users
        self._register_default_client()
        self._register_default_users()
        
        print(f"OAuth 2.1 Provider initialized:")
        print(f"  - Client ID: {self.client_id}")
        print(f"  - Access token expiry: {self.access_token_expiry}s")
        print(f"  - Refresh token expiry: {self.refresh_token_expiry}s")
    
    def _register_default_client(self):
        """Register the default client for OAuth 2.1"""
        self.registered_clients[self.client_id] = {
            "client_secret": self.client_secret,
            "client_type": "confidential",  # Can be "public" for PKCE-only clients
            "redirect_uris": [
                "http://localhost:3000/auth/callback",
                "https://cursor.com/auth/callback",
                "https://your-frontend.com/auth/callback",
                "https://darwing-mcp.onrender.com/auth/callback",
                "https://darwing-mcp.onrender.com/oauth/callback",
                "https://darwing-mcp.onrender.com/register/",
                "urn:ietf:wg:oauth:2.0:oob"  # For CLI/desktop apps
            ],
            "scopes": ["read", "write", "admin"],
            "grant_types": ["authorization_code", "refresh_token", "client_credentials"],
            "require_pkce": True  # OAuth 2.1 recommends PKCE for all clients
        }
    
    def _register_default_users(self):
        """Register default users for demonstration"""
        # Demo users (in production, use proper password hashing)
        default_users = [
            {
                "username": "demo",
                "password": "password123",  # Use bcrypt in production
                "email": "demo@darwing-mcp.com",
                "name": "Demo User",
                "scopes": ["read", "write"]
            },
            {
                "username": "admin", 
                "password": "admin123",
                "email": "admin@darwing-mcp.com",
                "name": "Admin User",
                "scopes": ["read", "write", "admin"]
            }
        ]
        
        for user in default_users:
            # In production, hash passwords with bcrypt
            user_id = user["username"]
            self.users[user_id] = {
                "user_id": user_id,
                "username": user["username"],
                "password": user["password"],  # Hash this!
                "email": user["email"],
                "name": user["name"],
                "scopes": user["scopes"],
                "created_at": time.time()
            }
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user with username/password"""
        user = self.users.get(username)
        if user and user["password"] == password:  # Use bcrypt.checkpw in production
            return {
                "user_id": user["user_id"],
                "username": user["username"],
                "email": user["email"],
                "name": user["name"],
                "scopes": user["scopes"]
            }
        return None
    
    def get_routes(self):
        """Return OAuth routes for FastMCP compatibility"""
        from fastapi import APIRouter
        router = APIRouter()
        
        # Add OAuth discovery endpoint
        @router.get("/.well-known/oauth-authorization-server")
        async def oauth_discovery():
            return {
                "issuer": self.issuer_url,
                "authorization_endpoint": self.auth_url,
                "token_endpoint": self.token_url,
                "userinfo_endpoint": self.userinfo_url,
                "jwks_uri": self.jwks_url,
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
                "code_challenge_methods_supported": ["S256"],
                "scopes_supported": ["read", "write", "admin"]
            }
        
        return router
    
    def _generate_code_challenge(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        # OAuth 2.1 requires PKCE for all authorization code flows
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        return code_verifier, code_challenge
    
    def _verify_code_challenge(self, code_verifier: str, code_challenge: str) -> bool:
        """Verify PKCE code challenge"""
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        return secrets.compare_digest(expected_challenge, code_challenge)
    
    def generate_authorization_code(self, client_id: str, redirect_uri: str, scope: str, 
                                  code_challenge: str, code_challenge_method: str = "S256",
                                  user_id: str = "default_user") -> str:
        """Generate an authorization code for OAuth 2.1 flow with PKCE"""
        if code_challenge_method != "S256":
            raise ValueError("OAuth 2.1 requires S256 code challenge method")
        
        code = secrets.token_urlsafe(32)
        
        self.authorization_codes[code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "user_id": user_id,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "expires_at": time.time() + self.authorization_code_expiry,
            "used": False
        }
        
        return code
    
    def _generate_jwt_token(self, payload: Dict) -> str:
        """Generate a JWT token with OAuth 2.1 best practices"""
        payload.update({
            "iat": int(time.time()),
            "jti": secrets.token_urlsafe(16),  # JWT ID for token tracking
            "iss": "darwing-mcp-server",  # Issuer
        })
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
    
    def _verify_jwt_token(self, token: str) -> Optional[Dict]:
        """Verify and decode a JWT token"""
        try:
            # Decode JWT without audience verification first, then verify manually
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=["HS256"],
                options={"verify_aud": False}  # We'll verify audience manually
            )
            
            # Check if token is expired
            if payload.get("exp", 0) < time.time():
                return None
            
            # Verify audience if present
            if "aud" in payload and payload["aud"] != "darwing-mcp-server":
                return None
                
            return payload
        except jwt.InvalidTokenError:
            return None
    
    def exchange_code_for_token(self, code: str, client_id: str, client_secret: str, 
                              redirect_uri: str, code_verifier: str) -> Optional[Dict]:
        """Exchange authorization code for access token (OAuth 2.1 with PKCE)"""
        # Verify authorization code exists and is valid
        if code not in self.authorization_codes:
            return None
            
        auth_code_data = self.authorization_codes[code]
        
        # Check if code is expired or already used
        if auth_code_data["expires_at"] < time.time() or auth_code_data["used"]:
            # Clean up expired/used codes
            if code in self.authorization_codes:
                del self.authorization_codes[code]
            return None
        
        # Verify client credentials and redirect URI
        client_data = self.registered_clients.get(client_id)
        if not client_data:
            return None
            
        if (auth_code_data["client_id"] != client_id or
            auth_code_data["redirect_uri"] != redirect_uri):
            return None
        
        # For confidential clients, verify client secret
        if client_data["client_type"] == "confidential":
            if client_data["client_secret"] != client_secret:
                return None
        
        # Verify PKCE code challenge (required in OAuth 2.1)
        if not self._verify_code_challenge(code_verifier, auth_code_data["code_challenge"]):
            return None
        
        # Mark code as used and remove it (one-time use)
        auth_code_data["used"] = True
        del self.authorization_codes[code]
        
        # Generate tokens with shorter expiry (OAuth 2.1 best practice)
        access_token_payload = {
            "sub": auth_code_data["user_id"],
            "client_id": client_id,
            "scope": auth_code_data["scope"],
            "exp": int(time.time()) + self.access_token_expiry,
            "token_type": "access_token",
            "aud": "darwing-mcp-server"  # Audience
        }
        
        refresh_token_payload = {
            "sub": auth_code_data["user_id"],
            "client_id": client_id,
            "scope": auth_code_data["scope"],
            "exp": int(time.time()) + self.refresh_token_expiry,
            "token_type": "refresh_token",
            "aud": "darwing-mcp-server"
        }
        
        access_token = self._generate_jwt_token(access_token_payload)
        refresh_token = self._generate_jwt_token(refresh_token_payload)
        
        # Store tokens for validation and revocation
        self.access_tokens[access_token] = access_token_payload
        self.refresh_tokens[refresh_token] = refresh_token_payload
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.access_token_expiry,
            "scope": auth_code_data["scope"]
        }
    
    def refresh_access_token(self, refresh_token: str, client_id: str, 
                           client_secret: str = None) -> Optional[Dict]:
        """Refresh an access token with refresh token rotation (OAuth 2.1)"""
        # Verify refresh token
        token_data = self._verify_jwt_token(refresh_token)
        if not token_data or token_data.get("token_type") != "refresh_token":
            return None
        
        # Verify client
        client_data = self.registered_clients.get(client_id)
        if not client_data or token_data["client_id"] != client_id:
            return None
        
        # For confidential clients, verify client secret
        if client_data["client_type"] == "confidential" and client_secret:
            if client_data["client_secret"] != client_secret:
                return None
        
        # OAuth 2.1: Refresh token rotation - invalidate old refresh token
        if refresh_token in self.refresh_tokens:
            del self.refresh_tokens[refresh_token]
        
        # Generate new tokens
        access_token_payload = {
            "sub": token_data["sub"],
            "client_id": client_id,
            "scope": token_data["scope"],
            "exp": int(time.time()) + self.access_token_expiry,
            "token_type": "access_token",
            "aud": "darwing-mcp-server"
        }
        
        new_refresh_token_payload = {
            "sub": token_data["sub"],
            "client_id": client_id,
            "scope": token_data["scope"],
            "exp": int(time.time()) + self.refresh_token_expiry,
            "token_type": "refresh_token",
            "aud": "darwing-mcp-server"
        }
        
        access_token = self._generate_jwt_token(access_token_payload)
        new_refresh_token = self._generate_jwt_token(new_refresh_token_payload)
        
        # Store new tokens
        self.access_tokens[access_token] = access_token_payload
        self.refresh_tokens[new_refresh_token] = new_refresh_token_payload
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,  # New refresh token
            "token_type": "Bearer",
            "expires_in": self.access_token_expiry,
            "scope": token_data["scope"]
        }
    
    def client_credentials_grant(self, client_id: str, client_secret: str, 
                               scope: str = "read write") -> Optional[Dict]:
        """Client credentials grant for machine-to-machine authentication"""
        # Verify client credentials
        client_data = self.registered_clients.get(client_id)
        if not client_data or client_data["client_secret"] != client_secret:
            return None
        
        # Check if client supports client credentials grant
        if "client_credentials" not in client_data.get("grant_types", []):
            return None
        
        # Generate access token (no refresh token for client credentials)
        access_token_payload = {
            "sub": client_id,  # Subject is the client_id for client credentials
            "client_id": client_id,
            "scope": scope,
            "exp": int(time.time()) + self.access_token_expiry,
            "token_type": "access_token",
            "grant_type": "client_credentials",
            "aud": "darwing-mcp-server"
        }
        
        access_token = self._generate_jwt_token(access_token_payload)
        self.access_tokens[access_token] = access_token_payload
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self.access_token_expiry,
            "scope": scope
        }
    
    def revoke_token(self, token: str, client_id: str, client_secret: str = None) -> bool:
        """Revoke an access or refresh token (OAuth 2.1)"""
        # Verify client if secret provided
        if client_secret:
            client_data = self.registered_clients.get(client_id)
            if not client_data or client_data["client_secret"] != client_secret:
                return False
        
        # Remove token from storage
        revoked = False
        if token in self.access_tokens:
            del self.access_tokens[token]
            revoked = True
        if token in self.refresh_tokens:
            del self.refresh_tokens[token]
            revoked = True
            
        return revoked
    
    async def authenticate(self, request) -> Optional[Dict]:
        """Authenticate request using OAuth 2.1 Bearer token"""
        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Verify token
        token_data = self._verify_jwt_token(token)
        if not token_data or token_data.get("token_type") != "access_token":
            return None
        
        # Check if token is in our valid tokens storage
        if token not in self.access_tokens:
            return None
        
        # Return user/client information
        return {
            "user_id": token_data["sub"],
            "client_id": token_data["client_id"],
            "scopes": token_data["scope"].split(" ") if token_data.get("scope") else [],
            "token_data": token_data
        }
    
    def get_authorization_url(self, client_id: str, redirect_uri: str, 
                            scope: str = "read write", state: str = None) -> Dict[str, str]:
        """Generate OAuth 2.1 authorization URL with PKCE"""
        if client_id not in self.registered_clients:
            raise ValueError("Invalid client_id")
        
        if redirect_uri not in self.registered_clients[client_id]["redirect_uris"]:
            raise ValueError("Invalid redirect_uri")
        
        # Generate PKCE challenge
        code_verifier, code_challenge = self._generate_code_challenge()
        
        # Generate authorization code (simplified for demo)
        code = self.generate_authorization_code(
            client_id, redirect_uri, scope, code_challenge
        )
        
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state or secrets.token_urlsafe(16)
        }
        
        auth_url = f"http://localhost:8000/oauth/authorize?{urlencode(params)}"
        
        return {
            "authorization_url": auth_url,
            "code_verifier": code_verifier,  # Client needs this for token exchange
            "code": code,  # For demo purposes
            "state": params["state"]
        }

# Create OAuth 2.1 provider
oauth_provider = OAuth21Provider()

# Initialize the integrated MCP server with OAuth 2.1 authentication
mcp = FastMCP("Forest Market MCP Server", auth=oauth_provider)

# OAuth 2.1 helper endpoints for token management
@mcp.tool(
    name="oauth_get_client_credentials_token",
    description="Get OAuth 2.1 access token using client credentials grant (for machine-to-machine authentication)"
)
def oauth_get_client_credentials_token(
    client_id: Annotated[str, Field(description="OAuth client ID")] = None,
    client_secret: Annotated[str, Field(description="OAuth client secret")] = None,
    scope: Annotated[str, Field(description="Requested scopes (space-separated)")] = "read write"
) -> Dict[str, Any]:
    """Get access token using OAuth 2.1 client credentials grant"""
    
    # Use default client if not provided
    if not client_id:
        client_id = oauth_provider.client_id
    if not client_secret:
        client_secret = oauth_provider.client_secret
    
    try:
        token_response = oauth_provider.client_credentials_grant(client_id, client_secret, scope)
        
        if token_response:
            return {
                "success": True,
                "token_info": token_response,
                "usage": "Use the access_token in Authorization header: 'Bearer <access_token>'"
            }
        else:
            return {
                "success": False,
                "error": "Invalid client credentials or unsupported grant type"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get token: {str(e)}"
        }

@mcp.tool(
    name="oauth_get_authorization_url",
    description="Get OAuth 2.1 authorization URL for authorization code flow with PKCE"
)
def oauth_get_authorization_url(
    redirect_uri: Annotated[str, Field(description="Redirect URI for OAuth callback")] = "http://localhost:3000/auth/callback",
    scope: Annotated[str, Field(description="Requested scopes (space-separated)")] = "read write",
    state: Annotated[Optional[str], Field(description="Optional state parameter for CSRF protection")] = None
) -> Dict[str, Any]:
    """Get OAuth 2.1 authorization URL with PKCE for user authentication"""
    
    try:
        auth_data = oauth_provider.get_authorization_url(
            oauth_provider.client_id, redirect_uri, scope, state
        )
        
        return {
            "success": True,
            "authorization_data": auth_data,
            "instructions": [
                "1. Direct user to authorization_url",
                "2. User authorizes and gets redirected with 'code' parameter",
                "3. Use oauth_exchange_code_for_token with the code and code_verifier"
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate authorization URL: {str(e)}"
        }

@mcp.tool(
    name="oauth_exchange_code_for_token",
    description="Exchange OAuth 2.1 authorization code for access token (with PKCE)"
)
def oauth_exchange_code_for_token(
    code: Annotated[str, Field(description="Authorization code from OAuth callback")],
    code_verifier: Annotated[str, Field(description="PKCE code verifier (from authorization URL generation)")],
    redirect_uri: Annotated[str, Field(description="Same redirect URI used in authorization request")] = "http://localhost:3000/auth/callback",
    client_id: Annotated[str, Field(description="OAuth client ID")] = None,
    client_secret: Annotated[str, Field(description="OAuth client secret")] = None
) -> Dict[str, Any]:
    """Exchange authorization code for access token using OAuth 2.1 with PKCE"""
    
    # Use default client if not provided
    if not client_id:
        client_id = oauth_provider.client_id
    if not client_secret:
        client_secret = oauth_provider.client_secret
    
    try:
        token_response = oauth_provider.exchange_code_for_token(
            code, client_id, client_secret, redirect_uri, code_verifier
        )
        
        if token_response:
            return {
                "success": True,
                "token_info": token_response,
                "usage": "Use the access_token in Authorization header: 'Bearer <access_token>'"
            }
        else:
            return {
                "success": False,
                "error": "Invalid authorization code, client credentials, or PKCE verification failed"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to exchange code for token: {str(e)}"
        }

@mcp.tool(
    name="oauth_refresh_token",
    description="Refresh OAuth 2.1 access token using refresh token (with token rotation)"
)
def oauth_refresh_token(
    refresh_token: Annotated[str, Field(description="Refresh token from previous token response")],
    client_id: Annotated[str, Field(description="OAuth client ID")] = None,
    client_secret: Annotated[str, Field(description="OAuth client secret")] = None
) -> Dict[str, Any]:
    """Refresh access token using OAuth 2.1 refresh token with rotation"""
    
    # Use default client if not provided
    if not client_id:
        client_id = oauth_provider.client_id
    if not client_secret:
        client_secret = oauth_provider.client_secret
    
    try:
        token_response = oauth_provider.refresh_access_token(refresh_token, client_id, client_secret)
        
        if token_response:
            return {
                "success": True,
                "token_info": token_response,
                "note": "New refresh token provided - old refresh token is now invalid (token rotation)",
                "usage": "Use the new access_token in Authorization header: 'Bearer <access_token>'"
            }
        else:
            return {
                "success": False,
                "error": "Invalid refresh token or client credentials"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to refresh token: {str(e)}"
        }

@mcp.tool(
    name="oauth_revoke_token",
    description="Revoke OAuth 2.1 access or refresh token"
)
def oauth_revoke_token(
    token: Annotated[str, Field(description="Access or refresh token to revoke")],
    client_id: Annotated[str, Field(description="OAuth client ID")] = None,
    client_secret: Annotated[str, Field(description="OAuth client secret")] = None
) -> Dict[str, Any]:
    """Revoke an OAuth 2.1 access or refresh token"""
    
    # Use default client if not provided
    if not client_id:
        client_id = oauth_provider.client_id
    if not client_secret:
        client_secret = oauth_provider.client_secret
    
    try:
        revoked = oauth_provider.revoke_token(token, client_id, client_secret)
        
        return {
            "success": revoked,
            "message": "Token revoked successfully" if revoked else "Token not found or already revoked"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to revoke token: {str(e)}"
        }

@mcp.tool(
    name="oauth_get_server_info",
    description="Get OAuth 2.1 server configuration and client information"
)
def oauth_get_server_info() -> Dict[str, Any]:
    """Get OAuth 2.1 server configuration information"""
    
    return {
        "oauth_version": "2.1",
        "server_info": {
            "issuer": "darwing-mcp-server",
            "authorization_endpoint": "http://localhost:8000/oauth/authorize",
            "token_endpoint": "http://localhost:8000/oauth/token",
            "revocation_endpoint": "http://localhost:8000/oauth/revoke"
        },
        "client_info": {
            "client_id": oauth_provider.client_id,
            "client_type": "confidential",
            "supported_grant_types": ["authorization_code", "refresh_token", "client_credentials"],
            "supported_scopes": ["read", "write", "admin"],
            "redirect_uris": oauth_provider.registered_clients[oauth_provider.client_id]["redirect_uris"]
        },
        "token_settings": {
            "access_token_expiry": f"{oauth_provider.access_token_expiry} seconds",
            "refresh_token_expiry": f"{oauth_provider.refresh_token_expiry} seconds",
            "authorization_code_expiry": f"{oauth_provider.authorization_code_expiry} seconds"
        },
        "security_features": [
            "PKCE (Proof Key for Code Exchange) required",
            "Short-lived access tokens (15 minutes default)",
            "Refresh token rotation",
            "JWT tokens with proper validation",
            "Secure token storage and revocation"
        ],
        "usage_examples": {
            "client_credentials": "Use oauth_get_client_credentials_token for machine-to-machine auth",
            "authorization_code": "Use oauth_get_authorization_url then oauth_exchange_code_for_token for user auth",
            "refresh": "Use oauth_refresh_token to get new access tokens"
        }
    }

# Add HTTP endpoints for OAuth 2.1 when running in HTTP mode
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Create FastAPI app for OAuth endpoints (only used in HTTP mode)
oauth_app = FastAPI()

@oauth_app.get("/oauth/authorize")
async def oauth_authorize_endpoint(
    response_type: str,
    client_id: str, 
    redirect_uri: str,
    scope: str = "read write",
    code_challenge: str = None,
    code_challenge_method: str = "S256",
    state: str = None
):
    """OAuth 2.1 Authorization Endpoint - Shows login form"""
    
    # Validate client and redirect URI
    if client_id not in oauth_provider.registered_clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    client_data = oauth_provider.registered_clients[client_id]
    if redirect_uri not in client_data["redirect_uris"]:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    
    if not code_challenge:
        return HTMLResponse("""
        <html><body>
        <h2>OAuth 2.1 Authorization Error</h2>
        <p>Error: PKCE code_challenge is required</p>
        </body></html>
        """)
    
    # Store authorization request in session
    session_id = secrets.token_urlsafe(32)
    oauth_provider.auth_sessions[session_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "state": state,
        "expires_at": time.time() + 600  # 10 minutes
    }
    
    # Show login form
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DarwinG MCP - OAuth 2.1 Login</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }}
            .login-form {{ background: #f5f5f5; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            input {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }}
            button {{ background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; width: 100%; cursor: pointer; }}
            button:hover {{ background: #0056b3; }}
            .info {{ background: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .demo-creds {{ background: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 15px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="login-form">
            <h2>🔐 DarwinG MCP OAuth 2.1</h2>
            
            <div class="info">
                <strong>Application:</strong> {client_id}<br>
                <strong>Permissions:</strong> {scope}<br>
                <strong>Redirect:</strong> {redirect_uri}
            </div>
            
            <form action="/oauth/login" method="post">
                <input type="hidden" name="session_id" value="{session_id}">
                
                <label>Username:</label>
                <input type="text" name="username" required placeholder="Enter your username">
                
                <label>Password:</label>
                <input type="password" name="password" required placeholder="Enter your password">
                
                <button type="submit">🔑 Login & Authorize</button>
            </form>
            
            <div class="demo-creds">
                <strong>Demo Credentials:</strong><br>
                • Username: <code>demo</code> / Password: <code>password123</code><br>
                • Username: <code>admin</code> / Password: <code>admin123</code>
            </div>
        </div>
    </body>
    </html>
    """)

@oauth_app.post("/oauth/login")
async def oauth_login_endpoint(
    session_id: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    """Handle user login and authorization"""
    
    # Get auth session
    auth_session = oauth_provider.auth_sessions.get(session_id)
    if not auth_session or auth_session["expires_at"] < time.time():
        return HTMLResponse("""
        <html><body>
        <h2>OAuth 2.1 Session Expired</h2>
        <p>Your authorization session has expired. Please try again.</p>
        </body></html>
        """)
    
    # Authenticate user
    user = oauth_provider.authenticate_user(username, password)
    if not user:
        return HTMLResponse(f"""
        <html><body>
        <h2>OAuth 2.1 Login Failed</h2>
        <p>Invalid username or password.</p>
        <a href="/oauth/authorize?response_type=code&client_id={auth_session['client_id']}&redirect_uri={auth_session['redirect_uri']}&scope={auth_session['scope']}&code_challenge={auth_session['code_challenge']}&code_challenge_method={auth_session['code_challenge_method']}&state={auth_session.get('state', '')}">← Try Again</a>
        </body></html>
        """)
    
    # Check if user has required scopes
    requested_scopes = auth_session["scope"].split(" ")
    user_scopes = user["scopes"]
    
    if not all(scope in user_scopes for scope in requested_scopes):
        return HTMLResponse(f"""
        <html><body>
        <h2>OAuth 2.1 Insufficient Permissions</h2>
        <p>User <strong>{user['username']}</strong> does not have the required permissions.</p>
        <p>Required: {requested_scopes}</p>
        <p>Available: {user_scopes}</p>
        </body></html>
        """)
    
    # Generate authorization code
    try:
        auth_code = oauth_provider.generate_authorization_code(
            auth_session["client_id"],
            auth_session["redirect_uri"], 
            auth_session["scope"],
            auth_session["code_challenge"],
            auth_session["code_challenge_method"],
            user["user_id"]
        )
        
        # Clean up session
        del oauth_provider.auth_sessions[session_id]
        
        # Redirect with authorization code
        redirect_url = f"{auth_session['redirect_uri']}?code={auth_code}"
        if auth_session.get("state"):
            redirect_url += f"&state={auth_session['state']}"
            
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        return HTMLResponse(f"""
        <html><body>
        <h2>OAuth 2.1 Authorization Error</h2>
        <p>Error generating authorization code: {str(e)}</p>
        </body></html>
        """)

@oauth_app.post("/oauth/token")
async def oauth_token_endpoint(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(None),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    code_verifier: str = Form(None),
    refresh_token: str = Form(None),
    scope: str = Form("read write")
):
    """OAuth 2.1 Token Endpoint"""
    
    try:
        if grant_type == "authorization_code":
            if not all([code, redirect_uri, code_verifier]):
                raise HTTPException(status_code=400, detail="Missing required parameters for authorization_code grant")
            
            token_response = oauth_provider.exchange_code_for_token(
                code, client_id, client_secret, redirect_uri, code_verifier
            )
            
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise HTTPException(status_code=400, detail="Missing refresh_token")
            
            token_response = oauth_provider.refresh_access_token(
                refresh_token, client_id, client_secret
            )
            
        elif grant_type == "client_credentials":
            if not client_secret:
                raise HTTPException(status_code=400, detail="Missing client_secret for client_credentials grant")
            
            token_response = oauth_provider.client_credentials_grant(
                client_id, client_secret, scope
            )
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported grant_type")
        
        if not token_response:
            raise HTTPException(status_code=400, detail="Invalid request or credentials")
        
        return JSONResponse(content=token_response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@oauth_app.post("/oauth/revoke")
async def oauth_revoke_endpoint(
    token: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(None)
):
    """OAuth 2.1 Token Revocation Endpoint"""
    
    try:
        revoked = oauth_provider.revoke_token(token, client_id, client_secret)
        return JSONResponse(content={"revoked": revoked})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@oauth_app.get("/register/")
async def register_callback():
    """Handle registration callback (placeholder)"""
    return HTMLResponse("""
    <html><body>
    <h2>OAuth 2.1 Registration Complete</h2>
    <p>Your authorization was successful!</p>
    <p>You can now close this window.</p>
    </body></html>
    """)

@oauth_app.get("/auth/callback")
async def auth_callback(code: str = None, state: str = None, error: str = None):
    """Handle OAuth callback"""
    if error:
        return HTMLResponse(f"""
        <html><body>
        <h2>OAuth 2.1 Authorization Error</h2>
        <p>Error: {error}</p>
        </body></html>
        """)
    
    return HTMLResponse(f"""
    <html><body>
    <h2>OAuth 2.1 Authorization Successful</h2>
    <p>Authorization code: <code>{code}</code></p>
    <p>State: <code>{state}</code></p>
    <p>You can now exchange this code for an access token.</p>
    </body></html>
    """)

@oauth_app.get("/oauth/callback")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    """Alternative OAuth callback endpoint"""
    return await auth_callback(code, state, error)

@oauth_app.get("/")
async def root():
    """Root endpoint with OAuth info"""
    return JSONResponse(content={
        "service": "DarwinG MCP OAuth 2.1 Server",
        "version": "2.1",
        "endpoints": {
            "authorization": "/oauth/authorize",
            "token": "/oauth/token", 
            "revocation": "/oauth/revoke"
        },
        "client_id": oauth_provider.client_id,
        "supported_grant_types": ["authorization_code", "refresh_token", "client_credentials"],
        "supported_scopes": ["read", "write", "admin"]
    })

# Internal function for create_draft logic that can be shared
def _create_draft_internal(
    user_id: Annotated[str, Field(description="User identifier for draft ownership. Use provided user ID or 'ai_agent' if generating automatically.")],
    title: Annotated[str, Field(description="Product name extracted from user input. Examples: 'wireless gaming mouse', 'vintage leather jacket', 'Python programming course'")] = "",
    description: Annotated[str, Field(description="Detailed product description extracted from user input. Include features, benefits, use cases, and selling points mentioned by user.")] = "",
    price: Annotated[float, Field(description="Product price in USDT. Extract numerical value from user input (e.g., '$99.99' becomes 99.99, '50 dollars' becomes 50.0). Must be >= 0.", ge=0)] = 0.0,
    category: Annotated[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"], Field(description="Product category classification. Map user input to exact values: software/courses/digital content = DIGITAL_GOODS, phones/computers/gadgets = ELECTRONICS, clothing/accessories = FASHION, rare items/collectibles = COLLECTIBLES, blockchain hardware = DEPIN, personalized items = CUSTOM, everything else = OTHER")] = "OTHER",
    condition: Annotated[Literal["NEW", "USED"], Field(description="Product condition. Extract from user input: new/unused/fresh/mint = NEW, used/pre-owned/second-hand/refurbished = USED")] = "NEW",
    variations_data: Annotated[Optional[List[VariationData]], Field(description='''Product variations extracted from user input. EXACT FORMAT REQUIRED: null OR array matching VariationData class:
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

# Register all draft management tools
@mcp.tool(
    name="create_draft",
    description="Create a Forest Market product draft from natural language - just describe your product naturally! AI will automatically extract and structure all the details."
)
def create_draft(
    user_input: Annotated[str, Field(description="Natural language description of the product you want to create. Example: 'I want to sell a wireless gaming mouse for $50, it has RGB lighting and ships from US to anywhere, I have 10 in stock'")],
    user_id: Annotated[str, Field(description="User identifier for draft ownership")] = "ai_user",
    image_file_paths: Annotated[Optional[List[str]], Field(description="Optional image file paths if you have product images")] = None
) -> Dict[str, Any]:
    """Create a draft using natural language - AI will extract all the structured data automatically"""
    
    # Extract schema directly from the internal function to get all detailed field descriptions
    create_draft_schema = _extract_schema_from_function(_create_draft_internal)
    
    # Use AI to parse the natural language input
    parsed_params = _parse_natural_language_with_ai(user_input, create_draft_schema, user_id)
    
    # Add image paths if provided
    if image_file_paths:
        parsed_params["image_file_paths"] = image_file_paths
    
    # Convert variations_data format if present
    if "variations_data" in parsed_params and parsed_params["variations_data"]:
        variations_list = []
        for var in parsed_params["variations_data"]:
            if isinstance(var, dict) and "name" in var and "values" in var:
                variations_list.append(VariationData(name=var["name"], values=var["values"]))
        parsed_params["variations_data"] = variations_list if variations_list else None
    
    # Convert shipping_prices_data format if present
    if "shipping_prices_data" in parsed_params and parsed_params["shipping_prices_data"]:
        shipping_list = []
        for sp in parsed_params["shipping_prices_data"]:
            if isinstance(sp, dict) and "country_code" in sp:
                shipping_list.append(ShippingPriceData(
                    country_code=sp["country_code"],
                    price=sp.get("price", 0.0),
                    currency_code=sp.get("currency_code", "USDT")
                ))
        parsed_params["shipping_prices_data"] = shipping_list if shipping_list else None
    
    # Filter out None values that should be strings
    filtered_params = {}
    for key, value in parsed_params.items():
        if value is None and key in ["ship_from_country", "discount_type"]:
            # Skip None values for optional string fields
            continue
        filtered_params[key] = value
    
    # Call the internal create_draft function
    try:
        # Debug: Print parsed parameters to see what AI generated
        print(f"AI parsed parameters: {filtered_params}")
        
        result = _create_draft_internal(**filtered_params)
        return result
    except Exception as e:
        return {
            "error": f"Failed to create draft: {str(e)}"
        }

@mcp.tool(
    name="get_draft",
    description="Retrieve draft information with flexible output modes: full details, summary, or batch processing"
)
def get_draft(
    draft_id: Annotated[Optional[str], Field(description="Draft ID to retrieve (required unless using batch_ids)")] = None,
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification and access control")] = None,
    summary_only: Annotated[bool, Field(description="Return summary instead of full draft details")] = False,
    batch_ids: Annotated[Optional[List[str]], Field(description="Multiple draft IDs for batch retrieval (overrides draft_id)")] = None
) -> Dict[str, Any]:
    """Unified draft retrieval tool with multiple modes"""
    
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

@mcp.tool(
    name="update_draft",
    description="Update Forest Market draft from natural language - just describe what you want to change about your product!"
)
def update_draft(
    draft_id: Annotated[str, Field(description="Draft ID to update (required)")],
    user_input: Annotated[str, Field(description="Natural language description of what you want to update about your product. Example: 'Change the price to $65 and add Blue switches as a variation option'")],
    user_id: Annotated[str, Field(description="User identifier for ownership verification")] = "ai_user"
) -> Dict[str, Any]:
    """Update a Forest Market product draft from natural language - just describe what you want to change!"""
    
    # Extract schema directly from the internal function
    update_draft_schema = _extract_schema_from_function(_update_draft_internal)
    
    # Use AI to parse the natural language input 
    parsed_params = _parse_natural_language_with_ai(user_input, update_draft_schema, user_id)
    
    # Always include the draft_id and user_id
    parsed_params["draft_id"] = draft_id
    parsed_params["user_id"] = user_id
    
    # Convert variations_data format if present
    if "variations_data" in parsed_params and parsed_params["variations_data"]:
        variations_list = []
        for var in parsed_params["variations_data"]:
            if isinstance(var, dict) and "name" in var and "values" in var:
                variations_list.append(VariationData(name=var["name"], values=var["values"]))
        parsed_params["variations_data"] = variations_list if variations_list else None
    
    # Convert shipping_prices_data format if present
    if "shipping_prices_data" in parsed_params and parsed_params["shipping_prices_data"]:
        shipping_list = []
        for sp in parsed_params["shipping_prices_data"]:
            if isinstance(sp, dict) and "country_code" in sp:
                shipping_list.append(ShippingPriceData(
                    country_code=sp["country_code"],
                    price=sp.get("price", 0.0),
                    currency_code=sp.get("currency_code", "USDT")
                ))
        parsed_params["shipping_prices_data"] = shipping_list if shipping_list else None
    
    # Call the internal function
    try:
        # Filter out None values that should be strings
        filtered_params = {}
        for key, value in parsed_params.items():
            if value is None and key in ["ship_from_country", "discount_type"]:
                continue
            filtered_params[key] = value
        
        result = _update_draft_internal(**filtered_params)
        result["ai_parsed_input"] = user_input
        result["ai_extracted_params"] = {k: v for k, v in filtered_params.items() if k not in ["draft_id", "user_id"]}
        return result
    except Exception as e:
        return {
            "error": f"Failed to update draft: {str(e)}",
            "ai_parsed_input": user_input,
            "ai_extracted_params": parsed_params
        }

@mcp.tool(
    name="list_drafts",
    description="Search and filter Forest Market drafts with advanced querying capabilities"
)
def list_drafts(
    user_id: Annotated[Optional[str], Field(description="Filter by user ID (leave empty for all users)")] = None,
    query: Annotated[Optional[str], Field(description="Search term for title, description, tags, and specifications")] = None,
    category: Annotated[Optional[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]], Field(description="Filter by Forest Market category")] = None,
    condition: Annotated[Optional[Literal["NEW", "USED"]], Field(description="Filter by product condition")] = None,
    min_price: Annotated[Optional[float], Field(description="Minimum price filter (>= 0)", ge=0)] = None,
    max_price: Annotated[Optional[float], Field(description="Maximum price filter (>= 0)", ge=0)] = None,
    limit: Annotated[Optional[int], Field(description="Max results to return (1-100)", ge=1, le=100)] = None,
    offset: Annotated[Optional[int], Field(description="Results to skip for pagination (>= 0)", ge=0)] = None,
    with_stats: Annotated[bool, Field(description="Include user statistics (requires user_id)")] = False
) -> Dict[str, Any]:
    """Search and filter drafts with comprehensive query capabilities"""
    
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
    name="export_draft",
    description="Export draft in Forest Market format for listing integration and final review"
)
def export_draft(
    draft_id: Annotated[str, Field(description="Draft ID to export for listing (required)")],
    user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
    export_format: Annotated[Literal["forest_market", "json"], Field(description="Export format: forest_market (optimized) or json (raw)")] = "forest_market",
    include_mapping_info: Annotated[bool, Field(description="Include field mapping information for upload tool compatibility")] = False
) -> Dict[str, Any]:
    """Export draft data for integration with listing MCP services"""
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
    description="Add new options to draft from natural language - just describe what you want to add to your product!"
)
def add_to_draft(
    draft_id: Annotated[str, Field(description="Draft ID to update incrementally (required)")],
    user_input: Annotated[str, Field(description="Natural language description of what you want to add to your product. Example: 'Add XL and XXL sizes, add wireless tag, and add shipping to Canada for $30'")],
    user_id: Annotated[str, Field(description="User identifier for ownership verification")] = "ai_user"
) -> Dict[str, Any]:
    """Add new options to a Forest Market product draft from natural language - just describe what you want to add!"""
    
    # Extract schema directly from the internal function
    add_to_draft_schema = _extract_schema_from_function(_add_to_draft_internal)
    
    # Use AI to parse the natural language input 
    parsed_params = _parse_natural_language_with_ai(user_input, add_to_draft_schema, user_id)
    
    # Always include the draft_id and user_id
    parsed_params["draft_id"] = draft_id
    parsed_params["user_id"] = user_id
    
    # Convert variations_data format if present
    if "variations_data" in parsed_params and parsed_params["variations_data"]:
        variations_list = []
        for var in parsed_params["variations_data"]:
            if isinstance(var, dict) and "name" in var and "values" in var:
                variations_list.append(VariationData(name=var["name"], values=var["values"]))
        parsed_params["variations_data"] = variations_list if variations_list else None
    
    # Convert shipping_prices_data format if present
    if "shipping_prices_data" in parsed_params and parsed_params["shipping_prices_data"]:
        shipping_list = []
        for sp in parsed_params["shipping_prices_data"]:
            if isinstance(sp, dict) and "country_code" in sp:
                shipping_list.append(ShippingPriceData(
                    country_code=sp["country_code"],
                    price=sp.get("price", 0.0),
                    currency_code=sp.get("currency_code", "USDT")
                ))
        parsed_params["shipping_prices_data"] = shipping_list if shipping_list else None
    
    # Call the internal function
    try:
        # Filter out None values
        filtered_params = {}
        for key, value in parsed_params.items():
            if value is not None:
                filtered_params[key] = value
        
        result = _add_to_draft_internal(**filtered_params)
        result["ai_parsed_input"] = user_input
        result["ai_extracted_params"] = {k: v for k, v in filtered_params.items() if k not in ["draft_id", "user_id"]}
        return result
    except Exception as e:
        return {
            "error": f"Failed to add to draft: {str(e)}",
            "ai_parsed_input": user_input,
            "ai_extracted_params": parsed_params
        }

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

@mcp.tool(
    name="remove_from_draft",
    description="Remove options from draft using natural language - just describe what you want to remove from your product!"
)
def remove_from_draft(
    draft_id: Annotated[str, Field(description="Draft ID to update selectively (required)")],
    user_input: Annotated[str, Field(description="Natural language description of what you want to remove from your product. Example: 'Remove size S and M, remove wireless tag, and stop shipping to Canada'")],
    user_id: Annotated[str, Field(description="User identifier for ownership verification")] = "ai_user"
) -> Dict[str, Any]:
    """Remove options from a Forest Market product draft using natural language - just describe what you want to remove!"""
    
    # Extract schema directly from the internal function
    remove_from_draft_schema = _extract_schema_from_function(_remove_from_draft_internal)
    
    # Use AI to parse the natural language input 
    parsed_params = _parse_natural_language_with_ai(user_input, remove_from_draft_schema, user_id)
    
    # Always include the draft_id and user_id
    parsed_params["draft_id"] = draft_id
    parsed_params["user_id"] = user_id
    
    # Call the internal function
    try:
        # Filter out None values
        filtered_params = {}
        for key, value in parsed_params.items():
            if value is not None:
                filtered_params[key] = value
        
        result = _remove_from_draft_internal(**filtered_params)
        result["ai_parsed_input"] = user_input
        result["ai_extracted_params"] = {k: v for k, v in filtered_params.items() if k not in ["draft_id", "user_id"]}
        return result
    except Exception as e:
        return {
            "error": f"Failed to remove from draft: {str(e)}",
            "ai_parsed_input": user_input,
            "ai_extracted_params": parsed_params
        }

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

@mcp.tool(
    name="draft_to_listing",
    description="🚨 CONFIRMATION REQUIRED: Complete workflow to export draft and create live listing. This will upload images and create a REAL listing on Forest Market. ALWAYS ask user for explicit confirmation before calling this tool. Never call this automatically after create_draft."
)
def draft_to_listing(
    draft_id: Annotated[str, Field(description="Draft ID to convert to live listing")],
    user_confirmed: Annotated[Any, Field(description="User explicit confirmation to proceed with live listing creation. Can be boolean True or string 'true'/'yes'. AI should ask user: 'Do you want to create a live listing on Forest Market?' and get explicit yes/no confirmation.")] = False,
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
            "session_token": os.getenv('FM_SESSION_TOKEN'),
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


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        # Run as MCP server
        mcp.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "http":
        # Run as HTTP server for public deployment (Render)
        port = int(os.getenv("PORT", 8000))
        
        # Get the FastMCP's FastAPI app
        app = mcp.http_app()
        
        # Mount OAuth endpoints
        app.mount("/oauth", oauth_app)
        app.add_api_route("/register/", register_callback, methods=["GET"])
        app.add_api_route("/auth/callback", auth_callback, methods=["GET"])
        
        # Add a root endpoint that shows server info
        @app.get("/")
        async def main_root():
            return {
                "service": "DarwinG MCP OAuth 2.1 Server", 
                "version": "2.1",
                "mcp_endpoints": {
                    "tools": "/tools",
                    "prompts": "/prompts", 
                    "resources": "/resources"
                },
                "oauth_endpoints": {
                    "authorize": "/oauth/authorize", 
                    "token": "/oauth/token",
                    "revoke": "/oauth/revoke"
                },
                "callbacks": {
                    "register": "/register/",
                    "auth": "/auth/callback"
                },
                "demo_users": {
                    "demo": "password123",
                    "admin": "admin123"
                }
            }
        
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        print("Usage:")
        print("  python integrated_mcp_server_oauth.py mcp   # STDIO transport")
        print("  python integrated_mcp_server_oauth.py http  # HTTP transport for Render")