# let `python -m pumpswapcli` work as well as the entry-point
from .cli import PumpSwapCLI
__all__ = ["PumpSwapCLI"]