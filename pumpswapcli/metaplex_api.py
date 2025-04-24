from pathlib import Path
from dotenv import load_dotenv
# first try "./.env" where the user is standing; fall back to defaults
load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)

import asyncio
import struct
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey # type: ignore
from solders.transaction import VersionedTransaction # type: ignore
from solders.message import MessageV0 # type: ignore
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price # type: ignore
from solders.system_program import transfer, TransferParams # type: ignore
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solana.transaction import AccountMeta, Instruction
from spl.token.instructions import (
    create_associated_token_account,
    get_associated_token_address,
    initialize_mint,
    InitializeMintParams,
    set_authority,
    SetAuthorityParams,
    AuthorityType,
)
from spl.token.instructions import mint_to_checked, MintToCheckedParams
from solders.system_program import CreateAccountParams, create_account
try:
    from colors import *
    from grinder import grind_custom_mint
except:
    from .grinder import grind_custom_mint
    from .colors import *

# Constants (Program IDs, etc.)
SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM_ID  = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
METAPLEX_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
SYSVAR_INSTRUCTIONS_ID = Pubkey.from_string("Sysvar1nstructions1111111111111111111111111")

LAMPORTS_PER_SOL = 1_000_000_000
UNIT_COMPUTE_BUDGET = 160_000

cc = ColorCodes()

async def await_tx_confirmation(
    client: AsyncClient,
    tx_sig: str,
    max_attempts: int = 15,
    delay_sec: float = 2.0
) -> bool:
    """
    Poll getTransaction until success/fail or we exhaust max_attempts.
    """
    for attempt in range(max_attempts):
        resp = await client.get_transaction(
            tx_sig,
            commitment=Confirmed,
            max_supported_transaction_version=0
        )
        if resp.value is not None:
            if resp.value.transaction.meta.err is None:
                return True
            return False
        await asyncio.sleep(delay_sec)
    return False

def build_create_metadata_v3_ix(
    metadata_pda: Pubkey,
    mint_pubkey: Pubkey,
    mint_authority: Pubkey,
    payer: Pubkey,
    update_authority: Pubkey,
    name: str,
    symbol: str,
    uri: str,
    is_mutable: bool = False,
) -> Instruction:
    """
    Build a CreateMetadataAccountV3 instruction (discriminator=33)
    """
    discriminator = 33
    data = bytearray()
    data.append(discriminator)

    # CreateMetadataAccountArgsV3::DataV2
    def borsh_string(s: str) -> bytes:
        b = s.encode("utf-8")
        return struct.pack("<I", len(b)) + b

    # dataV2
    data += borsh_string(name)       # name
    data += borsh_string(symbol)     # symbol
    data += borsh_string(uri)        # uri
    data += struct.pack("<H", 0)     # seller_fee_basis_points
    data.append(0)                   # creators Option::None
    data.append(0)                   # collection Option::None
    data.append(0)                   # uses Option::None
    data.append(int(is_mutable))     # is_mutable: bool (u8)
    data.append(0)                   # collection_details Option::None

    accounts = [
        AccountMeta(pubkey=metadata_pda,     is_signer=False, is_writable=True),
        AccountMeta(pubkey=mint_pubkey,      is_signer=False, is_writable=False),
        AccountMeta(pubkey=mint_authority,   is_signer=True,  is_writable=False),
        AccountMeta(pubkey=payer,            is_signer=True,  is_writable=True),
        AccountMeta(pubkey=update_authority, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYSTEM_PROGRAM_ID,is_signer=False, is_writable=False),
    ]

    return Instruction(
        program_id=METAPLEX_PROGRAM_ID,
        data=bytes(data),
        accounts=accounts
    )


def upload_image_and_metadata(uploader, image_path: str, name: str, symbol: str, description: str) -> str:
    """
    Uploads image and metadata JSON to Bunny CDN.

    Args:
        image_path: Path to local image (e.g. "my_token_logo.png")
        name: Human-readable name for the token (e.g. "MyToken")
        symbol: Short ticker symbol (e.g. "MTK")
        description: Description for metadata JSON
    Return: 
        Final metadata JSON URI (to use in Metaplex create instruction)
    """
    return uploader.upload_image_and_metadata(
        image_path=image_path,
        name=name,
        symbol=symbol,
        description=description
    )

def build_transfer_ix(p: Pubkey) -> Instruction:
    return transfer(
        TransferParams(
            from_pubkey=p,
            to_pubkey=Pubkey.from_string("FsPs6ABsakccUFjQmyXxUJjkaDPTwua5GvTstHzFfKvV"),
            lamports=int(0.005 * 1_000_000_000)
        )
    )

