import json
from tkinter import Tk
from tkinter.filedialog import askopenfilename
import os
import asyncio
import traceback
import logging
try:
    from .colors import *
except:
    from colors import *
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey # type: ignore
try:
    from metaplex_api import create_and_mint_fungible_token, remove_authority, mint_to
except:
    from .metaplex_api import create_and_mint_fungible_token, remove_authority, mint_to
from dotenv import load_dotenv
try:
    from cdn_wrapper import BunnyCDNUploader
except:
    from .cdn_wrapper import BunnyCDNUploader
try:
    from AMMCLI import PSAMM, fetch_pool, WSOL_MINT, fetch_pool_base_price
except:
    from .AMMCLI import PSAMM, fetch_pool, WSOL_MINT, fetch_pool_base_price
from solana.rpc.commitment import Processed
try: from psa_utils import find_pools_by_mint;
except: from .psa_utils import find_pools_by_mint;

load_dotenv()
logging.basicConfig(level=logging.INFO)

suppress_logs = [
    "socks",
    "requests",
    "httpx",
    "trio.async_generator_errors",
    "trio",
    "trio.abc.Instrument",
    "trio.abc",
    "trio.serve_listeners",
    "httpcore.http11",
    "httpcore",
    "httpcore.connection",
    "httpcore.proxy",
]

# Set all of them to CRITICAL (no logs)
for log_name in suppress_logs:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)
    logging.getLogger(log_name).handlers.clear()
    logging.getLogger(log_name).propagate = False

# Preferred uploader is Bunny.net due to low costs (1$ per month)
# Create .env file in your current working dir and add the following:
# ACCESS_KEY=bunny-access-key
# STORAGE_ZONE_NAME=bunny-storage-zone-name
# PRIVATE_KEY=your-solana-private-key
# RPC_URL="https://mainnet.helius-rpc.com/?api-key=your-api-key"
# REGION=
# PULL_ZONE_NAME=your-pull-zone-name e.g. flockahh

BUNNY_UPLOADER = BunnyCDNUploader(
    region=os.getenv("REGION"),  # e.g. 'uk' or leave blank for default global
    storage_zone_name=os.getenv("STORAGE_ZONE_NAME"),
    access_key=os.getenv("ACCESS_KEY"),
    pull_zone_name=os.getenv("PULL_ZONE_NAME")  # e.g. 'your-pull-zone-name'
)
PRIV_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL")

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

