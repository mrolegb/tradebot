from __future__ import annotations

import asyncio
from dataclasses import replace

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.exchange.safety import execution_guard_error
from app.reporting.readers import latest_dashboard_data, read_csv, read_json
from app.runtime.profiles import CONFIG_PROFILES, STRATEGIES, load_selected_settings, selected_profile
from app.runtime.state import runtime_state
from app.runtime.trading_loop import run_binance_trading_loop
from app.simulation.batch import run_batch
from app.simulation.runner import run_simulation

app = FastAPI(title="Binance Futures Bot MVP")
load_dotenv()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_task: asyncio.Task | None = None


class SelectionRequest(BaseModel):
    value: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config")
def config() -> dict:
    settings = load_selected_settings()
    return {
        "mode": settings.app.mode,
        "symbols": settings.trading.symbols,
        "strategy": settings.strategy.name,
        "testnet": settings.exchange.testnet,
        "timeframe": settings.trading.timeframe,
        "risk": settings.risk,
        "simulation": settings.simulation,
    }


@app.get("/api/dashboard")
def dashboard() -> dict:
    settings = load_selected_settings()
    return {
        "config": config(),
        "runtime": runtime_state.snapshot(),
        "reports": latest_dashboard_data(settings.simulation.output_dir),
        "mode": settings.app.mode,
        "options": options(),
    }


@app.get("/api/options")
def options() -> dict:
    return {
        "profiles": CONFIG_PROFILES,
        "strategies": STRATEGIES,
    }


@app.get("/api/summary")
def summary() -> dict:
    return read_json(f"{load_selected_settings().simulation.output_dir}/summary.json")


@app.get("/api/trades")
def trades(limit: int = 100) -> list[dict]:
    return read_csv(f"{load_selected_settings().simulation.output_dir}/trades.csv", limit=limit)


@app.get("/api/signals")
def signals(limit: int = 100) -> list[dict]:
    return read_csv(f"{load_selected_settings().simulation.output_dir}/signals.csv", limit=limit)


@app.get("/api/equity")
def equity(limit: int = 400) -> list[dict]:
    return read_csv(f"{load_selected_settings().simulation.output_dir}/equity_curve.csv", limit=limit)


@app.get("/api/batch")
def batch() -> dict:
    return read_json(f"{load_selected_settings().simulation.output_dir}/batch/aggregate.json")


@app.post("/api/runtime/profile")
def set_profile(request: SelectionRequest) -> dict:
    if request.value not in CONFIG_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {request.value}")
    return runtime_state.select_profile(request.value)


@app.post("/api/runtime/strategy")
def set_strategy(request: SelectionRequest) -> dict:
    if request.value not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.value}")
    return runtime_state.select_strategy(request.value)


@app.post("/api/control/start")
async def start() -> dict:
    global active_task
    if runtime_state.running:
        return runtime_state.snapshot()

    profile = selected_profile()
    if not profile["can_start"]:
        raise HTTPException(status_code=501, detail=f"{profile['label']} cannot be started yet.")

    settings = load_selected_settings()
    guard_error = execution_guard_error(settings.app.mode)
    if settings.app.mode == "live" and guard_error:
        raise HTTPException(status_code=403, detail=guard_error)

    runtime_state.start()
    if runtime_state.selected_profile == "simulation":
        active_task = asyncio.create_task(_run_simulation_loop(settings))
    else:
        active_task = asyncio.create_task(run_binance_trading_loop(settings, runtime_state))
    return runtime_state.snapshot()


@app.post("/api/control/stop")
def stop() -> dict:
    global active_task
    if active_task and not active_task.done():
        active_task.cancel()
    active_task = None
    return runtime_state.stop()


@app.post("/api/simulation/report")
async def run_report() -> dict:
    settings = load_selected_settings()
    summary_data = await run_simulation(settings)
    return {"status": "completed", "summary": summary_data}


@app.post("/api/simulation/batch")
async def run_batch_report() -> dict:
    if runtime_state.selected_profile != "simulation":
        raise HTTPException(status_code=409, detail="Batch simulation is available only for the simulation profile.")
    aggregate = await asyncio.create_task(run_batch(selected_profile()["config_path"], base_settings=load_selected_settings()))
    return {"status": "completed", "aggregate": aggregate}


async def _run_simulation_loop(settings) -> None:
    try:
        while runtime_state.running:
            run_settings = replace(
                settings,
                simulation=replace(
                    settings.simulation,
                    seed=settings.simulation.seed + runtime_state.loop_count + 1,
                ),
            )
            await run_simulation(run_settings)
            runtime_state.register_loop_run()
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise
    finally:
        runtime_state.stop()
