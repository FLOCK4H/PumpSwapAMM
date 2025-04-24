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

```
  $ git clone https://github.com/FLOCK4H/PumpSwapAMM
  $ cd PumpSwapAMM
  $ pip install .
```

# NEW

<div align="center">
  
![gdfgdgfdgdfgdf](https://github.com/user-attachments/assets/548575ae-714e-43c4-b717-f8d2fc768ee1)

</div>

**How to setup:**

`pip install PumpSwapAMM` for quick install of the CLI + library
Use command `pumpswap` alone to get into CLI, but first grab your Bunny.net (if creating tokens) credentials, 
then make sure to create .env file with these fields:

# Create .env file in your current working dir and add the following:
# ACCESS_KEY=bunny-access-key
# STORAGE_ZONE_NAME=bunny-storage-zone-name
# PRIVATE_KEY=your-solana-private-key
# RPC_URL="https://mainnet.helius-rpc.com/?api-key=your-api-key"
# REGION= 



# Usage

**Check out the `example.py` script for a plug&play implementation**

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

# Issues

- "get_account_info_json_parsed" may throw a 401 or 403 if you're using helius/ (any other triton) dedicated node or staked APIs

# LICENSE

**Standard MIT License**

> THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
> LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