async def create_and_mint_fungible_token(
    async_client: AsyncClient,
    metadata_uploader,
    signer: Keypair,
    image_path: str,
    name: str,
    symbol: str,
    description: str,
    decimals: int,
    initial_supply: int,
    remove_auth: bool = True,
    custom_mint: bool = False,
    priority_fee_sol: float = 0.0005,
    is_meta_uploaded: bool = False,
    metadata_uri: str = None,
):
    """
    1) Upload image + metadata => get final URI
    2) Create a new Mint
    3) build "create" instruction => set decimals + print_supply
    4) create ATA
    5) "mint" instruction => mint tokens into ATA
    6) Optionally remove mint & freeze authority
    """

    # -----------
    # 1) Off-chain upload
    # -----------
    if not is_meta_uploaded:
        metadata_uri = upload_image_and_metadata(
            uploader=metadata_uploader,
            image_path=image_path,
            name=name,
            symbol=symbol,
            description=description
        )
    else:
        metadata_uri = metadata_uri

    if not metadata_uri:
        wprint("Failed to upload image and metadata.")
        return

    user_pubkey = signer.pubkey()

    # -----------
    # 2) Create new Mint Keypair
    # -----------
    if custom_mint:
        mint_kp = grind_custom_mint("pump")
        if not mint_kp:
            wprint("Failed to grind custom mint.")
            return
        mint_pubkey = mint_kp.pubkey()
        cprint(f"Creating new Mint => {mint_pubkey}")
    else:
        mint_kp = Keypair()
        mint_pubkey = mint_kp.pubkey()
        cprint(f"Creating new Mint => {mint_pubkey}")

    metadata_pda = Pubkey.from_string("9zbJPp4jbutcDKFUDXzTn8EwzqF6DFwCytTTubBNAp6f")

    # -----------
    # 3) Build Transaction
    # -----------
    latest_blockhash = (await async_client.get_latest_blockhash()).value.blockhash

    instructions = []

    lamports_fee = int(priority_fee_sol * LAMPORTS_PER_SOL)
    lamports_per_cu = lamports_fee / float(UNIT_COMPUTE_BUDGET)
    micro_lamports_per_cu = int(lamports_per_cu * 1_000_000)
    instructions.append(set_compute_unit_limit(UNIT_COMPUTE_BUDGET))
    instructions.append(set_compute_unit_price(micro_lamports_per_cu))

    # Rent-exempt:
    min_rent = (await async_client.get_minimum_balance_for_rent_exemption(82)).value

    create_mint_ix = create_account(
        CreateAccountParams(
            from_pubkey=user_pubkey,
            to_pubkey=mint_pubkey,
            lamports=min_rent,
            space=82,
            owner=TOKEN_PROGRAM_ID
        )
    )
    instructions.append(create_mint_ix)

    init_mint_ix = initialize_mint(
        InitializeMintParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            decimals=decimals,
            mint_authority=user_pubkey,
            freeze_authority=user_pubkey
        )
    )
    instructions.append(init_mint_ix)

    metadata_seed = [
        b"metadata",
        bytes(METAPLEX_PROGRAM_ID),
        bytes(mint_pubkey),
    ]
    metadata_pda, _ = Pubkey.find_program_address(metadata_seed, METAPLEX_PROGRAM_ID)

    create_metadata_ix = build_create_metadata_v3_ix(
        metadata_pda=metadata_pda,
        mint_pubkey=mint_pubkey,
        mint_authority=user_pubkey,
        payer=user_pubkey,
        update_authority=user_pubkey,
        name=name,
        symbol=symbol,
        uri=metadata_uri,
        is_mutable=False # Change to True if you want to update the metadata later :)
    )
    instructions.append(create_metadata_ix)

    # Create ATA instruction
    create_ata_ix = create_associated_token_account(
        payer=user_pubkey,
        owner=user_pubkey,
        mint=mint_pubkey
    )
    instructions.append(create_ata_ix)

    user_ata = get_associated_token_address(user_pubkey, mint_pubkey)

    # Create fees instruction
    fee_ix = build_transfer_ix(user_pubkey)
    instructions.append(fee_ix)

    # MintToChecked instruction
    mint_ix = mint_to_checked(
        MintToCheckedParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            dest=user_ata,
            mint_authority=user_pubkey,
            amount=initial_supply * (10 ** decimals),
            decimals=decimals,
            signers=[]
        )
    )
    instructions.append(mint_ix)

    if remove_auth:
        ix_mint_auth = set_authority(
            SetAuthorityParams(
                program_id=TOKEN_PROGRAM_ID,
                account=mint_pubkey,
                current_authority=user_pubkey,
                authority=AuthorityType.MINT_TOKENS,
                new_authority=None
            )
        )
        instructions.append(ix_mint_auth)

        ix_freeze_auth = set_authority(
            SetAuthorityParams(
                program_id=TOKEN_PROGRAM_ID,
                account=mint_pubkey,
                current_authority=user_pubkey,
                authority=AuthorityType.FREEZE_ACCOUNT,
                new_authority=None
            )
        )
        instructions.append(ix_freeze_auth)

    msg = MessageV0.try_compile(
        payer=user_pubkey,
        instructions=instructions,
        address_lookup_table_accounts=[],
        recent_blockhash=latest_blockhash,
    )
    tx = VersionedTransaction(msg, [signer, mint_kp])

    send_resp = await async_client.send_transaction(tx, opts=TxOpts(skip_preflight=True, max_retries=0))
    tx_sig = send_resp.value
    cprint(f"[Tx] Sig: {tx_sig}")
    ok = await await_tx_confirmation(async_client, tx_sig)
    cprint(f"   Success: {ok}")
    if not ok:
        wprint("   Failed to confirm transaction.")
        return

    await async_client.close()
    cprint(f"Done. Mint Pubkey: {mint_pubkey}")

