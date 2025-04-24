import asyncio
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from solana.rpc.commitment import Processed
from pumpswapamm.PumpSwapAMM import PumpSwap, fetch_pool, WSOL_MINT
from pumpswapamm.fetch_reserves import fetch_pool_base_price

PRIVATE_KEY  = "YOUR_PRIVATE_KEY_HERE"
RPC_ENDPOINT = "ANY_RPC_ENDPOINT" # e.g. "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY_HERE"

async_client = AsyncClient(RPC_ENDPOINT)
async_payer_keypair = Keypair.from_base58_string(PRIVATE_KEY)

async def main():
    """
        Every PumpSwapAMM function takes in 'mute' argument, 
        which is set to False by default.
        If set to True, it will not print any logs.
    """
    client = PumpSwap(async_client, signer=async_payer_keypair)
    pool_addr = None

    mint_id = "8oubm4nEgTFFa6SQWUoav9hpGt6MCrWQt5yXUBWEpump"

    # 1. create a brand-new pool
    # Comment it out when pool is already created and you just want to withdraw/ deposit (like with the one above)
    pool_addr = await client.create_pool(
        base_mint          = Pubkey.from_string(mint_id),
        base_amount_tokens = 990_000_000, # How many tokens to deposit, in this case 990_000_000 equals to 990M tokens
        quote_amount_sol   = 0.01, # How much SOL to deposit
        decimals_base      = 6,
        index              = 0,
        fee_sol            = 0.001,
    )
    if not pool_addr:
        return
    print("Pool PDA:", pool_addr)
    # Here stop the comment if so

    if not pool_addr:
        # If we didnt create the pool in this session we can still derive the pool address
        pool_addr = client.derive_pool_address(
            creator=async_payer_keypair.pubkey(),
            base_mint=Pubkey.from_string(mint_id),
            quote_mint=WSOL_MINT
        )

    pool_addr = str(pool_addr)
    print("Pool PDA:", pool_addr)

    pool_keys  = await fetch_pool(pool_addr, async_client)
    _, base_bal, quote_bal = await fetch_pool_base_price(pool_keys, async_client)

    # Compose pool data
    pool_data = {
        "pool_pubkey": Pubkey.from_string(pool_addr),
        "token_base":  Pubkey.from_string(pool_keys["base_mint"]),
        "token_quote": Pubkey.from_string(pool_keys["quote_mint"]),
        "lp_mint":     pool_keys["lp_mint"],
        "pool_base_token_account": pool_keys["pool_base_token_account"],
        "pool_quote_token_account": pool_keys["pool_quote_token_account"],
        "base_balance_tokens": base_bal,
        "quote_balance_sol":   quote_bal,
        "decimals_base":       dec_base,
    }

    # fetch decimals of the token
    mint_info = await async_client.get_account_info_json_parsed(
        Pubkey.from_string(mint_id),
        commitment=Processed
    )
    if not mint_info:
        print("Error: Failed to fetch mint info (tried to fetch token decimals).")
        return
    dec_base = mint_info.value.data.parsed['info']['decimals']

    # 2. Deposit tokens into the pool if the pool is already created
    # await client.deposit(
    #     pool_data          = pool_data,
    #     base_amount_tokens = 2_000_000,   # <- NOT SOL any more
    #     slippage_pct       = 1.0,
    #     fee_sol            = 0.0002,
    #     sol_cap            = 0.1
    # )

    print("Waiting for 15 seconds to withdraw...")
    await asyncio.sleep(15)

    # 3. Withdraw reserves from the pool
    await client.withdraw(
        pool_data     = pool_data,
        withdraw_pct  = 100,
        fee_sol       = 0.0002,
    )

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())