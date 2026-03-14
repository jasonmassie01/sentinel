"""
BTC price feed and on-chain balance lookup.

Uses public APIs only — no API keys required:
- CoinGecko for price data
- Mempool.space / Blockstream.info for on-chain lookups
"""

import httpx
from dataclasses import dataclass
from typing import Optional

from app.config import settings

COINGECKO_PRICE_URL = f"{settings.btc_price_api}/simple/price"
MEMPOOL_ADDRESS_URL = f"{settings.mempool_api}/address"
MEMPOOL_FEE_URL = f"{settings.mempool_api}/v1/fees/recommended"
BLOCKSTREAM_ADDRESS_URL = "https://blockstream.info/api/address"


@dataclass
class BTCPrice:
    usd: float
    usd_24h_change: Optional[float] = None
    usd_market_cap: Optional[float] = None
    last_updated: Optional[str] = None


@dataclass
class UTXO:
    txid: str
    vout: int
    value: int  # satoshis
    status_confirmed: bool


@dataclass
class AddressInfo:
    address: str
    funded_sats: int
    spent_sats: int
    balance_sats: int
    balance_btc: float
    tx_count: int
    utxos: list[UTXO]


@dataclass
class FeeEstimate:
    fastest: int  # sat/vB
    half_hour: int
    hour: int
    economy: int
    minimum: int


async def get_btc_price() -> BTCPrice:
    """Fetch current BTC price from CoinGecko."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            COINGECKO_PRICE_URL,
            params={
                "ids": "bitcoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_market_cap": "true",
                "include_last_updated_at": "true",
            },
        )
        resp.raise_for_status()
        data = resp.json()["bitcoin"]

    return BTCPrice(
        usd=data["usd"],
        usd_24h_change=data.get("usd_24h_change"),
        usd_market_cap=data.get("usd_market_cap"),
        last_updated=str(data.get("last_updated_at", "")),
    )


async def get_address_info(address: str) -> AddressInfo:
    """
    Look up BTC address balance and UTXOs via Mempool.space.
    Falls back to Blockstream.info if Mempool is unavailable.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Try Mempool first
        try:
            addr_resp = await client.get(f"{MEMPOOL_ADDRESS_URL}/{address}")
            addr_resp.raise_for_status()
            addr_data = addr_resp.json()

            utxo_resp = await client.get(f"{MEMPOOL_ADDRESS_URL}/{address}/utxo")
            utxo_resp.raise_for_status()
            utxo_data = utxo_resp.json()
        except (httpx.HTTPError, httpx.TimeoutException):
            # Fallback to Blockstream
            addr_resp = await client.get(f"{BLOCKSTREAM_ADDRESS_URL}/{address}")
            addr_resp.raise_for_status()
            addr_data = addr_resp.json()

            utxo_resp = await client.get(f"{BLOCKSTREAM_ADDRESS_URL}/{address}/utxo")
            utxo_resp.raise_for_status()
            utxo_data = utxo_resp.json()

    chain_stats = addr_data.get("chain_stats", {})
    mempool_stats = addr_data.get("mempool_stats", {})

    funded = chain_stats.get("funded_txo_sum", 0) + mempool_stats.get("funded_txo_sum", 0)
    spent = chain_stats.get("spent_txo_sum", 0) + mempool_stats.get("spent_txo_sum", 0)
    balance_sats = funded - spent
    tx_count = chain_stats.get("tx_count", 0) + mempool_stats.get("tx_count", 0)

    utxos = [
        UTXO(
            txid=u["txid"],
            vout=u["vout"],
            value=u["value"],
            status_confirmed=u.get("status", {}).get("confirmed", False),
        )
        for u in utxo_data
    ]

    return AddressInfo(
        address=address,
        funded_sats=funded,
        spent_sats=spent,
        balance_sats=balance_sats,
        balance_btc=balance_sats / 1e8,
        tx_count=tx_count,
        utxos=utxos,
    )


async def get_fee_estimates() -> FeeEstimate:
    """Get current mempool fee rate estimates."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(MEMPOOL_FEE_URL)
        resp.raise_for_status()
        data = resp.json()

    return FeeEstimate(
        fastest=data["fastestFee"],
        half_hour=data["halfHourFee"],
        hour=data["hourFee"],
        economy=data["economyFee"],
        minimum=data["minimumFee"],
    )
