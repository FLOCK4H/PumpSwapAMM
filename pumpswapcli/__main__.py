import asyncio, sys
from .cli import PumpSwapCLI

def main() -> None:
    try:
        asyncio.run(PumpSwapCLI().run())
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()