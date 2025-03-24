import asyncio
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore

from PumpSwapAMM import PumpSwap, fetch_pool
from fetch_reserves import fetch_pool_base_price

PRIVATE_KEY  = "YOUR_PRIVATE_KEY_HERE"
RPC_ENDPOINT = "ANY_RPC_ENDPOINT" # e.g. "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY_HERE"
WSOL_MINT    = Pubkey.from_string("So11111111111111111111111111111111111111112")

async_client = AsyncClient(RPC_ENDPOINT)
async_payer_keypair = Keypair.from_base58_string(PRIVATE_KEY)

async def main():
    # 1) Initialize PumpSwap client
    client = PumpSwap(async_client, signer=async_payer_keypair)

    # Example pool: https://solscan.io/account/9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3
    pool = "9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3"

    # 2) Fetch pool data
    pool_keys = await fetch_pool(pool, async_client) 
    base_price, base_balance_tokens, quote_balance_sol = await fetch_pool_base_price(pool_keys, async_client)
    decimals_base       = 6 # Pump.fun mints got 6 decimals, otherwise it can be read from Pool Creation, or Mint Creation transaction

    # 3) Prepare pool data
    pool_data = {
        "pool_pubkey": Pubkey.from_string(pool),
        "token_base": Pubkey.from_string(pool_keys["base_mint"]),
        "token_quote": Pubkey.from_string(pool_keys["quote_mint"]),
        "pool_base_token_account": pool_keys["pool_base_token_account"],
        "pool_quote_token_account": pool_keys["pool_quote_token_account"],
        "base_balance_tokens": base_balance_tokens,
        "quote_balance_sol": quote_balance_sol,
        "decimals_base": decimals_base
    }

    # 4) Buy
    await client.buy(
        pool_data,
        sol_amount=0.002,
        slippage_pct=10,
        fee_sol=0.0005,
    )

    print("Waiting 10 seconds...")
    await asyncio.sleep(10)

    # 5) Sell
    await client.sell(
        pool_data,
        sell_pct=100,
        slippage_pct=10,
        fee_sol=0.0005,
    )

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())