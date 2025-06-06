import asyncio
import traceback
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore

from PumpSwapAMM import PumpSwap, fetch_pool_state
from solana.rpc.commitment import Processed

API_KEY = ""

PRIVATE_KEY  = ""
RPC_ENDPOINT = "https://mainnet.helius-rpc.com/?api-key=" + API_KEY
async_client = AsyncClient(RPC_ENDPOINT)
async_payer_keypair = Keypair.from_base58_string(PRIVATE_KEY)

async def main():
    # 1) Initialize PumpSwap client
    client = PumpSwap(async_client, signer=async_payer_keypair)

    # Example pool: https://solscan.io/account/8HmuBwTTYiLZcxUpUBwx4axwyogiaTwmhxyvE5qjc4ku
    pool = "FSmcuAztqvA68xwrae1gxuPgwbFJwjNYQ9UU3qAXG2mA"

    # For getting pool out of mint see pumpswapcli/psa_utils.py
    mint = "4enWCbYyjTrvZPZzNiXi53CLqYVquLt4Z6MABKM3pump"

    # 2) Fetch pool data
    pool_keys, pool_type = await fetch_pool_state(pool, async_client) 
    base_price, base_balance_tokens, quote_balance_sol = await client.fetch_pool_base_price(pool)
    # fetch decimals of the token
    mint_info = await async_client.get_account_info_json_parsed(
        Pubkey.from_string(mint),
        commitment=Processed
    )
    if not mint_info:
        print("Error: Failed to fetch mint info (tried to fetch token decimals).")
        return
    dec_base = mint_info.value.data.parsed['info']['decimals']

    # 3) Prepare pool data
    pool_data = {
        "pool_pubkey": Pubkey.from_string(pool),
        "token_base": Pubkey.from_string(pool_keys["base_mint"]),
        "token_quote": Pubkey.from_string(pool_keys["quote_mint"]),
        "pool_base_token_account": pool_keys["pool_base_token_account"],
        "pool_quote_token_account": pool_keys["pool_quote_token_account"],
        "base_balance_tokens": base_balance_tokens,
        "quote_balance_sol": quote_balance_sol,
        "decimals_base": dec_base,
    }
    if pool_type == "NEW":
        pool_data["coin_creator"] = Pubkey.from_string(pool_keys["coin_creator"])
    else:
        print("Pool is old, which means tx may return custom program error: 3003 | Failed to deserialize the account")

    try:
    # 4) Buy
        await client.buy(
            pool_data,
            sol_amount=0.002,
            pool_type=pool_type,
            slippage_pct=10,
            fee_sol=0.0005
            )
    except Exception as e:
        traceback.print_exc()
        print(e)

    print("Waiting 10 seconds...")
    await asyncio.sleep(10)

    # 5) Sell
    await client.sell(
        pool_data,
        sell_pct=100,
        pool_type=pool_type,
        slippage_pct=10,
        fee_sol=0.0005,
    )

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())