# Tradebot Agent Handoff

## Project State

Repository: `D:\projects\tradebot`

Python target: `3.13.12`

Node/npm:
- Node `v24.13.0`
- npm `11.6.2`

The project is a Binance Futures trading bot MVP with:
- local generated-market simulation
- strategy layer
- risk/cooldown controls
- report generation
- batch robustness simulations
- guarded Binance testnet/live execution path
- SQLite storage for trades, runtime snapshots, and positions
- FastAPI backend
- React/Vite dashboard

Git remote:

```text
git@github.com:mrolegb/tradebot.git
```

## Common Commands

```powershell
.\task.ps1 setup
.\task.ps1 test
.\task.ps1 compile
.\task.ps1 sim
.\task.ps1 local-smoke
.\task.ps1 testnet
.\task.ps1 testnet-smoke
.\task.ps1 live
.\task.ps1 live-smoke
.\task.ps1 report
.\task.ps1 batch
.\task.ps1 api
.\task.ps1 web-install
.\task.ps1 web-dev
.\task.ps1 web-build
```

Current verification status:

```powershell
.\task.ps1 test
# 40 passed

.\task.ps1 compile
# app and tests compile

.\task.ps1 web-build
# succeeds; Vite warns that the JS chunk is over 500 kB
```

## Execution Modes

### Local Simulation

Command:

```powershell
.\task.ps1 sim
```

Config:

```text
configs/local_test.yaml
```

This uses `app.exchange.simulator.SimulatedBinanceFuturesClient`. It does not call Binance and does not need API keys.

Smoke command:

```powershell
.\task.ps1 local-smoke
```

It runs a short report simulation under `reports/local_test/smoke/` and verifies expected output files exist.

### Binance Testnet

Command:

```powershell
.\task.ps1 testnet
```

Config:

```text
configs/binance_testnet.yaml
```

By default, testnet execution is guarded dry-run. Real testnet orders require:

```powershell
$env:BINANCE_TESTNET_EXECUTION_ENABLED="true"
```

Credentials are loaded from `.env`:

```text
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
```

Smoke command:

```powershell
.\task.ps1 testnet-smoke
```

It checks:
- signed account endpoint
- exchange info/rules
- candles
- position risk
- quantity normalization
- cancel-all path
- market order path
- close-position path

Without `BINANCE_TESTNET_EXECUTION_ENABLED=true`, the order step remains dry-run. With the flag enabled, it opens and closes a minimal testnet position.

### Binance Live

Command:

```powershell
.\task.ps1 live
```

Config:

```text
configs/binance_live.yaml
```

Live execution is blocked unless both guards are present:

```powershell
$env:BINANCE_LIVE_EXECUTION_ENABLED="true"
$env:BINANCE_LIVE_CONFIRM="I_UNDERSTAND_THIS_CAN_LOSE_MONEY"
```

Do not bypass these guards casually.

Live smoke requires one extra guard:

```powershell
$env:BINANCE_LIVE_SMOKE_CONFIRM="PLACE_LIVE_SMOKE_ORDER"
.\task.ps1 live-smoke
```

Smoke sizing:

```powershell
$env:BINANCE_SMOKE_SYMBOL="BTCUSDT"
$env:BINANCE_SMOKE_NOTIONAL_USDT="10"
```

## Main Structure

```text
app/
  api.py
  main.py
  config/loader.py
  exchange/
    binance_client.py
    factory.py
    order_executor.py
    safety.py
    simulator.py
  market/
    candles.py
    indicators.py
  risk/
    risk_manager.py
    cooldown_manager.py
  runtime/
    profiles.py
    state.py
    trading_loop.py
  simulation/
    runner.py
    batch.py
    cli.py
    report.py
  storage/
    database.py
    models.py
  strategies/
    breakout.py
    ema_cross.py
    rsi_mean_reversion.py
web/
  src/main.jsx
  src/styles.css
configs/
  local_test.yaml
  binance_testnet.yaml
  binance_live.yaml
tests/
agent/
  HANDOFF.md
  STRATEGIES_101.md
```

## Runtime Profiles

Defined in `app/runtime/profiles.py`.

Profiles:
- `simulation`
- `binance_testnet`
- `binance_live`

