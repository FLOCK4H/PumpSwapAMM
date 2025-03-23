import asyncio
from typing import Optional
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts, TokenAccountOpts
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit # type: ignore
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey # type: ignore
from solders.transaction import VersionedTransaction # type: ignore
from solders.message import MessageV0 # type: ignore
from solana.rpc.commitment import Processed, Confirmed
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
    sync_native,
    SyncNativeParams,
    close_account,
    CloseAccountParams,
)

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

class PumpSwap:
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

    async def buy(
        self,
        pool_data: dict,
        sol_amount: float,      # e.g. 0.001
        slippage_pct: float,    # e.g. 1.0 => 1%
        fee_sol: float,         # total priority fee user wants to pay, e.g. 0.0005
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
            max_quote_amount_in = max_quote_amount_in
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
        print(f"Transaction sent: https://solscan.io/tx/{send_resp.value}")

        # Confirm
        confirmed = await self._await_confirm_transaction(send_resp.value)
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
        max_quote_amount_in: int
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

        BUY_INSTR_DISCRIM = b'\x66\x06\x3d\x12\x01\xda\xeb\xea'

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
        
        user_base_balance_f = await self._fetch_user_token_balance(pool_data['token_base'])
        if user_base_balance_f <= 0:
            print("No base token balance, can't sell.")
            return False
        
        to_sell_amount_f = user_base_balance_f * (sell_pct / 100.0)
        if to_sell_amount_f <= 0:
            print("Nothing to sell after applying percentage.")
            return False
        
        decimals_base = pool_data['decimals_base']
        base_amount_in = int(to_sell_amount_f * (10 ** decimals_base))
        
        base_balance_tokens = pool_data['base_balance_tokens']
        quote_balance_sol   = pool_data['quote_balance_sol']
        
        price = get_price(base_balance_tokens, quote_balance_sol)
        raw_sol = to_sell_amount_f * price
        
        min_sol_out = raw_sol * (1 - slippage_pct/100.0)
        min_quote_amount_out = int(min_sol_out * LAMPORTS_PER_SOL)
        if min_quote_amount_out <= 0:
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
        
        sell_ix = self._build_pumpswap_sell_ix(
            user_pubkey = user_pubkey,
            pool_data = pool_data,
            base_amount_in = base_amount_in,
            min_quote_amount_out = min_quote_amount_out,
            protocol_fee_recipient   = PROTOCOL_FEE_RECIP,
            protocol_fee_recipient_ata = PROTOCOL_FEE_RECIP_ATA,
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
        print(f"Transaction sent: https://solscan.io/tx/{send_resp.value}")
        
        confirmed = await self._await_confirm_transaction(send_resp.value)
        print("Success:", confirmed)
        return confirmed

    def _build_pumpswap_sell_ix(
        self,
        user_pubkey: Pubkey,
        pool_data: dict,
        base_amount_in: int,
        min_quote_amount_out: int,
        protocol_fee_recipient: Pubkey,
        protocol_fee_recipient_ata: Pubkey
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

        SELL_INSTR_DISCRIM = b"\x33\xe6\x85\xa4\x01\x7f\x83\xad"

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
        ]

        return Instruction(
            program_id=SPubkey.from_string(str(PUMPSWAP_PROGRAM_ID)),
            data=data,
            accounts=accs
        )

    async def _fetch_user_token_balance(self, mint_pubkey_str: str) -> Optional[float]:
        response = await self.async_client.get_token_accounts_by_owner_json_parsed(
            self.signer.pubkey(),
            TokenAccountOpts(mint=mint_pubkey_str),
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