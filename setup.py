from setuptools import setup, find_packages
from pathlib import Path

setup(
    name='PumpSwapAMM',
    version='1.0.0',
    description='Unofficial client for Pump.fun PumpSwap AMM pools',
    author='FLOCK4H',
    author_email='flock4h@gmail.com',
    url='https://github.com/FLOCK4H/PumpSwapAMM',
    py_modules=["PumpSwapAMM", "fetch_reserves"],
    install_requires=[
        "solana==0.35.1",
        "solders==0.21.0",
        "construct",
        "base58",
    ],
    python_requires='>=3.9',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)