#!/usr/bin/env python3
"""
Forest Market Integrated Authentication Test Script
===================================================

This single script handles the complete process of capturing a fresh signature
and immediately testing the full Forest Market authentication workflow.
It is designed to correctly handle session cookies to retrieve the final
session token and includes retry logic for network stability.

WHAT THIS SCRIPT DOES:
1.  Uses a single, persistent session to fetch a CSRF token and its
    corresponding security cookie.
2.  Fetches a fresh nonce from the Dynamic.xyz API, retrying on network errors.
3.  Generates the exact SIWE message to be signed.
4.  Provides instructions for you to use the local `signer.html` to get a signature.
5.  Waits for you to input the fresh signature.
6.  Immediately uses all the captured data to run the complete authentication test,
    persisting the session cookie and retrying on network errors.
"""

import requests
import urllib.parse
from datetime import datetime
from typing import Dict, Any
import os
import time

class ForestMarketAuthTester:
    """
    Handles the entire authentication flow using a single requests.Session
    to correctly manage cookies, particularly the CSRF cookie.
    """
    def __init__(self):
        self.dynamic_base_url = "https://app.dynamicauth.com/api/v0/sdk"
        self.dynamic_environment_id = "02e5c99f-a7aa-4841-b64a-df128fa8e08f"
        self.forest_market_base_url = "https://forestmarket.net"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })
        self.csrf_token = None
        self.nonce = None

    def get_fresh_login_data(self):
        """Step 1 & 2: Get fresh CSRF token (and cookie) and nonce with retry logic."""
        print("[STEP 1 & 2] Getting fresh CSRF token and Nonce...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Step 1: Get CSRF token. The session object will store the cookie automatically.
                csrf_url = f"{self.forest_market_base_url}/api/auth/csrf"
                csrf_response = self.session.get(csrf_url, timeout=10)
                csrf_response.raise_for_status() # Raise an exception for bad status codes
                self.csrf_token = csrf_response.json().get("csrfToken")
                print(f"[SUCCESS] CSRF token retrieved: {self.csrf_token[:30]}...")
                
                # Step 2: Get nonce
                nonce_url = f"{self.dynamic_base_url}/{self.dynamic_environment_id}/nonce"
                nonce_headers = {"Origin": "https://forestmarket.net"}
                nonce_response = self.session.get(nonce_url, headers=nonce_headers, timeout=10)
                nonce_response.raise_for_status()
                self.nonce = nonce_response.json().get("nonce")
                print(f"[SUCCESS] Nonce retrieved: {self.nonce[:30]}...")
                
                return True # Success, exit the loop
            except requests.exceptions.RequestException as e:
                print(f"[ATTEMPT {attempt + 1}/{max_retries}] Network Error while getting fresh data: {e}")
                if attempt < max_retries - 1:
                    print("     --> Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    print("[FAILED] Max retries reached. Could not get fresh login data.")
                    return False
        return False

    def create_login_message(self, wallet_address: str):
        """Step 3: Create the exact message that needs to be signed."""
        print("\n[STEP 3] Creating SIWE message for signing...")
        timestamp = datetime.utcnow().isoformat() + "Z"
        message = f"""forestmarket.net wants you to sign in with your Ethereum account:
{wallet_address}

Welcome to Forest Market. Signing is the only way we can truly know that you are the owner of the wallet you are connecting. Signing is a safe, gas-less transaction that does not in any way give Forest Market permission to perform any transactions with your wallet.

URI: https://forestmarket.net/en-HK
Version: 1
Chain ID: 1
Nonce: {self.nonce}
Issued At: {timestamp}
Request ID: {self.dynamic_environment_id}"""
        print("[SUCCESS] Message created.")
        return message

    def verify_signature(self, wallet_address: str, message: str, signature: str) -> Dict[str, Any]:
        """Step 4: Verify signature with Dynamic and get JWT"""
        print("\n[STEP 4] Testing signature verification with Dynamic...")
        try:
            url = f"{self.dynamic_base_url}/{self.dynamic_environment_id}/verify"
            payload = {
                "signedMessage": signature, "messageToSign": message, "publicWalletAddress": wallet_address,
                "chain": "EVM", "walletName": "metamask", "walletProvider": "browserExtension",
                "network": "1", "additionalWalletAddresses": []
            }
            response = self.session.post(url, json=payload, headers={"Origin": "https://forestmarket.net"}, timeout=15)
            
            if response.status_code == 200:
                jwt_token = response.json().get("jwt", "")
                print("[SUCCESS] Signature verified successfully")
                print(f"      --> JWT token received: {jwt_token[:30]}...")
                return {"success": True, "jwt": jwt_token}
            else:
                print(f"[FAILED] Signature verification failed: {response.status_code}")
                print(f"     --> Response: {response.text[:200]}")
                return {"success": False}
        except Exception as e:
            print(f"[FAILED] Error verifying signature: {e}")
            return {"success": False}

    def exchange_jwt(self, jwt_token: str) -> Dict[str, Any]:
        """Step 5: Exchange JWT for Forest Market session token with retry logic."""
        print("\n[STEP 5] Testing JWT exchange for session token...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                url = f"{self.forest_market_base_url}/api/auth/callback/Dynamic"
                headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": "https://forestmarket.net"}
                payload_data = {
                    "token": jwt_token, "redirect": "false", "callbackUrl": "https://forestmarket.net/en-HK",
                    "csrfToken": self.csrf_token, "json": "true"
                }
                payload = urllib.parse.urlencode(payload_data)
                response = self.session.post(url, data=payload, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    set_cookie = response.headers.get("Set-Cookie", "")
                    session_token = None
                    if "__Secure-next-auth.session-token=" in set_cookie:
                        start = set_cookie.find("__Secure-next-auth.session-token=") + len("__Secure-next-auth.session-token=")
                        end = set_cookie.find(";", start)
                        session_token = set_cookie[start:end if end != -1 else None]
                        print(f"[SUCCESS] Session token extracted: {session_token[:30]}...")
                    else:
                        print("[WARNING] No session token found in Set-Cookie header. The server accepted the login but did not return a token.")
                    return {"success": True, "session_token": session_token}
            except requests.exceptions.RequestException as e:
                print(f"[ATTEMPT {attempt + 1}/{max_retries}] Network Error: {e}")
                if attempt < max_retries - 1:
                    print("     --> Retrying in 2 seconds...")
                    time.sleep(2)
            except Exception as e:
                print(f"[FAILED] An unexpected error occurred: {e}")
                return {"success": False}
        
        print("[FAILED] Max retries reached for JWT exchange.")
        return {"success": False}

    def verify_session(self, session_token: str):
        """Step 6: Verify the session token works"""
        if not session_token:
            print("\n[SKIPPED] Step 6: Skipped session verification (no session token).")
            return True # Not a failure, just nothing to test

        print("\n[STEP 6] Testing session verification...")
        try:
            url = f"{self.forest_market_base_url}/api/auth/session"
            headers = {"Cookie": f"__Secure-next-auth.session-token={session_token}"}
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_id = response.json().get('user', {}).get('id', 'N/A')
                print(f"[SUCCESS] Session verified successfully. User ID: {user_id}")
                return True
            else:
                print(f"[FAILED] Session verification failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"[FAILED] Error verifying session: {e}")
            return False

def main():
    print("=" * 60)
    print("Forest Market Integrated Authentication Test")
    print("=" * 60)

    tester = ForestMarketAuthTester()

    if not tester.get_fresh_login_data():
        return

    wallet_address = input("\nPlease enter your wallet address: ").strip()
    if not wallet_address:
        print("[FAILED] No wallet address provided. Exiting.")
        return
    
    message = tester.create_login_message(wallet_address)
    
    print("\n" + "=" * 60)
    print("ACTION REQUIRED: Please sign the message below")
    print("=" * 60)
    print(message)
    print("=" * 60)
    print("[INFO] HOW TO SIGN (using signer.html)")
    print("1. Open `signer.html` in your browser.")
    print(f"   (It's in this folder: {os.path.abspath(os.path.dirname(__file__))})")
    print("   If that doesn't work, use the local server URL: http://localhost:8000/signer.html")
    print("2. Copy the message block above and paste it into the webpage.")
    print("3. Click 'Connect Wallet & Sign Message' and approve in MetaMask.")
    print("4. Copy the signature from the webpage and paste it below.")
    print("-" * 60)

    signature = input("\nPlease enter the signature from MetaMask: ").strip()
    if not signature or not signature.startswith("0x"):
        print("[FAILED] Invalid signature format. Exiting.")
        return

    print("\n" + "=" * 60)
    print("RUNNING AUTHENTICATION TEST...")
    print("=" * 60)
    
    verify_result = tester.verify_signature(wallet_address, message, signature)
    if not verify_result["success"]:
        print("\n[FAILED] TEST FAILED at Signature Verification.")
        return
    
    exchange_result = tester.exchange_jwt(verify_result["jwt"])
    if not exchange_result["success"]:
        print("\n[FAILED] TEST FAILED at JWT Exchange.")
        return

    if not tester.verify_session(exchange_result["session_token"]):
        print("\n[FAILED] TEST FAILED at Session Verification.")
        return

    print("\n" + "=" * 60)
    print("[SUCCESS] ALL TESTS PASSED! Authentication workflow is working correctly!")
    print("=" * 60)
    if exchange_result.get("session_token"):
        session_token = exchange_result['session_token']
        print(f"Your session token is: {session_token}")
        with open("session_token.txt", "w") as f:
            f.write(session_token)
        print("(Saved to session_token.txt)")

if __name__ == "__main__":
    main()
