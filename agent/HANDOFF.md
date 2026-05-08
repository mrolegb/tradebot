# Tradebot Agent Handoff

## Project State

Repository: `D:\projects\tradebot`

Python target: `3.13.12`

Node/npm:
- Node `v24.13.0`
- npm `11.6.2`

The project is a Binance Futures trading bot MVP with:
- local simulator
- strategy layer
- risk/cooldown controls
- report generation
- batch robustness simulations
- FastAPI backend
- React/Vite dashboard

Git repository is initialized, but commits may still be blocked until local git identity is configured.

## Current Running Services

Backend:

```powershell
http://127.0.0.1:8000
```

Frontend:

```powershell
http://127.0.0.1:5173
```

If services need restart:

```powershell
.\task.ps1 api
.\task.ps1 web-dev
```

The user usually works from PowerShell on Windows.

## Common Commands

```powershell
.\task.ps1 setup
.\task.ps1 test
.\task.ps1 report
.\task.ps1 batch
.\task.ps1 api
.\task.ps1 web-install
.\task.ps1 web-dev
.\task.ps1 web-build
```

Tests currently pass:

```powershell
.\task.ps1 test
# 6 passed
```

Frontend build currently succeeds:

```powershell
.\task.ps1 web-build
```

## Main Structure

```text
app/
  api.py
  config/loader.py
  exchange/
    binance_client.py
    simulator.py
    factory.py
  market/
    candles.py
    indicators.py
  risk/
    risk_manager.py
    cooldown_manager.py
  simulation/
    runner.py
    batch.py
    cli.py
    report.py
  strategies/
    breakout.py
    ema_cross.py
    rsi_mean_reversion.py
  runtime/
    state.py
    profiles.py
  reporting/
    readers.py
web/
  package.json
  vite.config.js
  src/main.jsx
  src/styles.css
configs/
  local_test.yaml
  binance_testnet.yaml
  binance_live.yaml
tests/
agent/
  HANDOFF.md
```

## Runtime Profiles

Defined in `app/runtime/profiles.py`.

Profiles:
- `simulation`
- `binance_testnet`
- `binance_live`

Current safety behavior:
- `simulation` can start.
- `binance_testnet` can be selected, but `Start` returns `501` because the live/testnet trading loop is not implemented yet.
- `binance_live` can be selected, but `Start` returns `403`; this is intentional until live safeguards and real exchange execution are implemented.

Do not remove these guards casually.

## Dashboard Behavior

React dashboard is in `web/src/main.jsx`.

Current controls:
- Config dropdown
- Strategy dropdown
- `Start`
- `Stop`
- `Run Report`
- `Run Batch`

Removed by user request:
- Pause
- Resume
- Close All Sim

Dashboard polls `/api/dashboard` every 5 seconds.

Important visual indicators:
- `Running` / `Stopped`
- `Loop Runs`
- `Last Run`
- latest report summary
- equity chart
- latest trades
- latest signals
- batch by regime table

## Start / Stop Behavior

Implemented in `app/api.py`.

`POST /api/control/start`:
- checks selected profile
- starts an asyncio background task for simulation profile
- the task loops until stopped
- each loop runs `run_simulation(settings)`
- each loop uses a new seed:

```python
seed = settings.simulation.seed + runtime_state.loop_count + 1
```

- after each run, `runtime_state.register_loop_run()` increments `loop_count`
- waits 5 seconds before the next run

`POST /api/control/stop`:
- cancels the active task
- sets runtime `running = False`

Current simulation loop is not real-time market replay. It repeatedly runs report-style simulations with different seeds and overwrites `reports/local_test/*`.

## Run Report / Run Batch

`Run Report`:
- endpoint: `POST /api/simulation/report`
- runs one simulation using the selected profile/strategy
- writes:

```text
reports/local_test/summary.json
reports/local_test/trades.csv
reports/local_test/signals.csv
reports/local_test/equity_curve.csv
```

`Run Batch`:
- endpoint: `POST /api/simulation/batch`
- only allowed for `simulation` profile
- runs all configured seeds/regimes from `configs/local_test.yaml`
- writes:

```text
reports/local_test/batch/aggregate.json
reports/local_test/batch/runs.csv
reports/local_test/batch/<regime>/seed_<n>/
```

## Strategy State

The most developed strategy is `BreakoutStrategy` in `app/strategies/breakout.py`.

Current filters:
- close-based breakout level
- breakout buffer
- EMA fast/slow trend confirmation
- minimum trend gap
- rolling volatility min/max filter
- optional shorts

`rolling_volatility()` is in `app/market/indicators.py`.

The strategy was improved because the original breakout logic overtraded choppy/high-volatility regimes.

## Risk / Simulation Behavior

Simulation runner: `app/simulation/runner.py`.

Includes:
- spread
- slippage
- fees
- funding cost
- stop loss
- take profit
- cooldown after losing trade
- max daily loss kill switch

Current max daily loss behavior:
- uses `risk.max_daily_loss_percent`
- stops opening new positions when balance falls below allowed daily loss

## Latest Robustness Result

After improvements, batch behavior was approximately:

```text
Runs:              50
Positive runs:     20
Failure rate:      60%
Mean return:       +2.63%
Median return:      0.00%
Worst run:         -4.11%
Best run:         +13.82%
Worst drawdown:    -4.11%
```

Regime behavior:

```text
uptrend:          profitable
downtrend:        profitable
low_volatility:   no trades
choppy:           controlled loss via kill switch
high_volatility:  controlled loss via kill switch
```

Main takeaway:
- risk is much better controlled than before
- strategy is still regime-dependent
- choppy/high-volatility filters need further work

## Reports Are Ignored

Generated reports are under `reports/` and are git-ignored.

`web/node_modules/` and `web/dist/` are also git-ignored.

## Known Limitations

1. Binance testnet/live trading loop is not implemented.
2. Real order placement is intentionally gated.
3. `Close All` real exchange control does not exist yet.
4. UI control state is in-memory only; restarting backend resets it.
5. Simulation loop overwrites latest report files each cycle.
6. Simulation is synthetic, not historical Binance data.
7. Current simulator prices are generated, not downloaded.
8. Batch runs can take roughly 1-2 minutes depending on machine load.

## Good Next Steps

Recommended next technical steps:

1. Add historical data ingestion from Binance testnet/public klines.
2. Add symbol universe selection and `symbol_rankings.csv`.
3. Persist runtime state and open positions in SQLite.
4. Replace repeated report loop with true candle-by-candle simulation state.
5. Implement Binance testnet trading loop with dry-run guard.
6. Add explicit confirmation and env flag before enabling live mode.
7. Improve dashboard feedback while long tasks run.
8. Add backend tests for profile selection and start/stop behavior.

## Safety Notes

Do not enable live trading by simply removing the API guard.

Before live/testnet start is allowed, implement:
- exchange position fetch
- order placement
- order cancellation
- close position
- precision/min-notional handling
- leverage setup
- account balance verification
- emergency stop
- durable state
- audit logging

The current dashboard controls are safe for simulator only.

