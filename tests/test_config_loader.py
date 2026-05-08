import pytest

from app.config.loader import load_settings


def test_loads_local_test_simulation_settings() -> None:
    settings = load_settings("configs/local_test.yaml")

    assert settings.app.mode == "simulator"
    assert settings.exchange.name == "simulated_binance_futures"
    assert settings.strategy.name == "breakout"
    assert settings.simulation.batch_regimes


def test_rejects_non_mapping_root(tmp_path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Root config"):
        load_settings(config_path)


def test_rejects_non_mapping_section(tmp_path) -> None:
    config_path = tmp_path / "bad_section.yaml"
    config_path.write_text("app: bad\n", encoding="utf-8")

    with pytest.raises(ValueError, match="section 'app'"):
        load_settings(config_path)

