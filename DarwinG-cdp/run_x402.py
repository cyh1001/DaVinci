import os
import asyncio
import requests
from dotenv import load_dotenv
from eth_account import Account
from x402.clients.httpx import x402HttpxClient
from x402.clients.base import decode_x_payment_response, x402Client
import httpx

from cdp import CdpClient
from web3 import Web3
from cdp.evm_transaction_types import TransactionRequestEIP1559


load_dotenv()

# Environment variables
OPENROUTER_KEY = os.environ["OPENROUTER_KEY"]
CDP_WALLET_SECRET = os.environ["CDP_WALLET_SECRET"]  # This will be our private key for x402

LOW_WATERMARK = float(os.getenv("LOW_BALANCE_THRESHOLD", "30"))
TOPUP_AMOUNT = float(os.getenv("TOPUP_AMOUNT", "10"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MS", "60000")) // 1000

POOL_FEE_TIER       = int(os.getenv("POOL_FEE_TIER", "500"))            
TX_VALUE_ETH        = os.getenv("TX_VALUE_ETH", "0.004")

PAYMENT_PROTOCOL_ABI = [
    {
        "type": "function",
        "name": "swapAndTransferUniswapV3Native",
        "stateMutability": "payable",
        "inputs": [
            {
                "name": "details",
                "type": "tuple",
                "internalType": "struct Transfers.TransferDetails",
                "components": [
                    {"name": "recipientAmount",     "type": "uint256", "internalType": "uint256"},
                    {"name": "deadline",            "type": "uint256", "internalType": "uint256"},
                    {"name": "recipient",           "type": "address", "internalType": "address"},
                    {"name": "recipientCurrency",   "type": "address", "internalType": "address"},
                    {"name": "refundDestination",   "type": "address", "internalType": "address"},
                    {"name": "feeAmount",           "type": "uint256", "internalType": "uint256"},
                    {"name": "id",                  "type": "bytes16", "internalType": "bytes16"},
                    {"name": "operator",            "type": "address", "internalType": "address"},
                    {"name": "signature",           "type": "bytes",   "internalType": "bytes"},
                    {"name": "prefix",              "type": "bytes",   "internalType": "bytes"}
                ],
            },
            {"name": "poolFeesTier", "type": "uint24", "internalType": "uint24"}
        ],
        "outputs": []
    }
]

# Initialize CDP client and account at module level (synchronous)
cdp = CdpClient(
    api_key_id=os.environ["CDP_API_KEY_ID"],
    api_key_secret=os.environ["CDP_API_KEY_SECRET"],
    wallet_secret=os.environ["CDP_WALLET_SECRET"],
)

async def get_or_create_named_account(name="ETHGL-BUYER"):
    # try:
    acct = await cdp.evm.get_account(name=name)
    faucet_hash = await cdp.evm.request_faucet(
        address=acct.address,
        network="base-sepolia",
        token="usdc"
    ) 
    print(f"Requested funds from ETH faucet: https://sepolia.basescan.org/tx/{faucet_hash}")

    await cdp.close()
    # except Exception as e:
    #     print(f"Error getting account, creating a new one at {acct.address}")
    #     acct = await cdp.evm.create_account(name=name)
    return acct

account = asyncio.run(get_or_create_named_account())

def custom_payment_selector(accepts, network_filter=None, scheme_filter=None, max_value=None):
    """Custom payment selector for Base network"""
    return x402Client.default_payment_requirements_selector(
        accepts,
        network_filter="base-mainnet",  # Use Base mainnet
        scheme_filter=scheme_filter,
        max_value=max_value,
    )

# 1) Get OpenRouter balance
def get_openrouter_balance():
    """Get current OpenRouter account balance"""
    r = requests.get("https://openrouter.ai/api/v1/credits",
                     headers={"Authorization": f"Bearer {OPENROUTER_KEY}"})
    r.raise_for_status()
    d = r.json()["data"]
    return float(d["total_credits"]) - float(d["total_usage"])

# 2) Purchase OpenRouter credits using x402 httpx client
async def purchase_openrouter_credits_x402(amount_usd: float):
    """Purchase OpenRouter credits using x402 protocol with httpx client"""
    try:
        # Use x402HttpxClient to make protected requests
        async with x402HttpxClient(
            account=account,
            base_url="https://openrouter.ai",
            payment_requirements_selector=custom_payment_selector,
        ) as client:
            
            # Get the wallet address from CDP account
            wallet_address = account.address
            
            # Prepare the crypto purchase request using correct OpenRouter API
            purchase_data = {
                "amount": amount_usd,
                "sender": wallet_address,
                "chain_id": 8453  # Base mainnet
            }
            
            headers = {
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            }
            
            print(f"💸 Making x402 protected request to purchase ${amount_usd} credits...")
            print(f"🏦 Using wallet: {wallet_address}")
            
            # Make the x402 protected request to the correct endpoint
            # The client will automatically handle 402 responses and payments
            response = await client.post(
                "/api/v1/credits/coinbase",
                json=purchase_data,
                headers=headers
            )
            
            # Read response content
            content = await response.aread()
            
            # Check for payment response header
            if "X-Payment-Response" in response.headers:
                payment_response = decode_x_payment_response(
                    response.headers["X-Payment-Response"]
                )
                print(f"💳 Payment transaction hash: {payment_response['transaction']}")
            
            if response.status_code == 200:
                try:
                    result = response.json() if hasattr(response, 'json') else eval(content.decode())
                    return {
                        "success": True,
                        "transaction_id": result.get("transaction_id"),
                        "amount": amount_usd,
                        "message": f"Successfully purchased ${amount_usd} in OpenRouter credits",
                        "response": content.decode()
                    }
                except:
                    return {
                        "success": True,
                        "amount": amount_usd,
                        "message": f"Purchase request completed (${amount_usd})",
                        "response": content.decode()
                    }
            else:
                return {
                    "success": False,
                    "error": f"Purchase failed with status {response.status_code}: {content.decode()}"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": f"x402 purchase error: {str(e)}"
        }

async def ensure_credits():
    """Main monitoring function using official x402 httpx client"""
    print(f"🚀 Starting x402 AI Agent Monitoring System (Official httpx Client)")
    print(f"💰 Low watermark: ${LOW_WATERMARK}")
    print(f"🔄 Top-up amount: ${TOPUP_AMOUNT}")
    print(f"⏰ Check interval: {CHECK_INTERVAL}s")
    print(f"🏦 Wallet address: {account.address}")
    print(f"📡 Starting balance monitoring loop...")

    while True:
        try:
            # Check OpenRouter balance
            bal = get_openrouter_balance()
            print(f"💳 OpenRouter balance: ${bal:.2f}")
            
            if bal < LOW_WATERMARK:
                print(f"⚠️  Balance below threshold! Initiating x402 auto-purchase...")
                
                # Use official x402 httpx client to purchase credits
                result = await purchase_openrouter_credits_x402(TOPUP_AMOUNT)
                
                if result["success"]:
                    print(f"✅ {result['message']}")
                    if result.get("transaction_id"):
                        print(f"🧾 Transaction ID: {result['transaction_id']}")
                    if result.get("response"):
                        print(f"📝 Response: {result['response']}")
                else:
                    print(f"❌ x402 purchase failed: {result['error']}")
                
                # Wait before checking balance again
                print(f"⏳ Waiting 30s before next balance check...")
                await asyncio.sleep(30)
            else:
                print(f"✅ Balance sufficient (${bal:.2f} >= ${LOW_WATERMARK})")
            
            # Check again in specified interval
            print(f"😴 Sleeping for {CHECK_INTERVAL}s until next check...")
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"🚨 Error in monitoring loop: {e}")
            print(f"🔄 Retrying in 30s...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(ensure_credits())