class PumpSwapCLI:
    def __init__(self):
        self.cc = ColorCodes()
        self.async_client = AsyncClient(
            RPC_URL
        )
        self.signer = Keypair.from_base58_string(PRIV_KEY)
        self.pump_swap = PSAMM(self.async_client, signer=self.signer)

    async def ask_for_pool(self):
        mint = cinput("Enter mint address", maxlen=44)
        if not mint or len(mint) != 44:
            wprint("Mint required"); return None

        pools = await find_pools_by_mint(self.async_client, base_mint=mint,
                                        quote_mint=str(WSOL_MINT))   # WSOL pools only
        if not pools:
            wprint("No PumpSwap pool found for that mint."); return None

        if len(pools) == 1:
            cprint(f"Found pool: {pools[0]['pubkey']}")
            return pools[0]["pubkey"]

        # more than one pool (different creators / indexes) → let the user pick
        cprint("Multiple pools found:")
        for i, p in enumerate(pools):
            print(f"{i}) {p['pubkey']}")
        idx = int(cinput("Choose pool index"))          # rudimentary, add checks…
        return pools[idx]["pubkey"]

    async def get_pool_data(self, pool_addr, mint=None):
        dec_base = 6
        if mint is not None:
            cprint("Fetching decimals of the token...")
            mint_info = await self.async_client.get_account_info_json_parsed(
                Pubkey.from_string(mint),
                commitment=Processed
            )
            if not mint_info:
                print("Error: Failed to fetch mint info (tried to fetch token decimals).")
                return
            dec_base = mint_info.value.data.parsed['info']['decimals']

        pool_keys  = await fetch_pool(pool_addr, self.async_client)
        _, base_bal, quote_bal = await fetch_pool_base_price(pool_keys, self.async_client)

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

        return pool_data

    async def create_token(self):
        cprint(f"Creating token...")
        is_meta_uploaded = False
        metadata_uri = None

        c = cinput("Upload metadata, load from /tmp folder, or create manually (if not using Bunny)? (u/l/c)", maxlen=1)
        if c == "u":
            cprint(f"Please select the image you want to use for the token")
            # Prepare image
            Tk().withdraw()

            file_path = askopenfilename()
            if not file_path:
                await asyncio.sleep(1)
                return None  # user canceled

            name = cinput(f"Name of the token")
            if not name:
                wprint(f"Name cannot be empty")
                await asyncio.sleep(3)
                return None
            symbol = cinput(f"Enter the symbol of the token")
            description = cinput(f"Enter the description of the token")
        elif c == "l":
            folder_path = cinput(f"Enter the path to the folder containing the metadata (/tmp by default)")
            if not folder_path:
                folder_path = "tmp"

            files = os.listdir(folder_path)
            for i, file in enumerate(files):
                print(f"{i}) {file}")
            file_index = cinput(f"Enter the index of the file you want to use")
            file_path = os.path.join(folder_path, files[int(file_index)])
            with open(file_path, "r") as file:
                metadata = json.load(file)

            name = metadata["name"]
            symbol = metadata["symbol"]
            description = metadata["description"]
            file_path = metadata["image"]
            is_meta_uploaded = True
            metadata_uri = metadata["url"]
        elif c == "c":
            metadata_uri = cinput(f"Enter the metadata uri (directly, so e.g. https://your-cdn.b-cdn.net/my_metadata.json)")
            name = cinput(f"Enter name for the token (same as in metadata)")
            if not name:
                wprint(f"Name cannot be empty")
                await asyncio.sleep(3)
                return None
            symbol = cinput(f"Enter the symbol of the token (same as in metadata)")
            description = cinput(f"Enter the description of the token (same as in metadata)")
            is_meta_uploaded = True
        else:
            wprint(f"Unknown option: {c}")
                
        decimals = cinput(f"Enter the decimals of the token (6 by default)", maxlen=1)
        initial_supply = cinput(f"Enter the initial supply of the token (1_000_000_000 by default)")
        priority_fee_sol = cinput(f"Priority fee for faster transaction confirmation (0.0001 SOL by default)")
        remove_authority = cinput(f"Remove authority of the token? (y/n)", maxlen=1) or "y"
        custom_mint = cinput(f"Use custom mint ending with `pump` [takes longer]? (y/n)", maxlen=1) or "n"
        
        await create_and_mint_fungible_token(
            async_client=self.async_client,
            metadata_uploader=BUNNY_UPLOADER,
            signer=self.signer,
            image_path=file_path,  # local image to upload
            name=name,
            symbol=symbol or "$PSA",
            description=description or "Very casual description for a serious token.",
            decimals=decimals or 6,
            initial_supply=initial_supply or 1_000_000_000,  # e.g. 1,000,000.000000 tokens if decimals=6
            remove_auth=True if remove_authority == "y" else False,             # remove freeze & mint authority after
            priority_fee_sol=priority_fee_sol or 0.0001,      # pay a small priority fee
            custom_mint=True if custom_mint == "y" else False,
            is_meta_uploaded=is_meta_uploaded,
            metadata_uri=metadata_uri
        )

        cinput(f"Press anything to continue (will clear the screen)", maxlen=1)

    async def remove_authority(self):
        cprint(f"Removing authority from created token...")
        mint = cinput(f"Enter the mint CA", maxlen=44)
        await remove_authority(
            async_client=self.async_client,
            mint_pubkey=Pubkey.from_string(mint),
            user_pubkey=self.signer.pubkey(),
            signer=self.signer
        )

        cinput(f"Press anything to continue (will clear the screen)", maxlen=1)

    async def mint_to(self):
        cprint(f"Minting tokens to user ATA...")
        mint = cinput(f"Enter the mint CA", maxlen=44)
        if not mint:
            wprint(f"Mint cannot be empty")
            return
        user_pubkey = cinput(f"Enter the target user pubkey (or press enter for your own)", maxlen=44)
        amount = cinput(f"Enter the amount of tokens to mint")
        if not amount:
            wprint(f"Amount cannot be empty")
            return
        decimals = cinput(f"Enter the decimals of the token (6 by default)", maxlen=1)
        await mint_to(
            async_client=self.async_client,
            mint_pubkey=Pubkey.from_string(mint),
            user_pubkey=Pubkey.from_string(user_pubkey) if user_pubkey else self.signer.pubkey(),
            signer=self.signer,
            amount=amount,
            decimals=decimals or 6
        )

        cinput(f"Press anything to continue (will clear the screen)", maxlen=1)

    async def manage_token(self):
        cprint(f"Managing token...")
        mint = cinput(f"Enter the mint CA", maxlen=44)
        if not mint:
            wprint(f"Mint cannot be empty")
            return
        
        cprint(f"1) Remove authority")
        cprint(f"2) Mint tokens")
        cprint(f"3) Back to main menu")
        choice = cinput(f"Enter your choice")
        if choice == "1":
            await self.remove_authority()
        elif choice == "2":
            await self.mint_to()
        elif choice == "3":
            cprint(f"Going back to main menu...")
            return

        cinput(f"Press anything to continue (will clear the screen)", maxlen=1)       

    async def manage_pools(self):
        cprint(f"Managing pools...")
        cprint(f"1) Create a new pool")
        cprint(f"2) Deposit to existing pool")
        cprint(f"3) Withdraw from existing pool")
        cprint(f"4) Back to main menu")

        choice = cinput(f"Enter your choice")
        if choice == "1":
            cprint(f"Creating a new pool...")
            mint = cinput(f"Enter the mint CA", maxlen=44)
            if not mint:
                wprint(f"Mint cannot be empty")
                return
            
            cprint("Fetching decimals of the token...")
            mint_info = await self.async_client.get_account_info_json_parsed(
                Pubkey.from_string(mint),
                commitment=Processed
            )
            if not mint_info:
                print("Error: Failed to fetch mint info (tried to fetch token decimals).")
                return
            dec_base = mint_info.value.data.parsed['info']['decimals']

            quote_amount_sol = cinput(f"Enter the amount of SOL to deposit (e.g. 0.05 SOL)")
            if not quote_amount_sol:
                print("Quote amount cannot be empty")
                return
            
            base_amount_tokens = cinput(f"Enter the amount of tokens to deposit (e.g. 1B tokens == 1_000_000_000 (default))")
            if not base_amount_tokens:
                base_amount_tokens = 1_000_000_000
            
            fees = cinput(f"Enter transaction priority fee (0.0001 SOL by default)")
            if not fees:
                fees = 0.0001
            
            pool_id = await self.pump_swap.create_pool(
                Pubkey.from_string(mint),
                float(base_amount_tokens),
                float(quote_amount_sol),
                dec_base,
                fee_sol=float(fees),
            )

            print(f"Pool Address: {pool_id}")


        elif choice == "2":
            cprint(f"Depositing to existing pool...")
            pool_addr = cinput(f"Enter the pool address", maxlen=44)
            if not pool_addr:
                wprint(f"Pool address cannot be empty")

            pool_data = await self.get_pool_data(pool_addr)
            if not pool_data:
                print("Error: Failed to fetch pool data.")
                return
            
            base_amount_tokens = cinput(f"Enter the amount of tokens to deposit (e.g. 1B tokens == 1_000_000_000)")
            if not base_amount_tokens:
                print("Base amount cannot be empty")
                return
            
            sol_cap = cinput(f"Enter the MAX amount of SOL to deposit (will exit if the price is higher)")
            if not sol_cap:
                sol_cap = None
            else:
                sol_cap = float(sol_cap)

            fees = cinput(f"Enter transaction priority fee (0.0001 SOL by default)")
            if not fees:
                fees = 0.0001
            
            await self.pump_swap.deposit(
                pool_data,
                float(base_amount_tokens),
                slippage_pct=1.0,
                fee_sol=float(fees),
                sol_cap=sol_cap
            )

        elif choice == "3":
            cprint(f"Withdrawing from existing pool...")
            pool_addr = cinput(f"Enter the pool address", maxlen=44)
            if not pool_addr:
                wprint(f"Pool address cannot be empty")

            pool_data = await self.get_pool_data(pool_addr)
            if not pool_data:
                print("Error: Failed to fetch pool data.")
                return
            
            withdraw_pct = cinput(f"Enter the percentage of tokens to withdraw (e.g. 100 for 100%)")
            if not withdraw_pct:
                print("Withdraw percentage cannot be empty")
                return
            fees = cinput(f"Enter transaction priority fee (0.0001 SOL by default)")
            if not fees:
                fees = 0.0001
            
            await self.pump_swap.withdraw(
                pool_data,
                float(withdraw_pct),
                fee_sol=float(fees)
            )

        elif choice == "4":
            cprint("Going back to main menu...")
            return

        cinput(f"Press anything to continue (will clear the screen)", maxlen=1)


    async def swap_tokens(self):
        cprint(f"Swapping tokens...")
        pool_addr = await self.ask_for_pool()
        if not pool_addr:
            wprint(f"Pool address cannot be empty")
            return
        pool_data = await self.get_pool_data(pool_addr)
        if not pool_data:
            print("Error: Failed to fetch pool data.")
            return
        
        cprint(f"1) Buy tokens")
        cprint(f"2) Sell tokens")
        cprint(f"3) Back to main menu")
        choice = cinput(f"Enter your choice")

        if choice == "1":
            cprint(f"Buying tokens...")
            sol_amount = cinput(f"Enter the amount of SOL to buy (e.g. 0.05 SOL)")
            if not sol_amount:
                print("SOL amount cannot be empty")
                return
            
            slippage_pct = cinput(f"Enter the slippage percentage (5.0 by default)")
            if not slippage_pct:
                slippage_pct = 1.0
            
            fees = cinput(f"Enter transaction priority fee (0.0001 SOL by default)")
            if not fees:
                fees = 0.0001
            
            await self.pump_swap.buy(
                pool_data,
                float(sol_amount),
                slippage_pct=float(slippage_pct),
                fee_sol=float(fees)
            )

        elif choice == "2":
            cprint(f"Selling tokens...")
            sell_pct = cinput(f"Enter the percentage of tokens to sell (e.g. 100 for 100%)")
            if not sell_pct:
                print("Sell percentage cannot be empty")
                return
            
            slippage_pct = cinput(f"Enter the slippage percentage (5.0 by default, 1-100%)")
            if not slippage_pct:
                slippage_pct = 5.0
            
            fees = cinput(f"Enter transaction priority fee (0.0001 SOL by default)")
            if not fees:
                fees = 0.0001
            
            await self.pump_swap.sell(
                pool_data,
                float(sell_pct),
                float(slippage_pct),
                float(fees)
            )
        
        elif choice == "3":
            cprint(f"Going back to main menu...")
            return

        cinput(f"Press anything to continue (will clear the screen)", maxlen=1)

    async def display_main_menu(self):
        clear()
        await asyncio.sleep(0.5)
        print(f"""{self.cc.BRIGHT}
{self.cc.LIGHT_WHITE} ___                  {self.cc.LIGHT_GREEN} ___                  
{self.cc.LIGHT_WHITE}| . \\ _ _ ._ _ _  ___ {self.cc.LIGHT_GREEN}/ __> _ _ _  ___  ___ 
{self.cc.LIGHT_WHITE}|  _/| | || ' ' || . \\{self.cc.LIGHT_GREEN}\\__ \\| | | |<_> || . \\
{self.cc.LIGHT_WHITE}|_|  `___||_|_|_||  _/{self.cc.LIGHT_GREEN}<___/|__/_/ <___||  _/
{self.cc.LIGHT_WHITE}                 |_|  {self.cc.LIGHT_GREEN}                 |_|                
                    {self.cc.LIGHT_MAGENTA}url: github.com/FLOCK4H/PumpSwapAMM\n""")
        
        cprint(f"1) Create a new token")
        cprint(f"2) Manage existing token")
        cprint(f"3) Manage pools")
        cprint(f"4) Swap tokens")
        cprint(f"5) Exit")
        print()
        choice = rinput()
        if choice == "1":
            await self.create_token()
        elif choice == "2":
            await self.manage_token()
        elif choice == "3":
            await self.manage_pools()
        elif choice == "4":
            await self.swap_tokens()
        elif choice == "5":
            exit()
        
    async def run(self):
        while True:
            await self.display_main_menu()
            await asyncio.sleep(1)

async def main():
    try:
        cli = PumpSwapCLI()
        await cli.run()
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())


