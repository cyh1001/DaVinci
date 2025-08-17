import asyncio
from cdp import CdpClient
from dotenv import load_dotenv

load_dotenv()

async def main():
    async with CdpClient() as cdp:
        token_balances = await cdp.evm.list_token_balances(
            address="0xE7a09AdBd6D3E635b1D5FAe35AF67b8723F902A5",
            network="ethereum",
        )

        # print(f"Found {len(result.balances)} token balances:")
        for balance in token_balances.balances:
            print(f"Token contract address: {balance.token.contract_address}")
            print(f"Balance amount: {balance.amount.amount}")
            print(f"Balance decimals: {balance.amount.decimals}")
            print("---")

asyncio.run(main())