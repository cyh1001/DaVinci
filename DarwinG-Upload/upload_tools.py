# Direct API approach - much cleaner!
import requests
import json
from fastapi import FastAPI

class WalletConnectorMCP:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://forestmarket.net"
    
    async def connect_wallet(self, wallet_address: str, private_key: str):
        # 1. Get CSRF token
        csrf_response = self.session.get(f"{self.base_url}/api/auth/csrf")
        csrf_token = csrf_response.json()["csrfToken"]
        
        # 2. Get nonce for wallet signing
        nonce_response = self.session.get(f"{self.base_url}/api/auth/nonce", 
                                        params={"address": wallet_address})
        nonce = nonce_response.json()["nonce"]
        
        # 3. Sign the message (this is the key part)
        message = f"Sign this message to authenticate: {nonce}"
        signature = self._sign_message(message, private_key)
        
        # 4. Submit authentication
        auth_data = {
            "token": signature,
            "redirect": "/dashboard",
            "callbackUrl": f"{self.base_url}/dashboard", 
            "csrfToken": csrf_token,
            "json": True
        }
        
        auth_response = self.session.post(
            f"{self.base_url}/api/auth/signin/dynamic",
            json=auth_data
        )
        
        if auth_response.status_code == 200:
            # Session cookie is now stored in self.session
            return {
                "success": True,
                "session_cookies": dict(self.session.cookies),
                "session_token": self.session.cookies.get("session-token")
            }
    
    def _sign_message(self, message: str, private_key: str) -> str:
        # Use eth_account to sign the message
        from eth_account import Account
        from eth_account.messages import encode_defunct
        
        message_hash = encode_defunct(text=message)
        signed_message = Account.sign_message(message_hash, private_key)
        return signed_message.signature.hex()
    
    # Now you can use the authenticated session for other APIs
    async def upload_product(self, product_data: dict):
        """Use the stored session to upload a product"""
        response = self.session.post(
            f"{self.base_url}/api/products/upload",
            json=product_data
        )
        return response.json()

class ProductUploadMCP:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://forestmarket.net"

    async def upload_product(self, product_data: dict):
        """Use the stored session to upload a product"""
        response = self.session.post(
            f"{self.base_url}/api/products/upload",
            json=product_data
        )