from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AppConfig:
    mode: str = "paper"
    log_level: str = "INFO"


@dataclass(frozen=True)
class ExchangeConfig:
    name: str = "binance_futures"
    testnet: bool = True
    rest_url: str = "https://testnet.binancefuture.com"
    websocket_url: str = "wss://stream.binancefuture.com"


@dataclass(frozen=True)
class TradingConfig:
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframe: str = "5m"
    leverage: int = 1
    quote_balance: float = 1000.0


@dataclass(frozen=True)
class RiskConfig:
    max_risk_per_trade_percent: float = 1.0
    max_daily_loss_percent: float = 3.0
    max_open_positions: int = 1


@dataclass(frozen=True)
class CooldownConfig:
    enabled: bool = True
    after_loss_minutes: int = 10
    after_2_losses_minutes: int = 30
    after_3_losses_minutes: int = 120


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: str = "data/tradebot.sqlite3"


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "ema_cross"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationConfig:
    candles_limit: int = 1000
    output_dir: str = "reports/latest"
    seed: int = 42
    market_regime: str = "uptrend"
    stop_loss_percent: float = 1.0
    take_profit_percent: float = 2.0
    fee_rate_percent: float = 0.04
    spread_percent: float = 0.02
    slippage_percent: float = 0.01
    funding_rate_percent: float = 0.01
    funding_interval_hours: float = 8.0
    batch_seeds: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    batch_regimes: list[str] = field(default_factory=lambda: ["uptrend", "downtrend", "choppy", "high_volatility", "low_volatility"])


@dataclass(frozen=True)
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    cooldown: CooldownConfig = field(default_factory=CooldownConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{name}' must be a mapping")
    return value


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Root config must be a mapping")

    return Settings(
        app=AppConfig(**_section(raw, "app")),
        exchange=ExchangeConfig(**_section(raw, "exchange")),
        trading=TradingConfig(**_section(raw, "trading")),
        risk=RiskConfig(**_section(raw, "risk")),
        cooldown=CooldownConfig(**_section(raw, "cooldown")),
        storage=StorageConfig(**_section(raw, "storage")),
        strategy=StrategyConfig(**_section(raw, "strategy")),
        simulation=SimulationConfig(**_section(raw, "simulation")),
    )
