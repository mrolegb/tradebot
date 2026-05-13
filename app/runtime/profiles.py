from __future__ import annotations

from dataclasses import replace

from app.config.loader import Settings, StrategyConfig, load_settings
from app.runtime.state import runtime_state


CONFIG_PROFILES = {
    "simulation": {
        "label": "Simulation",
        "config_path": "configs/local_test.yaml",
        "can_start": True,
        "description": "Local simulator with generated market data.",
    },
    "binance_testnet": {
        "label": "Binance Testnet",
        "config_path": "configs/binance_testnet.yaml",
        "can_start": True,
        "description": "Binance Futures testnet profile. Uses dry-run unless BINANCE_TESTNET_EXECUTION_ENABLED=true.",
    },
    "binance_live": {
        "label": "Binance Live",
        "config_path": "configs/binance_live.yaml",
        "can_start": True,
        "description": "Live Binance profile. Requires explicit live execution environment confirmation.",
    },
}

STRATEGIES = {
    "breakout": "Breakout",
    "ema_cross": "EMA Cross",
    "rsi_mean_reversion": "RSI Mean Reversion",
}

STRATEGY_CONFIGS = {
    "breakout": "configs/breakout_strategy.yaml",
    "ema_cross": "configs/ema_strategy.yaml",
    "rsi_mean_reversion": "configs/rsi_strategy.yaml",
}


def selected_profile() -> dict:
    return CONFIG_PROFILES[runtime_state.selected_profile]


def load_selected_settings() -> Settings:
    settings = load_settings(selected_profile()["config_path"])
    return replace(settings, strategy=load_strategy_config(runtime_state.selected_strategy))


def load_strategy_config(strategy: str) -> StrategyConfig:
    config_path = STRATEGY_CONFIGS.get(strategy)
    if not config_path:
        raise ValueError(f"Unknown strategy: {strategy}")
    strategy_settings = load_settings(config_path)
    if strategy_settings.strategy.name != strategy:
        raise ValueError(f"Strategy config {config_path} defines {strategy_settings.strategy.name}, expected {strategy}")
    return strategy_settings.strategy
