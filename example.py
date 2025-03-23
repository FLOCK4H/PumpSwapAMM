import asyncio
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore

from PumpSwapAMM import PumpSwap

PRIVATE_KEY  = "YOUR_PRIVATE_KEY_HERE"
RPC_ENDPOINT = "YOUR_RPC_ENDPOINT_HERE" # e.g. "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY_HERE"
WSOL_MINT    = Pubkey.from_string("So11111111111111111111111111111111111111112")

async_client = AsyncClient(RPC_ENDPOINT)
async_payer_keypair = Keypair.from_base58_string(PRIVATE_KEY)

async def main():
    """
        NOTE:
        In an application scenario, the data below can be collected by deserializing program data from the PUMPSWAPAMM program logs LIVE
        Or by fetching the pool state and account balances, which is on the way 🌚
    """
    client = PumpSwap(async_client, signer=async_payer_keypair)

    base_balance_tokens = 887023845585680 / 1e6
    quote_balance_sol   = 21491509488 / 1e9
    decimals_base       = 6

    # Example pool: some mint/WSOL
    pool_data = {
        "pool_pubkey": Pubkey.from_string("9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3"),
        "token_base": Pubkey.from_string("x6X658KaETkoRYTxvsft8sdFHW1xt4ykeyzcRGtpump"),  # some mint
        "token_quote": WSOL_MINT, # we support only WSOL as quote token
        "pool_base_token_account": "3zAk4yo8JsBUTwNoL8amzxzX8ntG5kZbwnrgjArpFuCD",
        "pool_quote_token_account": "9XuBJdRaTciFs4sVHPYn5T7mcBJqfqYaYzubSYmLjFE9",
        "base_balance_tokens": base_balance_tokens, # poolBaseTokenReserves
        "quote_balance_sol": quote_balance_sol, # poolQuoteTokenReserves
        "decimals_base": decimals_base # this can be read from PoolCreation
    }

    await client.buy(
        pool_data,
        sol_amount=0.002,
        slippage_pct=10,
        fee_sol=0.0005,
    )

    print("Waiting 10 seconds...")
    await asyncio.sleep(10)

    await client.sell(
        pool_data,
        sell_pct=100,
        slippage_pct=10,
        fee_sol=0.0005,
    )

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())