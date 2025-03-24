# PumpSwapAMM

**This module allows making Buy and Sell transactions using Solana & Solders**, the current state of the module aims for an app integration rather than a standalone CLI application. 
The data necessary for making the swap can be fetched on the fly by for example capturing relevant logs such as mint creation, pool creation, buys and sells via a `logsSubscribe` Solana's Standard Websocket method.

# Setup

```
  $ pip install solana==0.35.1 solders==0.21.0
```

# Usage

**Check out the `example.py` script for a plug&play implementation**

**The pool data structure:**

```python
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
```

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

# TODO

❎ Fetch pool account state using PumpSwap AMM layouts
- example data: https://solscan.io/account/9NXBQSt63ZZcw3e4DhbDPGP2FjnwW3aDJWEXRwcGEsN3#anchorData

❎ Find pool account balances

# NOTE

This is an early stage of the module, please submit any errors to the [Issues](https://github.com/FLOCK4H/PumpSwapAMM/issues) page.
