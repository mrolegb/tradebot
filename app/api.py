from __future__ import annotations

import asyncio
from dataclasses import replace
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.exchange.factory import build_market_data_client
from app.reporting.readers import latest_dashboard_data, read_csv, read_json
from app.runtime.engine import CandleRuntimeEngine, ExecutionMode
from app.runtime.profiles import CONFIG_PROFILES, STRATEGIES, load_selected_settings, selected_profile
from app.runtime.state import runtime_state
from app.simulation.batch import run_batch
from app.simulation.runner import run_simulation

app = FastAPI(title="Binance Futures Bot MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_task: asyncio.Task | None = None
last_engine_cycle: dict | None = None


class SelectionRequest(BaseModel):
    value: str


class RuntimeCycleRequest(BaseModel):
    symbol: str | None = None
    mode: str = "dry_run"
    lookback: int = 200


@app.get("/health")
def health() -> dict:
    snapshot = runtime_state.snapshot()
    return {
        "status": "ok",
        "runtime_status": snapshot["runtime_status"],
        "runtime_health": snapshot["health"],
    }


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
    runtime_snapshot = runtime_state.snapshot()
    return {
        "config": config(),
        "runtime": runtime_snapshot,
        "runtime_health": runtime_snapshot["health"],
        "runtime_status": runtime_snapshot["runtime_status"],
        "engine": last_engine_cycle,
        "reports": latest_dashboard_data(),
        "mode": settings.app.mode,
        "options": options(),
    }


@app.get("/api/runtime")
def runtime() -> dict:
    return runtime_state.snapshot()


@app.get("/api/runtime/audit")
def runtime_audit(limit: int = 100) -> list[dict]:
    return runtime_state.audit_events(limit=limit)


@app.get("/api/runtime/engine")
def runtime_engine_status() -> dict:
    return {"last_cycle": last_engine_cycle}


@app.get("/api/options")
def options() -> dict:
    return {
        "profiles": CONFIG_PROFILES,
        "strategies": STRATEGIES,
    }


@app.get("/api/summary")
def summary() -> dict:
    return read_json("reports/local_test/summary.json")


@app.get("/api/trades")
def trades(limit: int = 100) -> list[dict]:
    return read_csv("reports/local_test/trades.csv", limit=limit)


@app.get("/api/signals")
def signals(limit: int = 100) -> list[dict]:
    return read_csv("reports/local_test/signals.csv", limit=limit)


@app.get("/api/equity")
def equity(limit: int = 400) -> list[dict]:
    return read_csv("reports/local_test/equity_curve.csv", limit=limit)


@app.get("/api/batch")
def batch() -> dict:
    return read_json("reports/local_test/batch/aggregate.json")


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
    if runtime_state.selected_profile == "binance_live":
        raise HTTPException(status_code=403, detail="Live Binance start is blocked until live execution safeguards are implemented.")
    if runtime_state.selected_profile == "binance_testnet":
        raise HTTPException(status_code=501, detail="Binance testnet trading loop is not implemented yet. Use Simulation for now.")
    if not profile["can_start"]:
        raise HTTPException(status_code=501, detail=f"{profile['label']} cannot be started yet.")

    runtime_state.start()
    settings = load_selected_settings()
    active_task = asyncio.create_task(_run_simulation_loop(settings))
    return runtime_state.snapshot()


@app.post("/api/control/stop")
def stop() -> dict:
    global active_task
    if active_task and not active_task.done():
        active_task.cancel()
    active_task = None
    return runtime_state.stop()


@app.post("/api/control/pause")
def pause() -> dict:
    global active_task
    if active_task and not active_task.done():
        active_task.cancel()
    active_task = None
    return runtime_state.pause("manual_pause")


@app.post("/api/runtime/engine/cycle")
async def run_engine_cycle(request: RuntimeCycleRequest) -> dict:
    global last_engine_cycle
    if request.mode not in {ExecutionMode.DRY_RUN, ExecutionMode.TESTNET}:
        raise HTTPException(status_code=400, detail=f"Unknown engine mode: {request.mode}")
    if request.mode == ExecutionMode.TESTNET and runtime_state.selected_profile != "binance_testnet":
        raise HTTPException(status_code=409, detail="Testnet engine mode requires the Binance Testnet profile.")
    if runtime_state.selected_profile == "binance_live":
        raise HTTPException(status_code=403, detail="Live engine execution is blocked.")

    settings = load_selected_settings()
    symbol = request.symbol or settings.trading.symbols[0]
    client = build_market_data_client(settings)
    engine = CandleRuntimeEngine(
        client,
        mode=ExecutionMode(request.mode),
        allow_shorts=False,
        max_open_positions=settings.risk.max_open_positions,
    )
    try:
        last_engine_cycle = await engine.runtime_cycle(
            symbol=symbol,
            interval=settings.trading.timeframe,
            lookback=request.lookback,
        )
        return {"status": "completed", "cycle": last_engine_cycle}
    finally:
        await client.close()


@app.post("/api/runtime/engine/recover")
async def recover_engine(request: RuntimeCycleRequest) -> dict:
    global last_engine_cycle
    if runtime_state.selected_profile == "binance_live":
        raise HTTPException(status_code=403, detail="Live recovery is blocked.")

    settings = load_selected_settings()
    symbol = request.symbol or settings.trading.symbols[0]
    client = build_market_data_client(settings)
    engine = CandleRuntimeEngine(
        client,
        mode=ExecutionMode.DRY_RUN,
        allow_shorts=False,
        max_open_positions=settings.risk.max_open_positions,
    )
    try:
        reconciliation = await engine.recover(symbol=symbol)
        last_engine_cycle = {"status": "recovered", "symbol": symbol, "reconciliation": reconciliation}
        return last_engine_cycle
    finally:
        await client.close()


@app.post("/api/simulation/report")
async def run_report() -> dict:
    settings = load_selected_settings()
    started_at = perf_counter()
    try:
        summary_data = await run_simulation(settings)
    except Exception as exc:
        runtime_state.record_runtime_failure(f"report_failed:{exc.__class__.__name__}")
        raise
    runtime_state.record_market_data(latency_ms=(perf_counter() - started_at) * 1000)
    runtime_state.record_runtime_success()
    return {"status": "completed", "summary": summary_data}


@app.post("/api/simulation/batch")
async def run_batch_report() -> dict:
    if runtime_state.selected_profile != "simulation":
        raise HTTPException(status_code=409, detail="Batch simulation is available only for the simulation profile.")
    started_at = perf_counter()
    try:
        aggregate = await asyncio.create_task(run_batch(selected_profile()["config_path"], base_settings=load_selected_settings()))
    except Exception as exc:
        runtime_state.record_runtime_failure(f"batch_failed:{exc.__class__.__name__}")
        raise
    runtime_state.record_market_data(latency_ms=(perf_counter() - started_at) * 1000)
    runtime_state.record_runtime_success()
    return {"status": "completed", "aggregate": aggregate}


async def _run_simulation_loop(settings) -> None:
    try:
        while runtime_state.running:
            runtime_state.heartbeat()
            run_settings = replace(
                settings,
                simulation=replace(
                    settings.simulation,
                    seed=settings.simulation.seed + runtime_state.loop_count + 1,
                ),
            )
            started_at = perf_counter()
            try:
                await run_simulation(run_settings)
            except Exception as exc:
                runtime_state.record_runtime_failure(f"simulation_loop_failed:{exc.__class__.__name__}")
                await asyncio.sleep(5)
                continue
            runtime_state.record_market_data(latency_ms=(perf_counter() - started_at) * 1000)
            runtime_state.record_runtime_success()
            runtime_state.register_loop_run()
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise
    finally:
        if runtime_state.running:
            runtime_state.stop()
