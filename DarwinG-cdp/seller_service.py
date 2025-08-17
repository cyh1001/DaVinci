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

# ---------- Environment ----------
OPENROUTER_KEY    = os.environ["OPENROUTER_KEY"]
CDP_API_KEY_ID    = os.environ["CDP_API_KEY_ID"]
CDP_API_KEY_SECRET= os.environ["CDP_API_KEY_SECRET"]
CDP_WALLET_SECRET = os.environ["CDP_WALLET_SECRET"]
CDP_WALLET_NAME   = os.getenv("CDP_WALLET_NAME", "ETHGL-CDP")

# Accept: "base", "base-mainnet", or "base-sepolia"
X402_NETWORK_ENV  = os.getenv("X402_NETWORK", "base").strip().lower()
NETWORK = "base" if X402_NETWORK_ENV in ("base", "base-mainnet") else "base-sepolia"

PRICE_0_1 = float(os.getenv("PRICE_0_1", "0.1"))
PRICE_10  = float(os.getenv("PRICE_10",  "10"))
PRICE_25  = float(os.getenv("PRICE_25",  "25"))
PRICE_50  = float(os.getenv("PRICE_50",  "50"))

# ---------- CDP wallet (seller receiving address) ----------
cdp = CdpClient(api_key_id=CDP_API_KEY_ID,
                api_key_secret=CDP_API_KEY_SECRET,
                wallet_secret=CDP_WALLET_SECRET)

async def get_or_create_named_account(name: str):
    try:
        return await cdp.evm.get_account(name=name)
    except Exception:
        return await cdp.evm.create_account(name=name)

account = asyncio.run(get_or_create_named_account(CDP_WALLET_NAME))
SELLER_ADDRESS = account.address  # receives the buyer's x402 payment

# ---------- FastAPI ----------
app = FastAPI(title="x402 Seller TopUp for OpenRouter", version="0.2.0")

# Helper: protect a path for a fixed price
def add_paid_route(path: str, price_usd: float):
    app.middleware("http")(
        require_payment(
            path=path,                               # IMPORTANT: path goes here, not on the decorator
            price=f"${price_usd}",
            pay_to_address=SELLER_ADDRESS,
            network=NETWORK                          # "base" or "base-sepolia"
        )
    )

# Protect these top-up endpoints via x402
add_paid_route("/topup/0.1", PRICE_0_1)
add_paid_route("/topup/10",  PRICE_10)
add_paid_route("/topup/25",  PRICE_25)
add_paid_route("/topup/50",  PRICE_50)

@app.get("/health")
async def health():
    return {"ok": True, "network": NETWORK, "pay_to": SELLER_ADDRESS}

# ---------- OpenRouter balance ----------
def get_openrouter_balance() -> float:
    r = requests.get(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()["data"]
    return float(d["total_credits"]) - float(d["total_usage"])

# ---------- Create OpenRouter charge (MAINNET only) ----------
def create_openrouter_charge(amount_usd: float, sender_addr: str):
    # OpenRouter supports Base MAINNET (8453) for crypto purchases
    payload = {"amount": amount_usd, "sender": sender_addr, "chain_id": 8453}
    r = requests.post(
        "https://openrouter.ai/api/v1/credits/coinbase",
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"]["web3_data"]["transfer_intent"]

def _parse_deadline(deadline_field):
    if isinstance(deadline_field, int):
        return deadline_field
    return int(datetime.fromisoformat(str(deadline_field).replace("Z", "+00:00")).timestamp())

async def fulfill_charge_on_base(transfer_intent: dict, pool_fee_tier: int = 500, eth_value: float = 0.004):
    call = transfer_intent["call_data"]
    meta = transfer_intent["metadata"]
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
    func_selector = w3.keccak(text="swapAndTransferUniswapV3Native((uint256,uint256,address,address,address,uint256,bytes16,address,bytes,bytes),uint24)")[:4]
    encoded_args = w3.codec.encode_abi(
        ["(uint256,uint256,address,address,address,uint256,bytes16,address,bytes,bytes)", "uint24"],
        [details_tuple, pool_fee_tier],
    )
    full_data = "0x" + (func_selector + encoded_args).hex()

    tx = TransactionRequestEIP1559(
        to=contract_addr,
        data=full_data,
        value=Web3.to_wei(eth_value, "ether"),  # needs a little Base ETH
    )

    resp = await cdp.evm.send_transaction(
        tx=tx,
        network=NETWORK  # "base" or "base-sepolia"
    )
    return resp["hash"]

# ---------- Top-up worker ----------
async def _do_topup(amount: float):
    # On testnet, don't call OpenRouter (mainnet-only endpoint). Just prove x402 works.
    if NETWORK == "base-sepolia":
        return {
            "paid": True,
            "testnet": True,
            "skipped_openrouter": True,
            "credited_amount_usd": amount,
            "hint": "Switch X402_NETWORK=base for real top-ups"
        }

    # Mainnet flow: create charge + fulfill on Base (8453)
    intent = create_openrouter_charge(amount_usd=amount, sender_addr=SELLER_ADDRESS)
    tx_hash = await fulfill_charge_on_base(intent, pool_fee_tier=500, eth_value=0.004)

    # Optional: brief delay before checking balance (OpenRouter API may be cached)
    time.sleep(15)
    try:
        new_bal = get_openrouter_balance()
    except Exception:
        new_bal = None

    return {"tx_hash": tx_hash, "credited_amount_usd": amount, "new_balance": new_bal}

# Paid endpoints — the middleware will verify/settle the x402 payment before these run
@app.post("/topup/0.1")
async def topup_0_1():
    return await _do_topup(PRICE_0_1)

@app.post("/topup/10")
async def topup_10():
    return await _do_topup(PRICE_10)

@app.post("/topup/25")
async def topup_25():
    return await _do_topup(PRICE_25)

@app.post("/topup/50")
async def topup_50():
    return await _do_topup(PRICE_50)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4021)
