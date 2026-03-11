from setuptools import setup, find_packages

setup(
    name="decisionledger",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["httpx>=0.25.0"],
    python_requires=">=3.10",
    description="Python SDK for DecisionLedger SaaS API",
    author="LedgerStone",
)