`POST /api/control/start` in `app/api.py`:
- starts `_run_simulation_loop()` for `simulation`
- starts `run_binance_trading_loop()` for `binance_testnet` and `binance_live`
- rejects live start with HTTP 403 unless live env guards are present
- allows testnet start, but Binance orders remain dry-run unless `BINANCE_TESTNET_EXECUTION_ENABLED=true`

## Binance Execution Path

Important files:
- `app/exchange/binance_client.py`
- `app/exchange/order_executor.py`
- `app/exchange/safety.py`
- `app/runtime/trading_loop.py`
- `app/runtime/smoke.py`

Implemented Binance REST operations:
- public klines
- exchange info
- signed account
- signed position risk
- change leverage
- market order
- cancel all open orders

Smoke coverage:
- local report generation smoke
- testnet account/rules/candle/position/order-flow smoke
- live smoke with extra confirmation

`BinanceOrderExecutor`:
- loads symbol rules from `exchangeInfo`
- normalizes quantity using `LOT_SIZE.stepSize`
- checks minimum quantity and minimum notional
- supports dry-run orders
- sends market orders when guards allow it
- can close an existing position by placing the opposite market order

## Simulation Behavior

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
- intrabar stop/take checks using candle `high` and `low`
- equity curve with unrealized PnL while a position is open

Simulation reports are written under:

```text
reports/local_test/
```

Files:
- `summary.json`
- `trades.csv`
- `signals.csv`
- `equity_curve.csv`

Batch reports:

```text
reports/local_test/batch/
```

## Dashboard Behavior

React dashboard is in `web/src/main.jsx`.

Controls:
- Config dropdown
- Strategy dropdown
- `Start`
- `Stop`
- `Run Report`
- `Run Batch`

Dashboard polls `/api/dashboard` every 5 seconds.

Known UI limitation:
- long `Run Batch` requests are still synchronous HTTP calls
- no frontend component tests yet
- Vite build succeeds but warns about one chunk over 500 kB

## Test Coverage

Current Python test suite has 40 tests.

Covered areas:
- API dashboard/options behavior
- API profile and strategy validation
- API simulation/testnet/live start behavior
- live/testnet env safety guards
- API start/stop happy path with mocked background task
- batch aggregate calculations
- Binance signed endpoint credentials guard
- Binance executor dry-run and quantity normalization
- Binance trading loop one-cycle dry-run behavior
- Binance smoke dry-run behavior
- live smoke extra confirmation guard
- config loader validation
- cooldown manager
- risk manager
- simulator candles and account behavior
- simulation report file generation
- intrabar stop/take checks
- strategy factory
- breakout filters
- indicators
- reporting readers
- runtime state
- SQLite trade, runtime, and position persistence
- backtest engine smoke behavior

## Strategy State

Strategy implementations live in `app/strategies/`.

Available strategies:
- `breakout`
- `ema_cross`
- `rsi_mean_reversion`

The most developed strategy is `BreakoutStrategy`.

Current breakout filters:
- previous close breakout level
- breakout buffer
- EMA fast/slow trend confirmation
- minimum trend gap
- rolling volatility min/max filter
- optional shorts

See `agent/STRATEGIES_101.md` for a plain-English explanation.

## Known Limitations

1. Simulation still uses generated candles, not downloaded historical Binance data.
2. The API `Start` simulation loop still repeats report-style simulations with different seeds.
3. Binance live/testnet path uses polling REST, not websocket/user-data streams.
4. No bracket stop-loss/take-profit orders are placed on Binance yet; exits are handled by loop logic.
5. No margin type setup yet.
6. No emergency close-all endpoint in the dashboard yet.
7. Runtime state persistence exists, but startup recovery is not fully wired into API startup.
8. Long-running batch/report jobs should be moved to background job state with progress.
9. Frontend component tests are still missing.

## Good Next Steps

1. Add historical Binance kline ingestion and cache.
2. Add startup recovery from SQLite runtime/positions.
3. Add Binance margin type setup and bracket stop/take orders.
4. Add emergency close-all/cancel-all API with explicit confirmation.
5. Replace API long-running report/batch calls with background jobs and progress.
6. Add frontend tests for profile switching and control states.
7. Add websocket/user-data stream support for real fill/position updates.

## Safety Notes

Live trading can lose money. Keep the live env guards intact.

Before increasing size on production:
- test on local simulation
- test on Binance testnet with tiny quantities
- inspect `data/*.sqlite3`
- inspect generated reports
- check Binance UI positions manually
- verify API key permissions and IP restrictions
