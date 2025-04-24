from typing import List, Dict, Any, Optional
from solders.pubkey import Pubkey            # type: ignore
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import MemcmpOpts
PUMPSWAP_AMM_ID = Pubkey.from_string(
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
)

BASE_MINT_OFFSET   = 43
QUOTE_MINT_OFFSET  = 75

async def find_pools_by_mint(
    client: AsyncClient,
    base_mint: str,
    quote_mint: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    each result item:  { "pubkey": <pool PDA str>, "account": <raw account> }
    """
    base_pk = Pubkey.from_string(base_mint)

    filters = [MemcmpOpts(offset=BASE_MINT_OFFSET, bytes=str(base_pk))]

    if quote_mint:
        quote_pk = Pubkey.from_string(quote_mint)
        filters.append(
            MemcmpOpts(offset=QUOTE_MINT_OFFSET, bytes=str(quote_pk))
        )

    resp = await client.get_program_accounts(
        pubkey=PUMPSWAP_AMM_ID,
        commitment="confirmed",
        encoding="base64",
        filters=filters,
    )

    return [
        {"pubkey": str(acc.pubkey), "account": acc.account}
        for acc in resp.value
    ]
