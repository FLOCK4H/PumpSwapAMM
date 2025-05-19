#  ─── PumpSwapAMM/setup.py ──────────────────────────────────────────────────
from pathlib import Path
from setuptools import setup, find_packages

this_dir = Path(__file__).parent
setup(
    name            = "PumpSwapAMM",
    version         = "2.0.7",
    description     = "Python SDK + optional CLI for Pump.fun’s PumpSwap AMM on Solana",
    long_description= (this_dir / "README.md").read_text(),
    long_description_content_type="text/markdown",
    author          = "FLOCK4H",
    license         = "MIT",
    python_requires = ">=3.10",
    packages=["PumpSwapAMM", "pumpswapcli"],
    package_dir={
        "PumpSwapAMM": "pumpswapamm",
    },
    include_package_data = True,

    install_requires=[
        "solana==0.35.1",          # RPC client + spl-token helpers
        "solders==0.21.0",         # Rust bindings – signatures / PDAs
        "construct",         # binary layout parsing
        "base58",
        "python-dotenv",    # .env convenience
        "requests>=2.31.0",        # Bunny CDN uploader
        "Pillow>=10.2.0",          # image header sniffs for metadata (cli)
        "readchar>=4.2.1",
    ],

    extras_require={
        # GUI needs Tk headers on Linux
        "cli": ["Tkinter-Designer>=1.0.2 ; sys_platform=='win32'"],
        "dev": ["black", "ruff", "pytest", "mypy"],
    },

    entry_points={
        "console_scripts": [
            # `pip install --editable .[cli]` gives you:
            "pumpswap = pumpswapcli.__main__:main",
        ]
    },

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)