from __future__ import annotations

from app.config.loader import Settings
from app.exchange.base import MarketDataClient
from app.exchange.binance_client import BinanceFuturesClient
from app.exchange.simulator import SimulatedBinanceFuturesClient


def build_market_data_client(settings: Settings) -> MarketDataClient:
    if settings.app.mode in {"mock", "simulator", "local"} or settings.exchange.name == "simulated_binance_futures":
        return SimulatedBinanceFuturesClient(
            settings.exchange,
            seed=settings.simulation.seed,
            market_regime=settings.simulation.market_regime,
            base_balance=settings.trading.quote_balance,
        )
    return BinanceFuturesClient(settings.exchange)
