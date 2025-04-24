import traceback
from solana.rpc.commitment import Processed
from solders.pubkey import Pubkey # type: ignore
from decimal import Decimal

async def async_get_pool_reserves(pool_keys, async_client):
    try:
        vault_quote = Pubkey.from_string(pool_keys["pool_quote_token_account"])
        vault_base = Pubkey.from_string(pool_keys["pool_base_token_account"])

        accounts_resp = await async_client.get_multiple_accounts_json_parsed(
            [vault_quote, vault_base], 
            commitment=Processed
        )
        accounts_data = accounts_resp.value

        account_quote = accounts_data[0]
        account_base = accounts_data[1]
        
        quote_balance = account_quote.data.parsed['info']['tokenAmount']['uiAmount']
        base_balance = account_base.data.parsed['info']['tokenAmount']['uiAmount']
        
        if quote_balance is None or base_balance is None:
            print("Error: One of the account balances is None.")
            return None, None
        
        return base_balance, quote_balance

    except Exception as exc:
        print(f"Error fetching pool reserves: {exc}")
        traceback.print_exc()
        return None, None
    
async def fetch_pool_base_price(pool_keys, async_client):
    balance_base, balance_quote = await async_get_pool_reserves(pool_keys, async_client)
    if balance_base is None or balance_quote is None:
        print("Error: One of the account balances is None.")
        return None
    price = Decimal(balance_quote) / Decimal(balance_base)
    return (price, balance_base, balance_quote)


