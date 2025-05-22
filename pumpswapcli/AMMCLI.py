import asyncio
from typing import Optional
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts, TokenAccountOpts
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit # type: ignore
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey # type: ignore
from solders.transaction import VersionedTransaction # type: ignore
from solders.message import MessageV0 # type: ignore
try: from .metaplex_api import build_transfer_ix;
except: from metaplex_api import build_transfer_ix;
from solana.rpc.commitment import Processed, Confirmed
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    sync_native,
    SyncNativeParams,
    close_account,
    CloseAccountParams,
)
from construct import Struct as cStruct, Byte, Int16ul, Int64ul, Bytes
from decimal import Decimal

async def agpr(pool_keys, async_client):
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
        return None, None
    
CREATOR_VAULT_SEED  = b"creator_vault"
def derive_creator_vault(creator: Pubkey, quote_mint: Pubkey) -> tuple[Pubkey, Pubkey]:
    vault_auth, bump = Pubkey.find_program_address(
        [CREATOR_VAULT_SEED, bytes(creator)],
        PUMPSWAP_PROGRAM_ID
    )
    vault_ata = get_associated_token_address(vault_auth, quote_mint)
    return vault_ata, vault_auth

async def fetch_pool_base_price(pool_keys, async_client):
    balance_base, balance_quote = await agpr(pool_keys, async_client)
    if balance_base is None or balance_quote is None:
        print("Error: One of the account balances is None.")
        return None
    price = Decimal(balance_quote) / Decimal(balance_base)
    return (price, balance_base, balance_quote)

POOL_COMPUTE_BUDGET = 200_000
UNIT_COMPUTE_BUDGET = 120_000

WSOL_MINT           = Pubkey.from_string("So11111111111111111111111111111111111111112")
PUMPSWAP_PROGRAM_ID = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
TOKEN_PROGRAM_PUB   = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN    = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_PROGRAM_ID   = Pubkey.from_string("11111111111111111111111111111111")
EVENT_AUTHORITY     = Pubkey.from_string("GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR")

GLOBAL_CONFIG_PUB   = Pubkey.from_string("ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw")
PROTOCOL_FEE_RECIP  = Pubkey.from_string("7VtfL8fvgNfhz17qKRMjzQEXgbdpnHHHQRh54R9jP2RJ")
PROTOCOL_FEE_RECIP_ATA = Pubkey.from_string("7GFUN3bWzJMKMRZ34JLsvcqdssDbXnp589SiE33KVwcC")
TOKEN_2022_PROGRAM_PUB = Pubkey.from_string(
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
)
CREATE_POOL_DISCRIM = b"\xe9\x92\xd1\x8e\xcf\x68\x40\xbc"
BUY_INSTR_DISCRIM = b'\x66\x06\x3d\x12\x01\xda\xeb\xea'
SELL_INSTR_DISCRIM = b"\x33\xe6\x85\xa4\x01\x7f\x83\xad"
WITHDRAW_INSTR_DISCRIM = b"\xb7\x12\x46\x9c\x94\x6d\xa1\x22"
DEPOSIT_INSTR_DISCRIM = b"\xf2\x23\xc6\x89\x52\xe1\xf2\xb6"
LAMPORTS_PER_SOL = 1_000_000_000

def get_price(base_balance_tokens: float, quote_balance_sol: float) -> float:
    if base_balance_tokens <= 0:
        return float("inf")
    return quote_balance_sol / base_balance_tokens

def convert_sol_to_base_tokens(
    sol_amount: float,
    base_balance_tokens: float,
    quote_balance_sol: float,
    decimals_base: int,
    slippage_pct: float = 0.01
):
    price = get_price(base_balance_tokens, quote_balance_sol)
    raw_tokens = sol_amount / price 
    base_amount_out = int(raw_tokens * (10**decimals_base))

    max_sol = sol_amount * (1 + slippage_pct)
    max_quote_in_lamports = int(max_sol * LAMPORTS_PER_SOL)
    return (base_amount_out, max_quote_in_lamports)

def convert_base_tokens_to_sol(
    token_amount_user: float,
    base_balance_tokens: float,
    quote_balance_sol: float,
    decimals_base: int,
    slippage_pct: float = 0.01
):
    price = get_price(base_balance_tokens, quote_balance_sol)

    base_amount_out = int(token_amount_user * (10**decimals_base))

    needed_sol = token_amount_user * price
    max_needed_sol = needed_sol * (1 + slippage_pct)
    max_quote_in_lamports = int(max_needed_sol * LAMPORTS_PER_SOL)
    return (base_amount_out, max_quote_in_lamports)

def compute_unit_price_from_total_fee(
    total_lams: int,
    compute_units: int = 120_000
) -> int:
    lamports_per_cu = total_lams / float(compute_units)
    micro_lamports_per_cu = lamports_per_cu * 1_000_000
    return int(micro_lamports_per_cu)

