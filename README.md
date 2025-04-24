# PumpSwapAMM

**Python SDK + optional CLI for Pump.fun’s PumpSwap AMM on Solana**

Trade, create, and manage - Pools and Tokens.
The module implements ways to fetch pool keys and price or account reserves.

Tip wallet: `3oFDwxVtZEpSGeNgdWRiJtNiArv4k9FiMsMz3yjudgeS`

**Thanks 💙**

**Discord: [FLOCK4H.CAVE](https://discord.gg/thREUECv2a)**, **Telegram: [FLOCK4H.CAVE](https://t.me/flock4hcave)**

**Telegram private handle: @dubskii420**

<img src="https://github.com/user-attachments/assets/d655c153-0056-47fc-8314-6f919f18ed6d" width="256" />

# Setup

**Most convenient:**

```
  $ pip install PumpSwapAMM
```

**For development:**

```
  $ git clone https://github.com/FLOCK4H/PumpSwapAMM
  $ cd PumpSwapAMM
  $ pip install .
```

# [NEW] PumpSwapCLI

<div align="center">
  
![gdfgdgfdgdfgdf](https://github.com/user-attachments/assets/548575ae-714e-43c4-b717-f8d2fc768ee1)

</div>

1. Create tokens via Metaplex, mint & modify authorities via user-friendly CLI application
2. Deploy and manage PumpSwap Liquidity Pools including:
- Withdraw
- Deposit
- Create_Pool
3. Trade on PumpSwap: buy and sell tokens

**How to setup:**

`pip install PumpSwapAMM` for quick install of the CLI + library
Use command `pumpswap` alone to get into CLI, but first grab your Bunny.net (if creating tokens) credentials, 
then make sure to create .env file with these fields:

```
ACCESS_KEY=bunny-access-key
STORAGE_ZONE_NAME=bunny-storage-zone-name
PRIVATE_KEY=your-solana-private-key
RPC_URL="https://mainnet.helius-rpc.com/?api-key=your-api-key"
REGION= 
```

# Usage

**Check out the `example.py` and `example_pool.py` scripts for a plug&play implementation**

```python
class PumpSwap(
    async_client: AsyncClient,
    signer: Keypair
)

(method) def buy(
    pool_data: dict,
    sol_amount: float,
    slippage_pct: float,
    fee_sol: float
) -> Coroutine[Any, Any, bool]
Args:
    pool_data: dict
    sol_amount: float
    slippage_pct: float
    fee_sol: float
Returns:
    bool: True if successful, False otherwise

(method) def sell(
    pool_data: dict,
    sell_pct: float,
    slippage_pct: float,
    fee_sol: float
) -> Coroutine[Any, Any, bool]
Args:
    pool_data: dict
    sell_pct: float
    slippage_pct: float
    fee_sol: float
Returns:
    bool: True if successful, False otherwise

(function) def fetch_pool(
    pool: str,
    async_client: AsyncClient
) -> Coroutine[Any, Any, dict[str, Any]]

(function) def fetch_pool_base_price(
    pool_keys: Any,
    async_client: Any
) -> Coroutine[Any, Any, tuple[Decimal, Any, Any] | None]

(method) def derive_pool_address(
    creator: Pubkey,
    base_mint: Pubkey,
    quote_mint: Pubkey,
    index: int = 0
) -> Pubkey

(method) def create_pool(
    base_mint: Pubkey,
    base_amount_tokens: float,
    quote_amount_sol: float,
    decimals_base: int = 6,
    index: int = 0,
    fee_sol: float = 0.0005,
    mute: bool = False
) -> Coroutine[Any, Any, bool]

(method) def withdraw(
    pool_data: dict,
    withdraw_pct: float,
    fee_sol: float = 0.0003,
    mute: bool = False
) -> Coroutine[Any, Any, bool]

(method) def deposit(
    pool_data: dict,
    base_amount_tokens: float,
    slippage_pct: float = 1,
    fee_sol: float = 0.0003,
    sol_cap: float | None = None,
    mute: bool = False
) -> Coroutine[Any, Any, bool]
```

<h4>Examples</h4>

```python
  # 1) Initialize PumpSwap client
  client = PumpSwap(async_client, signer=async_payer_keypair)

  # Example pool: https://solscan.io/account/9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3
  pool = "9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3" # Change this to the token pool address you want to buy

  # 2) Fetch pool data
  pool_keys = await fetch_pool(pool, async_client) 
  base_price, base_balance_tokens, quote_balance_sol = await fetch_pool_base_price(pool_keys, async_client)
  decimals_base = 6 # Pump.fun mints got 6 decimals, otherwise it can be read from Pool Creation, or Mint Creation transaction

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

  await client.buy(
      pool_data,
      sol_amount=0.002,
      slippage_pct=10,
      fee_sol=0.0005,
  )

  await client.sell(
      pool_data,
      sell_pct=100,
      slippage_pct=10,
      fee_sol=0.0005,
  )
```

```python
import asyncio
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from solana.rpc.commitment import Processed
from PumpSwapAMM import PumpSwap, fetch_pool, WSOL_MINT
from PumpSwapAMM.fetch_reserves import fetch_pool_base_price

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
```

# Issues

- "get_account_info_json_parsed" may throw a 401 or 403 if you're using helius/ (any other triton) dedicated node or staked APIs

# LICENSE

**Standard MIT License**

> THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
> LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
