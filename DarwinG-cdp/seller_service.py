# seller_service.py  (Base mainnet)
import os, asyncio, time
from datetime import datetime
import requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from x402.fastapi.middleware import require_payment
from cdp import CdpClient
from cdp.evm_transaction_types import TransactionRequestEIP1559
from web3 import Web3

load_dotenv()

# ---- Required env
OPENROUTER_KEY    = os.environ["OPENROUTER_KEY"]
CDP_API_KEY_ID    = os.environ["CDP_API_KEY_ID"]
CDP_API_KEY_SECRET= os.environ["CDP_API_KEY_SECRET"]
CDP_WALLET_SECRET = os.environ["CDP_WALLET_SECRET"]
CDP_WALLET_NAME   = os.getenv("CDP_WALLET_NAME", "ETHGL-CDP")

# ---- Pricing (USD)
PRICE_01 = float(os.getenv("PRICE_0_1", "0.1"))
PRICE_10 = float(os.getenv("PRICE_10", "10"))
PRICE_25 = float(os.getenv("PRICE_25", "25"))
PRICE_50 = float(os.getenv("PRICE_50", "50"))

# ---- CDP client & Seller wallet (EVM EOA) reused for onchain calls
cdp = CdpClient(api_key_id=CDP_API_KEY_ID, api_key_secret=CDP_API_KEY_SECRET, wallet_secret=CDP_WALLET_SECRET)

async def _get_or_create_account(name: str):
    try:
        return await cdp.evm.get_account(name=name)
    except Exception:
        return await cdp.evm.create_account(name=name)

account = asyncio.run(_get_or_create_account(CDP_WALLET_NAME))
SELLER_ADDRESS = account.address

# ---- FastAPI
app = FastAPI(title="x402 Seller (OpenRouter top-up)", version="1.0")

NETWORK = "base" if os.getenv("X402_NETWORK", "base-mainnet") in ("base", "base-mainnet") else "base-sepolia"
app.middleware("http")(
    require_payment(
        path="/topup/10",
        price=f"${PRICE_10}",
        pay_to_address=SELLER_ADDRESS,
        network=NETWORK,
    )
)

app.middleware("http")(
    require_payment(
        path="/topup/25",
        price=f"${PRICE_25}",
        pay_to_address=SELLER_ADDRESS,
        network=NETWORK,
    )
)

app.middleware("http")(
    require_payment(
        path="/topup/50",
        price=f"${PRICE_50}",
        pay_to_address=SELLER_ADDRESS,
        network=NETWORK,
    )
)

@app.get("/health")
async def health():
    return {"ok": True, "network": "base", "pay_to": SELLER_ADDRESS}

# ---- OpenRouter balance
def get_openrouter_balance() -> float:
    r = requests.get("https://openrouter.ai/api/v1/credits",
                     headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                     timeout=30)
    r.raise_for_status()
    d = r.json()["data"]
    return float(d["total_credits"]) - float(d["total_usage"])

# ---- Create charge with OpenRouter (mainnet Base only per docs)
def create_openrouter_charge(amount_usd: float, sender_addr: str):
    payload = {"amount": amount_usd, "sender": sender_addr, "chain_id": 8453}
    r = requests.post(
        "https://openrouter.ai/api/v1/credits/coinbase",
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if r.status_code >= 400:
        # Log full body so you can see why (bad sender, etc.)
        raise RuntimeError(f"OpenRouter charge failed: {r.status_code} {r.text}")
    return r.json()["data"]["web3_data"]["transfer_intent"]

def _parse_deadline(deadline_field):
    if isinstance(deadline_field, int):
        return deadline_field
    return int(datetime.fromisoformat(deadline_field.replace("Z","+00:00")).timestamp())

async def _fulfill_on_base(intent: dict, pool_fee_tier: int = 500, eth_value: float = 0.004):
    call = intent["call_data"]; meta = intent["metadata"]
    contract_addr = meta["contract_address"]
    details_tuple = (
        int(call["recipient_amount"]),
        _parse_deadline(call["deadline"]),
        Web3.to_checksum_address(call["recipient"]),
        Web3.to_checksum_address(call["recipient_currency"]),
        Web3.to_checksum_address(call["refund_destination"]),
        int(call["fee_amount"]),
        bytes.fromhex(call["id"].removeprefix("0x")),
        Web3.to_checksum_address(call["operator"]),
        bytes.fromhex(call["signature"].removeprefix("0x")),
        bytes.fromhex(call["prefix"].removeprefix("0x")),
    )
    w3 = Web3()
    selector = w3.keccak(text="swapAndTransferUniswapV3Native((uint256,uint256,address,address,address,uint256,bytes16,address,bytes,bytes),uint24)")[:4]
    args = w3.codec.encode_abi(
        ["(uint256,uint256,address,address,address,uint256,bytes16,address,bytes,bytes)", "uint24"],
        [details_tuple, pool_fee_tier],
    )
    data = "0x" + (selector + args).hex()

    tx = TransactionRequestEIP1559(to=contract_addr, data=data, value=Web3.to_wei(eth_value, "ether"))
    resp = await cdp.evm.send_transaction(tx=tx, network="base")  # mainnet
    return resp["hash"]

async def _do_topup(amount: float):
    # 1) Build transfer intent with OpenRouter (Base mainnet only)
    intent = create_openrouter_charge(amount_usd=amount, sender_addr=SELLER_ADDRESS)
    # 2) Fulfill on Base
    tx_hash = await _fulfill_on_base(intent, pool_fee_tier=500, eth_value=0.004)
    # 3) Balance can lag briefly
    time.sleep(15)
    try:
        new_bal = get_openrouter_balance()
    except Exception:
        new_bal = None
    return {"tx_hash": tx_hash, "credited_amount_usd": amount, "new_balance": new_bal}

@app.post("/topup/0.1")
async def topup_01(): return await _do_topup(PRICE_01)

@app.post("/topup/10")
async def topup_10(): return await _do_topup(PRICE_10)

@app.post("/topup/25")
async def topup_25(): return await _do_topup(PRICE_25)

@app.post("/topup/50")
async def topup_50(): return await _do_topup(PRICE_50)

if __name__ == "__main__":
    import uvicorn
    print("✅ Running Seller on Base mainnet with CDP facilitator")
    uvicorn.run(app, host="0.0.0.0", port=4021)