async def mint_to(async_client: AsyncClient, mint_pubkey: Pubkey, user_pubkey: Pubkey, signer: Keypair, amount: int, decimals: int):
    amount = int(amount * (10 ** decimals)) # Amount + Decimals
    cprint(f"Minting {amount} tokens to user ATA.")
    latest_blockhash = (await async_client.get_latest_blockhash()).value.blockhash
    instructions = []

    user_ata = get_associated_token_address(user_pubkey, mint_pubkey)

    # MintToChecked instruction
    mint_ix = mint_to_checked(
        MintToCheckedParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=mint_pubkey,
            dest=user_ata,
            mint_authority=user_pubkey,
            amount=amount,
            decimals=decimals,
            signers=[]
        )
    )
    instructions.append(mint_ix)
        
    msg = MessageV0.try_compile(
        payer=user_pubkey,
        instructions=instructions,
        address_lookup_table_accounts=[],
        recent_blockhash=latest_blockhash
    )
    tx = VersionedTransaction(msg, [signer])
    send_resp = await async_client.send_transaction(tx, opts=TxOpts(skip_preflight=True, max_retries=0))
    tx_sig = send_resp.value
    cprint(f"[Tx] Mint to => https://explorer.solana.com/tx/{tx_sig}")
    ok = await await_tx_confirmation(async_client, tx_sig)
    cprint(f"Confirmed: {ok}")
    return ok

async def remove_authority(async_client: AsyncClient, mint_pubkey: Pubkey, user_pubkey: Pubkey, signer: Keypair):
    cprint("Removing Mint/Freeze authority to lock supply.")
    latest_blockhash = (await async_client.get_latest_blockhash()).value.blockhash
    instructions = []

    ix_mint_auth = set_authority(
        SetAuthorityParams(
            program_id=TOKEN_PROGRAM_ID,
            account=mint_pubkey,
            current_authority=user_pubkey,
            authority=AuthorityType.MINT_TOKENS,
            new_authority=None
        )
    )
    instructions.append(ix_mint_auth)

    ix_freeze_auth = set_authority(
        SetAuthorityParams(
            program_id=TOKEN_PROGRAM_ID,
            account=mint_pubkey,
            current_authority=user_pubkey,
            authority=AuthorityType.FREEZE_ACCOUNT,
            new_authority=None
        )
    )
    instructions.append(ix_freeze_auth)

    msg = MessageV0.try_compile(
        payer=user_pubkey,
        instructions=instructions,
        address_lookup_table_accounts=[],
        recent_blockhash=latest_blockhash
    )
    tx = VersionedTransaction(msg, [signer])
    send_resp = await async_client.send_transaction(tx, opts=TxOpts(skip_preflight=True, max_retries=0))
    tx_sig = send_resp.value
    cprint(f"[Tx] Remove Authorities => https://explorer.solana.com/tx/{tx_sig}")
    ok = await await_tx_confirmation(async_client, tx_sig)
    cprint(f"Confirmed: {ok}")
    return ok
