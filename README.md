# PumpSwapAMM

**Trade tokens on the PumpSwap AMM using Python, Solders and Solana.**

All you need is a pool address, and eventually token decimals if mint wasn't created on Pump.fun (but via metaplex for example).
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
```

<h4>Examples</h4>

```python
  # 1) Initialize PumpSwap client
  client = PumpSwap(async_client, signer=async_payer_keypair)

  # Example pool: https://solscan.io/account/9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3
  pool = "9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3"

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

# TODO

❎ Fetch pool account state using PumpSwap AMM layouts
- example data: https://solscan.io/account/9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3#anchorData

❎ Find pool account balances

# NOTE

This is an early stage of the module, please submit any errors to the [Issues](https://github.com/FLOCK4H/PumpSwapAMM/issues) page.