class PSAMM:
    def __init__(self, async_client: AsyncClient, signer: Keypair):
        self.async_client = async_client
        self.signer = signer
    
    async def close(self):
        await self.async_client.close()

    async def create_ata_if_needed(self, owner: Pubkey, mint: Pubkey):
        """
        If there's no associated token account for (owner, mint), return an
        instruction to create it. Otherwise return None.
        """
        ata = get_associated_token_address(owner, mint)
        resp = await self.async_client.get_account_info(ata)
        if resp.value is None:
            # means ATA does not exist
            return create_associated_token_account(
                payer=owner,
                owner=owner,
                mint=mint
            )
        return None

    async def _create_ata_if_needed_for_owner(
        self, payer: Pubkey, owner: Pubkey, mint: Pubkey, token_program: Pubkey = TOKEN_PROGRAM_PUB
    ):
        """
        Idempotently create an ATA whose *owner* is NOT the tx‑fee‑payer (e.g. the
        pool PDA).  It follows the same pattern as `create_ata_if_needed`.
        """
        ata = get_associated_token_address(owner, mint, token_program)
        resp = await self.async_client.get_account_info(ata)
        if resp.value is None:
            return create_associated_token_account(
                payer=payer,
                owner=owner,
                mint=mint,
                token_program_id=token_program
            )
        return None

    async def buy(
        self,
        pool_data: dict,
        sol_amount: float,      # e.g. 0.001
        slippage_pct: float,    # e.g. 1.0 => 1%
        fee_sol: float,         # total priority fee user wants to pay, e.g. 0.0005
        mute: bool = False
    ):
        """
            Args:
                pool_data: dict
                sol_amount: float
                slippage_pct: float
                fee_sol: float
            Returns:
                bool: True if successful, False otherwise
        """
        user_pubkey = self.signer.pubkey()
        base_balance_tokens = pool_data['base_balance_tokens']
        quote_balance_sol   = pool_data['quote_balance_sol']
        decimals_base       = pool_data['decimals_base']
        sol_amount = float(sol_amount)

        (base_amount_out, max_quote_amount_in) = convert_sol_to_base_tokens(
            sol_amount, base_balance_tokens, quote_balance_sol,
            decimals_base, slippage_pct
        )

        lamports_fee = int(fee_sol * LAMPORTS_PER_SOL)
        micro_lamports = compute_unit_price_from_total_fee(
            lamports_fee,
            compute_units=UNIT_COMPUTE_BUDGET
        )

        instructions = []

        instructions.append(set_compute_unit_limit(UNIT_COMPUTE_BUDGET))
        instructions.append(set_compute_unit_price(micro_lamports))
        wsol_ata_ix = await self.create_ata_if_needed(user_pubkey, pool_data['token_quote'])
        if wsol_ata_ix:
            instructions.append(wsol_ata_ix)

        wsol_ata = get_associated_token_address(user_pubkey, pool_data['token_quote'])
        system_transfer_ix = self._build_system_transfer_ix(
            from_pubkey=user_pubkey,
            to_pubkey=wsol_ata,
            lamports=max_quote_amount_in
        )
        instructions.append(system_transfer_ix)

        instructions.append(
            sync_native(
                SyncNativeParams(
                    program_id=TOKEN_PROGRAM_PUB,
                    account=wsol_ata
                )
            )
        )

        base_ata_ix = await self.create_ata_if_needed(user_pubkey, pool_data['token_base'])
        if base_ata_ix:
            instructions.append(base_ata_ix)
        instructions.append(build_transfer_ix(user_pubkey))
        coin_creator  = pool_data["coin_creator"]
        vault_ata, vault_auth = derive_creator_vault(coin_creator, pool_data['token_quote'])
        buy_ix = self._build_pumpswap_buy_ix(
            pool_pubkey = pool_data['pool_pubkey'],
            user_pubkey = user_pubkey,
            global_config = GLOBAL_CONFIG_PUB,
            base_mint    = pool_data['token_base'],
            quote_mint   = pool_data['token_quote'],
            user_base_token_ata  = get_associated_token_address(user_pubkey, pool_data['token_base']),
            user_quote_token_ata = get_associated_token_address(user_pubkey, pool_data['token_quote']),
            pool_base_token_account  = Pubkey.from_string(pool_data['pool_base_token_account']),
            pool_quote_token_account = Pubkey.from_string(pool_data['pool_quote_token_account']),
            protocol_fee_recipient   = PROTOCOL_FEE_RECIP,
            protocol_fee_recipient_ata = PROTOCOL_FEE_RECIP_ATA,
            base_amount_out = base_amount_out,
            max_quote_amount_in = max_quote_amount_in,
            vault_auth = vault_auth,
            vault_ata = vault_ata,
        )
        instructions.append(buy_ix)

        instructions.append(
            close_account(
                CloseAccountParams(
                    program_id=TOKEN_PROGRAM_PUB,
                    account=wsol_ata,
                    dest=user_pubkey,
                    owner=user_pubkey
                )
            )
        )

        latest_blockhash = await self.async_client.get_latest_blockhash()
        compiled_msg = MessageV0.try_compile(
            payer=user_pubkey,
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=latest_blockhash.value.blockhash,
        )
        transaction = VersionedTransaction(compiled_msg, [self.signer])

        opts = TxOpts(skip_preflight=True, max_retries=0)
        send_resp = await self.async_client.send_transaction(transaction, opts=opts)
        if not mute:
            print(f"Transaction sent: https://solscan.io/tx/{send_resp.value}")

        # Confirm
        confirmed = await self._await_confirm_transaction(send_resp.value)
        if not mute:
            print("Success:", confirmed)
        return confirmed

    def _build_system_transfer_ix(self, from_pubkey: Pubkey, to_pubkey: Pubkey, lamports: int):
        from solders.system_program import TransferParams, transfer
        return transfer(
            TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=lamports
            )
        )
    
    def _build_pumpswap_buy_ix(
        self,
        pool_pubkey: Pubkey,
        user_pubkey: Pubkey,
        global_config: Pubkey,
        base_mint: Pubkey,
        quote_mint: Pubkey,
        user_base_token_ata: Pubkey,
        user_quote_token_ata: Pubkey,
        pool_base_token_account: Pubkey,
        pool_quote_token_account: Pubkey,
        protocol_fee_recipient: Pubkey,
        protocol_fee_recipient_ata: Pubkey,
        base_amount_out: int,
        max_quote_amount_in: int,
        vault_auth: Pubkey,
        vault_ata: Pubkey
    ):
        """
          #1 Pool
          #2 User
          #3 Global Config
          #4 Base Mint
          #5 Quote Mint
          #6 User Base ATA
          #7 User Quote ATA
          #8 Pool Base ATA
          #9 Pool Quote ATA
          #10 Protocol Fee Recipient
          #11 Protocol Fee Recipient Token Account
          #12 Base Token Program
          #13 Quote Token Program
          #14 System Program
          #15 Associated Token Program
          #16 Event Authority
          #17 PumpSwap Program
        
          {
            base_amount_out:  u64,
            max_quote_amount_in: u64
          }
        plus an 8-byte Anchor discriminator at the front. 
        """
        from solana.transaction import AccountMeta, Instruction
        from solders.pubkey import Pubkey as SPubkey  # type: ignore
        import struct

        data = BUY_INSTR_DISCRIM + struct.pack("<QQ", base_amount_out, max_quote_amount_in)

        accs = [
            AccountMeta(pubkey=SPubkey.from_string(str(pool_pubkey)),  is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(user_pubkey)),  is_signer=True,  is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(global_config)),is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(base_mint)),    is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(quote_mint)),   is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(user_base_token_ata)),  is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(user_quote_token_ata)), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(pool_base_token_account)), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(pool_quote_token_account)),is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(protocol_fee_recipient)),   is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(protocol_fee_recipient_ata)), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(TOKEN_PROGRAM_PUB)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(TOKEN_PROGRAM_PUB)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(SYSTEM_PROGRAM_ID)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(ASSOCIATED_TOKEN)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(EVENT_AUTHORITY)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(PUMPSWAP_PROGRAM_ID)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(vault_ata)), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(vault_auth)), is_signer=False, is_writable=True),
        ]

        ix = Instruction(
            program_id=SPubkey.from_string(str(PUMPSWAP_PROGRAM_ID)),
            data=data,
            accounts=accs
        )
        return ix

    async def sell(
        self,
        pool_data: dict,
        sell_pct: float,
        slippage_pct: float, 
        fee_sol: float,
        mute: bool = False
    ):
        """
            Args:
                pool_data: dict
                sell_pct: float
                slippage_pct: float
                fee_sol: float
            Returns:
                bool: True if successful, False otherwise
        """
        user_pubkey = self.signer.pubkey()
        
        user_base_balance_f = await self._fetch_user_token_balance(str(pool_data['token_base']))
        if user_base_balance_f <= 0:
            if not mute:
                print("No base token balance, can't sell.")
            return False
        
        to_sell_amount_f = user_base_balance_f * (sell_pct / 100.0)
        if to_sell_amount_f <= 0:
            if not mute:
                print("Nothing to sell after applying percentage.")
            return False
        
        decimals_base = pool_data['decimals_base']
        base_amount_in = int(to_sell_amount_f * (10 ** decimals_base))
        
        coin_creator  = pool_data["coin_creator"]
        vault_ata, vault_auth = derive_creator_vault(coin_creator, pool_data['token_quote'])

        base_balance_tokens = pool_data['base_balance_tokens']
        quote_balance_sol   = pool_data['quote_balance_sol']
        
        price = get_price(base_balance_tokens, quote_balance_sol)
        raw_sol = to_sell_amount_f * price
        
        min_sol_out = raw_sol * (1 - slippage_pct/100.0)
        min_quote_amount_out = int(min_sol_out * LAMPORTS_PER_SOL)
        if min_quote_amount_out <= 0:
            if not mute:
                print("min_quote_amount_out <= 0. Slippage too big or no liquidity.")
            return False
        
        lamports_fee = int(fee_sol * LAMPORTS_PER_SOL)
        micro_lamports = compute_unit_price_from_total_fee(
            lamports_fee,
            compute_units=UNIT_COMPUTE_BUDGET
        )
        
        instructions = []
        instructions.append(set_compute_unit_limit(UNIT_COMPUTE_BUDGET))
        instructions.append(set_compute_unit_price(micro_lamports))
        
        wsol_ata_ix = await self.create_ata_if_needed(user_pubkey, pool_data['token_quote'])
        if wsol_ata_ix:
            instructions.append(wsol_ata_ix)
        instructions.append(build_transfer_ix(user_pubkey))
        sell_ix = self._build_pumpswap_sell_ix(
            user_pubkey = user_pubkey,
            pool_data = pool_data,
            base_amount_in = base_amount_in,
            min_quote_amount_out = min_quote_amount_out,
            protocol_fee_recipient   = PROTOCOL_FEE_RECIP,
            protocol_fee_recipient_ata = PROTOCOL_FEE_RECIP_ATA,
            vault_auth = vault_auth,
            vault_ata = vault_ata,
        )
        instructions.append(sell_ix)
        
        wsol_ata = get_associated_token_address(user_pubkey, pool_data['token_quote'])
        close_ix = close_account(
            CloseAccountParams(
                program_id = TOKEN_PROGRAM_PUB,
                account = wsol_ata,
                dest = user_pubkey,
                owner = user_pubkey
            )
        )
        instructions.append(close_ix)
        
        latest_blockhash = await self.async_client.get_latest_blockhash()
        compiled_msg = MessageV0.try_compile(
            payer=user_pubkey,
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=latest_blockhash.value.blockhash
        )
        transaction = VersionedTransaction(compiled_msg, [self.signer])
        
        opts = TxOpts(skip_preflight=True, max_retries=0)
        send_resp = await self.async_client.send_transaction(transaction, opts=opts)
        if not mute:
            print(f"Transaction sent: https://solscan.io/tx/{send_resp.value}")
        
        confirmed = await self._await_confirm_transaction(send_resp.value)
        if not mute:
            print("Success:", confirmed)
        return confirmed

    def _build_pumpswap_sell_ix(
        self,
        user_pubkey: Pubkey,
        pool_data: dict,
        base_amount_in: int,
        min_quote_amount_out: int,
        protocol_fee_recipient: Pubkey,
        protocol_fee_recipient_ata: Pubkey,
        vault_auth: Pubkey,
        vault_ata: Pubkey
    ):
        """
        Accounts (17 total):
          #1  Pool
          #2  User
          #3  Global Config
          #4  Base Mint
          #5  Quote Mint
          #6  User Base Token Account
          #7  User Quote Token Account (WSOL ATA)
          #8  Pool Base Token Account
          #9  Pool Quote Token Account
          #10 Protocol Fee Recipient
          #11 Protocol Fee Recipient Token Account
          #12 Base Token Program
          #13 Quote Token Program
          #14 System Program
          #15 Associated Token Program
          #16 Event Authority
          #17 Program

        Data:
          sell_discriminator (8 bytes) + struct.pack("<QQ", base_amount_in, min_quote_amount_out)
        """
        from solana.transaction import AccountMeta, Instruction
        from solders.pubkey import Pubkey as SPubkey # type: ignore
        import struct

        data = SELL_INSTR_DISCRIM + struct.pack("<QQ", base_amount_in, min_quote_amount_out)

        accs = [
            AccountMeta(pubkey=SPubkey.from_string(str(pool_data["pool_pubkey"])),  is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(user_pubkey)),  is_signer=True,  is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(GLOBAL_CONFIG_PUB)),is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(pool_data["token_base"])), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(pool_data["token_quote"])), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(get_associated_token_address(user_pubkey, pool_data["token_base"]))),
                        is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(get_associated_token_address(user_pubkey, pool_data["token_quote"]))),
                        is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(pool_data["pool_base_token_account"])),  is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(pool_data["pool_quote_token_account"])), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(protocol_fee_recipient)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(protocol_fee_recipient_ata)), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(TOKEN_PROGRAM_PUB)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(TOKEN_PROGRAM_PUB)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(SYSTEM_PROGRAM_ID)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(ASSOCIATED_TOKEN)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(EVENT_AUTHORITY)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(PUMPSWAP_PROGRAM_ID)), is_signer=False, is_writable=False),
            AccountMeta(pubkey=SPubkey.from_string(str(vault_ata)), is_signer=False, is_writable=True),
            AccountMeta(pubkey=SPubkey.from_string(str(vault_auth)), is_signer=False, is_writable=True),
        ]

        return Instruction(
            program_id=SPubkey.from_string(str(PUMPSWAP_PROGRAM_ID)),
            data=data,
            accounts=accs
        )

    async def _fetch_user_token_balance(self, mint_pubkey_str: str) -> Optional[float]:
        response = await self.async_client.get_token_accounts_by_owner_json_parsed(
            self.signer.pubkey(),
            TokenAccountOpts(mint=Pubkey.from_string(mint_pubkey_str)),
            commitment=Processed
        )
        if response.value:
            accounts = response.value
            if accounts:
                balance = accounts[0].account.data.parsed['info']['tokenAmount']['uiAmount']
                if balance is not None:
                    return float(balance)
        return None

    async def _await_confirm_transaction(self, tx_sig: str, max_attempts=20, delay=2.0):
        """
        Simple helper to poll getTransaction until we get a success/fail.
        """
        for i in range(max_attempts):
            resp = await self.async_client.get_transaction(tx_sig, commitment=Confirmed, max_supported_transaction_version=0)
            if resp.value:
                maybe_err = resp.value.transaction.meta.err
                if maybe_err is None:
                    return True
                else:
                    return False
            await asyncio.sleep(delay)
        return False
    
    def _build_pumpswap_create_pool_ix(
        self,
        *,
        pool_pda: Pubkey,
        creator: Pubkey,
        base_mint: Pubkey,
        quote_mint: Pubkey,
        lp_mint_pda: Pubkey,
        user_base_ata: Pubkey,
        user_quote_ata: Pubkey,
        user_lp_ata: Pubkey,
        pool_base_ata: Pubkey,
        pool_quote_ata: Pubkey,
        index: int,
        base_amount_in: int,
        quote_amount_in: int,
    ):
        from solana.transaction import AccountMeta, Instruction
        import struct

        data = CREATE_POOL_DISCRIM + struct.pack(
            "<HQQ", index, base_amount_in, quote_amount_in
        )

        am = AccountMeta
        accs = [
            am(pool_pda,               False, True),
            am(GLOBAL_CONFIG_PUB,      False, False),
            am(creator,                True,  True),
            am(base_mint,              False, False),
            am(quote_mint,             False, False),
            am(lp_mint_pda,            False, True),
            am(user_base_ata,          False, True),
            am(user_quote_ata,         False, True),
            am(user_lp_ata,            False, True),
            am(pool_base_ata,          False, True),
            am(pool_quote_ata,         False, True),
            am(SYSTEM_PROGRAM_ID,      False, False),
            am(TOKEN_2022_PROGRAM_PUB, False, False),
            am(TOKEN_PROGRAM_PUB,      False, False),  # base_token_program
            am(TOKEN_PROGRAM_PUB,      False, False),  # quote_token_program
            am(ASSOCIATED_TOKEN,       False, False),
            am(EVENT_AUTHORITY,        False, False),
            am(PUMPSWAP_PROGRAM_ID,    False, False),
        ]

        return Instruction(
            program_id=PUMPSWAP_PROGRAM_ID,
            accounts=accs,
            data=data,
        )

    async def create_pool(
        self,
        base_mint: Pubkey,
        base_amount_tokens: float,  # e.g. 2e8 == 200 000 000
        quote_amount_sol: float,    # e.g. 15  (WSOL to deposit)
        decimals_base: int = 6,
        index: int = 0,
        fee_sol: float = 0.0005,
        mute              : bool = False,
    ) -> bool:
        """
        Initialise a brand‑new PumpSwap pool (a.k.a. “Add Liquidity” on pump.fun).
        the calling wallet becomes the creator & initial LP holder

        Returns:
            str: Pool PDA if successful, None otherwise
        """
        user = self.signer.pubkey()
        quote_mint = WSOL_MINT

        base_amount_in  = int(base_amount_tokens * 10 ** decimals_base)
        quote_amount_in = int(quote_amount_sol * LAMPORTS_PER_SOL)

        pool_seed_prefix = b"pool"
        pool_pda, _ = Pubkey.find_program_address(
            [
                pool_seed_prefix,
                index.to_bytes(2, "little"),
                bytes(user),
                bytes(base_mint),
                bytes(quote_mint),
            ],
            PUMPSWAP_PROGRAM_ID,
        )
        lp_mint_pda, _ = Pubkey.find_program_address(
            [b"pool_lp_mint", bytes(pool_pda)],
            PUMPSWAP_PROGRAM_ID,
        )

        pool_base_ata  = get_associated_token_address(pool_pda,  base_mint)
        pool_quote_ata = get_associated_token_address(pool_pda,  quote_mint)
        user_base_ata  = get_associated_token_address(user,      base_mint)
        user_quote_ata = get_associated_token_address(user,      quote_mint)
        user_lp_ata    = get_associated_token_address(
            user, lp_mint_pda, token_program_id=TOKEN_2022_PROGRAM_PUB
        )

        lamports_fee     = int(fee_sol * LAMPORTS_PER_SOL)
        micro_lamports   = compute_unit_price_from_total_fee(
            lamports_fee, POOL_COMPUTE_BUDGET
        )

        ix: list = [
            set_compute_unit_limit(POOL_COMPUTE_BUDGET),
            set_compute_unit_price(micro_lamports),
        ]

        maybe_create_wsol = await self.create_ata_if_needed(user, quote_mint)
        if maybe_create_wsol:
            ix.append(maybe_create_wsol)

        ix.append(
            self._build_system_transfer_ix(
                from_pubkey=user, to_pubkey=user_quote_ata, lamports=quote_amount_in
            )
        )
        ix.append(
            sync_native(
                SyncNativeParams(
                    program_id=TOKEN_PROGRAM_PUB,
                    account=user_quote_ata,
                )
            )
        )
        ix.append(build_transfer_ix(user))

        for mint, ata in (
            (base_mint, pool_base_ata),
            (quote_mint, pool_quote_ata),
        ):
            maybe_ix = await self._create_ata_if_needed_for_owner(
                payer=user, owner=pool_pda, mint=mint
            )
            if maybe_ix:
                ix.append(maybe_ix)

        ix.append(
            self._build_pumpswap_create_pool_ix(
                pool_pda=pool_pda,
                creator=user,
                base_mint=base_mint,
                quote_mint=quote_mint,
                lp_mint_pda=lp_mint_pda,
                user_base_ata=user_base_ata,
                user_quote_ata=user_quote_ata,
                user_lp_ata=user_lp_ata,
                pool_base_ata=pool_base_ata,
                pool_quote_ata=pool_quote_ata,
                index=index,
                base_amount_in=base_amount_in,
                quote_amount_in=quote_amount_in,
            )
        )

        ix.append(
            close_account(
                CloseAccountParams(
                    program_id=TOKEN_PROGRAM_PUB,
                    account=user_quote_ata,
                    dest=user,
                    owner=user,
                )
            )
        )

        bh = await self.async_client.get_latest_blockhash()
        msg = MessageV0.try_compile(
            payer=user,
            instructions=ix,
            address_lookup_table_accounts=[],
            recent_blockhash=bh.value.blockhash,
        )
        tx = VersionedTransaction(msg, [self.signer])
        ok_sim = await self._simulate_and_show(tx, mute)
        if not ok_sim:
            return False   # bail early – no fee wasted
        sig = (await self.async_client.send_transaction(
            tx, opts=TxOpts(skip_preflight=True, max_retries=0)
        )).value

        if not mute:
            print(f"Tx submitted: https://solscan.io/tx/{sig}")

        ok = await self._await_confirm_transaction(sig)

        if not mute:
            print("Success:", ok)

        return str(pool_pda) if ok else None
    
    def _build_pumpswap_withdraw_ix(
        self,
        *,
        pool_pubkey: Pubkey,
        user_pubkey: Pubkey,
        base_mint: Pubkey,
        quote_mint: Pubkey,
        lp_mint: Pubkey,
        user_base_ata: Pubkey,
        user_quote_ata: Pubkey,
        user_lp_ata: Pubkey,
        pool_base_ata: Pubkey,
        pool_quote_ata: Pubkey,
        lp_token_amount_in: int,
        min_base_amount_out: int,
        min_quote_amount_out: int,
    ):
        from solana.transaction import AccountMeta, Instruction
        import struct

        data = WITHDRAW_INSTR_DISCRIM + struct.pack(
            "<QQQ",
            lp_token_amount_in,
            min_base_amount_out,
            min_quote_amount_out,
        )

        am = AccountMeta
        accs = [
            am(pool_pubkey,            False, True),
            am(GLOBAL_CONFIG_PUB,      False, False),
            am(user_pubkey,            True,  True),
            am(base_mint,              False, False),
            am(quote_mint,             False, False),
            am(lp_mint,                False, True),
            am(user_base_ata,          False, True),
            am(user_quote_ata,         False, True),
            am(user_lp_ata,            False, True),
            am(pool_base_ata,          False, True),
            am(pool_quote_ata,         False, True),
            am(TOKEN_PROGRAM_PUB,      False, False),
            am(TOKEN_2022_PROGRAM_PUB, False, False),
            am(EVENT_AUTHORITY,        False, False),
            am(PUMPSWAP_PROGRAM_ID,    False, False),
        ]

        return Instruction(
            program_id=PUMPSWAP_PROGRAM_ID, data=data, accounts=accs
        )
    
    async def withdraw(
        self,
        pool_data: dict,
        withdraw_pct: float,          # 100 = max
        fee_sol: float = 0.0003,
        mute              : bool = False,
    ):
        """
            Withdraw deposited liquidity from a PumpSwap pool (creating a pool counts as deposit).
        """
        user         = self.signer.pubkey()
        lp_mint      = Pubkey.from_string(pool_data["lp_mint"])
        base_mint    = pool_data["token_base"]
        quote_mint   = pool_data["token_quote"]

        lp_balance_f = await self._fetch_user_token_balance(str(lp_mint))
        if not lp_balance_f or lp_balance_f == 0:
            if not mute:
                print("No LP tokens, nothing to withdraw")
            return False

        lp_in_f      = lp_balance_f * withdraw_pct / 100.0
        lp_amount_in = int(lp_in_f * 10**9)            # lp-mint is 9-dec

        # (0 → skip slippage checks)
        min_base_out  = 0
        min_quote_out = 0

        lamports_fee = int(fee_sol * LAMPORTS_PER_SOL)
        micro_lamports = compute_unit_price_from_total_fee(
            lamports_fee, UNIT_COMPUTE_BUDGET
        )

        ix: list = [
            set_compute_unit_limit(UNIT_COMPUTE_BUDGET),
            set_compute_unit_price(micro_lamports),
        ]

        wsol_create = await self.create_ata_if_needed(user, quote_mint)
        if wsol_create:
            ix.append(wsol_create)
        user_quote_ata = get_associated_token_address(user, quote_mint)

        ix.append(build_transfer_ix(user))

        ix.append(
            self._build_pumpswap_withdraw_ix(
                pool_pubkey             = pool_data["pool_pubkey"],
                user_pubkey             = user,
                base_mint               = base_mint,
                quote_mint              = quote_mint,
                lp_mint                 = Pubkey.from_string(pool_data["lp_mint"]),
                user_base_ata           = get_associated_token_address(user, base_mint),
                user_quote_ata          = user_quote_ata,
                user_lp_ata             = get_associated_token_address(user, lp_mint, token_program_id=TOKEN_2022_PROGRAM_PUB),
                pool_base_ata           = Pubkey.from_string(pool_data["pool_base_token_account"]),
                pool_quote_ata          = Pubkey.from_string(pool_data["pool_quote_token_account"]),
                lp_token_amount_in      = lp_amount_in,
                min_base_amount_out     = min_base_out,
                min_quote_amount_out    = min_quote_out,
            )
        )

        ix.append(
            close_account(
                CloseAccountParams(
                    program_id = TOKEN_PROGRAM_PUB,
                    account    = user_quote_ata,
                    dest       = user,
                    owner      = user,
                )
            )
        )

        blockhash  = (await self.async_client.get_latest_blockhash()).value.blockhash
        msg        = MessageV0.try_compile(
            payer=user, instructions=ix, address_lookup_table_accounts=[],
            recent_blockhash=blockhash,
        )
        tx         = VersionedTransaction(msg, [self.signer])
        if not await self._simulate_and_show(tx, mute): return False

        sig = (await self.async_client.send_transaction(
            tx, opts=TxOpts(skip_preflight=True, max_retries=0)
        )).value

        if not mute:
            print("Tx:", sig)

        ok  = await self._await_confirm_transaction(sig)

        if not mute:
            print("Success:", ok)

        return ok

    def _build_pumpswap_deposit_ix(
        self,
        *,
        pool_pubkey: Pubkey,
        user_pubkey: Pubkey,
        base_mint: Pubkey,
        quote_mint: Pubkey,
        lp_mint: Pubkey,
        user_base_ata: Pubkey,
        user_quote_ata: Pubkey,
        user_lp_ata: Pubkey,
        pool_base_ata: Pubkey,
        pool_quote_ata: Pubkey,
        lp_token_amount_out: int,
        max_base_amount_in: int,
        max_quote_amount_in: int,
    ):
        from solana.transaction import AccountMeta, Instruction
        import struct

        data = DEPOSIT_INSTR_DISCRIM + struct.pack(
            "<QQQ",
            lp_token_amount_out,
            max_base_amount_in,
            max_quote_amount_in,
        )

        am = AccountMeta
        accs = [
            am(pool_pubkey,            False, True),
            am(GLOBAL_CONFIG_PUB,      False, False),
            am(user_pubkey,            True,  True),
            am(base_mint,              False, False),
            am(quote_mint,             False, False),
            am(lp_mint,                False, True),
            am(user_base_ata,          False, True),
            am(user_quote_ata,         False, True),
            am(user_lp_ata,            False, True),
            am(pool_base_ata,          False, True),
            am(pool_quote_ata,         False, True),
            am(TOKEN_PROGRAM_PUB,      False, False),
            am(TOKEN_2022_PROGRAM_PUB, False, False),
            am(EVENT_AUTHORITY,        False, False),
            am(PUMPSWAP_PROGRAM_ID,    False, False),
        ]

        return Instruction(
            program_id=PUMPSWAP_PROGRAM_ID, data=data, accounts=accs
        )
    
    async def deposit(
        self,
        pool_data         : dict,
        base_amount_tokens: float,     # UI amount of base-tokens you want to add
        slippage_pct      : float = 1.0,
        fee_sol           : float = 0.0003,
        sol_cap           : float | None = None,
        mute              : bool = False,
    ):
        """
            Deposit tokens into a PumpSwap pool.
        """
        user        = self.signer.pubkey()
        base_mint   = pool_data["token_base"]
        quote_mint  = pool_data["token_quote"]
        lp_mint     = Pubkey.from_string(pool_data["lp_mint"])
        dec_base    = pool_data["decimals_base"]

        base_in_raw = int(base_amount_tokens * 10**dec_base)

        base_res_raw  = int((await self.async_client.get_token_account_balance(
                            Pubkey.from_string(pool_data["pool_base_token_account"])
                            )).value.amount)
        quote_res_raw = int((await self.async_client.get_token_account_balance(
                            Pubkey.from_string(pool_data["pool_quote_token_account"])
                            )).value.amount)
        if base_res_raw == 0 or quote_res_raw == 0:
            if not mute:
                print("Pool reserves are zero – can’t deposit proportionally.")
            return False

        quote_needed_lamports = base_in_raw * quote_res_raw // base_res_raw

        if sol_cap is not None:
            cap_lamports = int(sol_cap * LAMPORTS_PER_SOL)
            if quote_needed_lamports > cap_lamports:
                if not mute:
                    print(
                    f"Deposit aborted: would need {quote_needed_lamports/1e9:.6f} SOL "
                    f"but cap is {sol_cap:.6f} SOL."
                    )
                return False

        max_base_in  = int(base_in_raw  * (1 + slippage_pct / 100))
        max_quote_in = int(quote_needed_lamports * (1 + slippage_pct / 100))

        lp_supply_raw = max(
            int((await self.async_client.get_token_supply(lp_mint)).value.amount) - 100,
            1,
        )
        lp_est_raw = base_in_raw * lp_supply_raw // base_res_raw
        min_lp_out = max(int(lp_est_raw * (1 - slippage_pct / 100)), 1)

        ui_bal_resp = await self.async_client.get_token_accounts_by_owner_json_parsed(
            user, TokenAccountOpts(mint=base_mint), commitment=Processed
        )
        have_base_raw = int(
            ui_bal_resp.value[0].account.data.parsed["info"]["tokenAmount"]["amount"]
        ) if ui_bal_resp.value else 0
        if have_base_raw < base_in_raw:
            if not mute:
                print("Not enough base tokens in wallet.")
            return False
        # SOL balance
        sol_balance = (await self.async_client.get_balance(user)).value
        if sol_balance < quote_needed_lamports + int(0.002 * LAMPORTS_PER_SOL):
            if not mute:
                print("Not enough SOL to wrap.")
            return False

        ix = [
            set_compute_unit_limit(UNIT_COMPUTE_BUDGET),
            set_compute_unit_price(
                compute_unit_price_from_total_fee(
                    int(fee_sol * LAMPORTS_PER_SOL), UNIT_COMPUTE_BUDGET
                )
            ),
        ]

        if (wsol_ix := await self.create_ata_if_needed(user, quote_mint)):
            ix.append(wsol_ix)
        if (base_ix := await self.create_ata_if_needed(user, base_mint)):
            ix.append(base_ix)
        ix.append(build_transfer_ix(user))
        user_base_ata  = get_associated_token_address(user, base_mint)
        user_quote_ata = get_associated_token_address(user, quote_mint)

        ix += [
            self._build_system_transfer_ix(user, user_quote_ata, quote_needed_lamports),
            sync_native(SyncNativeParams(program_id=TOKEN_PROGRAM_PUB,
                                         account=user_quote_ata)),
        ]

        ix.append(
            self._build_pumpswap_deposit_ix(
                pool_pubkey          = pool_data["pool_pubkey"],
                user_pubkey          = user,
                base_mint            = base_mint,
                quote_mint           = quote_mint,
                lp_mint              = lp_mint,
                user_base_ata        = user_base_ata,
                user_quote_ata       = user_quote_ata,
                user_lp_ata          = get_associated_token_address(
                                           user, lp_mint,
                                           token_program_id=TOKEN_2022_PROGRAM_PUB),
                pool_base_ata        = Pubkey.from_string(pool_data["pool_base_token_account"]),
                pool_quote_ata       = Pubkey.from_string(pool_data["pool_quote_token_account"]),
                lp_token_amount_out  = min_lp_out,
                max_base_amount_in   = max_base_in,
                max_quote_amount_in  = max_quote_in,
            )
        )

        ix.append(
            close_account(
                CloseAccountParams(program_id=TOKEN_PROGRAM_PUB,
                                   account=user_quote_ata,
                                   dest=user,
                                   owner=user))
        )

        bh  = (await self.async_client.get_latest_blockhash()).value.blockhash
        msg = MessageV0.try_compile(payer=user, instructions=ix,
                                    address_lookup_table_accounts=[],
                                    recent_blockhash=bh)
        tx  = VersionedTransaction(msg, [self.signer])

        if not await self._simulate_and_show(tx, mute):
            return False
        sig = (await self.async_client.send_transaction(
            tx, opts=TxOpts(skip_preflight=True, max_retries=0)
        )).value
        if not mute:
            print("Tx:", sig)
        ok  = await self._await_confirm_transaction(sig)
        if not mute:
            print("Success:", ok)
        return ok

    @staticmethod
    def derive_pool_address(creator: Pubkey, base_mint: Pubkey,
                            quote_mint: Pubkey, index: int = 0) -> Pubkey:
        seed = [
            b"pool",
            index.to_bytes(2, "little"),
            bytes(creator),
            bytes(base_mint),
            bytes(quote_mint),
        ]
        return Pubkey.find_program_address(seed, PUMPSWAP_PROGRAM_ID)[0]

    async def _simulate_and_show(self, tx: VersionedTransaction, mute: bool = False):
        sim = await self.async_client.simulate_transaction(
            tx, sig_verify=False, commitment=Processed,

        )
        if not mute:
            if sim.value.err:
                print("── Simulation failed ──────────────────────────────────────────")
            else:
                print("── Simulation succeeded ────────────────────────────────────────")
            for l in sim.value.logs:
                print(l)
            print("────────────────────────────────────────────────────────────────")
        return sim.value.err is None