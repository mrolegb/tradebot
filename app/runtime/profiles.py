from __future__ import annotations

from dataclasses import replace

from app.config.loader import Settings, load_settings
from app.runtime.state import runtime_state


CONFIG_PROFILES = {
    "simulation": {
        "label": "Simulation",
        "config_path": "configs/local_test.yaml",
        "can_start": True,
        "runtime_mode": "simulation",
        "description": "Local simulator with generated market data.",
    },
    "binance_testnet": {
        "label": "Binance Testnet",
        "config_path": "configs/binance_testnet.yaml",
        "can_start": True,
        "runtime_mode": "testnet",
        "description": "Binance Futures testnet runtime environment.",
    },
    "binance_live": {
        "label": "Binance Live",
        "config_path": "configs/binance_live.yaml",
        "can_start": False,
        "runtime_mode": "live",
        "description": "Live Binance profile remains explicitly blocked until production hardening is complete.",
    },
}

STRATEGIES = {
    "breakout": "Breakout",
    "ema_cross": "EMA Cross",
    "rsi_mean_reversion": "RSI Mean Reversion",
}


def selected_profile() -> dict:
    return CONFIG_PROFILES[runtime_state.selected_profile]


def load_selected_settings() -> Settings:
    settings = load_settings(selected_profile()["config_path"])
    return replace(settings, strategy=replace(settings.strategy, name=runtime_state.selected_strategy))
