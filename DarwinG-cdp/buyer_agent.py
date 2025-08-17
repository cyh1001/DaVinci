# buyer_agent.py (Base mainnet)
import os, asyncio, time, requests
from dotenv import load_dotenv
import httpx
from eth_account import Account
from x402.clients.httpx import x402HttpxClient

# Optional CDP fallback
from cdp import CdpClient
from cdp.evm_local_account import EvmLocalAccount

load_dotenv()

OPENROUTER_KEY   = os.environ["OPENROUTER_KEY"]
SELLER_BASE_URL  = os.getenv("SELLER_BASE_URL", "http://localhost:4021")
LOW_WATERMARK    = float(os.getenv("LOW_BALANCE_THRESHOLD", "20"))
TOPUP_AMOUNT     = float(os.getenv("TOPUP_AMOUNT", "0.1"))
CHECK_INTERVAL_S = int(os.getenv("CHECK_INTERVAL_MS", "60000")) // 1000

BUYER_PRIVATE_KEY= os.getenv("BUYER_PRIVATE_KEY", "").strip()

CDP_API_KEY_ID    = os.getenv("CDP_API_KEY_ID", "")
CDP_API_KEY_SECRET= os.getenv("CDP_API_KEY_SECRET", "")
CDP_WALLET_SECRET = os.getenv("CDP_WALLET_SECRET", "")
BUYER_WALLET_NAME = os.getenv("BUYER_WALLET_NAME", "ETHGL-BUYER")

def get_openrouter_balance() -> float:
    r = requests.get("https://openrouter.ai/api/v1/credits",
                     headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                     timeout=20)
    r.raise_for_status()
    d = r.json()["data"]
    return float(d["total_credits"]) - float(d["total_usage"])

async def get_signer():
    if BUYER_PRIVATE_KEY:
        eoa = Account.from_key(BUYER_PRIVATE_KEY)
        print(f"🪪 Buyer address: {eoa.address} (EOA)")
        return eoa
    if CDP_API_KEY_ID and CDP_API_KEY_SECRET and CDP_WALLET_SECRET:
        cdp = CdpClient(api_key_id=CDP_API_KEY_ID, api_key_secret=CDP_API_KEY_SECRET, wallet_secret=CDP_WALLET_SECRET)
        try:
            acct = await cdp.evm.get_account(name=BUYER_WALLET_NAME)
        except Exception:
            acct = await cdp.evm.create_account(name=BUYER_WALLET_NAME)
        signer = EvmLocalAccount(acct)
        print(f"🪪 Buyer address: {signer.address} (CDP {BUYER_WALLET_NAME})")
        return signer
    raise RuntimeError("Provide BUYER_PRIVATE_KEY or CDP_* for a signer")

async def call_seller_topup(amount: float, signer):
    path = f"/topup/{amount}"
    # Preflight (see the raw 402)
    async with httpx.AsyncClient(base_url=SELLER_BASE_URL, timeout=30) as plain:
        pre = await plain.post(path)
        print(f"📬 Preflight {pre.status_code}: {pre.text}")

    # Pay + retry automatically
    async with x402HttpxClient(account=signer, base_url=SELLER_BASE_URL) as client:
        resp = await client.post(path)
        body = (await resp.aread()).decode(errors="ignore")
        print(f"📨 After x402 {resp.status_code}: {body}")
        return resp.status_code, body

async def monitor():
    signer = await get_signer()
    print(f"🚀 Buyer monitor | low=${LOW_WATERMARK}, top-up=${TOPUP_AMOUNT}, check={CHECK_INTERVAL_S}s")
    while True:
        try:
            bal = get_openrouter_balance()
            print(f"💳 OpenRouter balance: ${bal:.2f}")
            if bal < LOW_WATERMARK:
                print("⚠️  Below threshold – calling Seller (x402)...")
                code, body = await call_seller_topup(TOPUP_AMOUNT, signer)
                print(f"➡️  Seller responded [{code}]")
                time.sleep(10)  # let Seller finish onchain + OR credit
            else:
                print(f"✅ OK (${bal:.2f} ≥ ${LOW_WATERMARK})")
        except Exception as e:
            print("🚨 Monitor loop error:", e)
        await asyncio.sleep(CHECK_INTERVAL_S)

if __name__ == "__main__":
    asyncio.run(monitor())
