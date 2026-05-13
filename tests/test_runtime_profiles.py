from app.runtime.profiles import STRATEGIES, load_selected_settings
from app.runtime.state import runtime_state
from app.strategies import build_strategy


def test_selected_strategy_loads_matching_constructible_params() -> None:
    original_profile = runtime_state.selected_profile
    original_strategy = runtime_state.selected_strategy
    try:
        runtime_state.selected_profile = "simulation"
        for strategy in STRATEGIES:
            runtime_state.selected_strategy = strategy

            settings = load_selected_settings()

            assert settings.strategy.name == strategy
            build_strategy(settings.strategy.name, settings.strategy.params)
    finally:
        runtime_state.selected_profile = original_profile
        runtime_state.selected_strategy = original_strategy
