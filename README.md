# Binance Futures Trading Bot MVP

Local MVP for Binance Futures Testnet and paper trading. The project follows the supplied design document: configurable strategies, risk controls, cooldowns, market data, backtesting, logging, SQLite storage, and a small FastAPI surface.

## Requirements

- Python 3.13.12
- Binance Futures Testnet keys for live testnet execution

## Setup

```powershell
.\task.ps1 setup
```

Edit `.env` with testnet credentials.

## Windows Tasks

This repo includes a PowerShell task runner, so Windows does not need `make`.

```powershell
.\task.ps1 help
.\task.ps1 test
.\task.ps1 sim
.\task.ps1 report
.\task.ps1 batch
.\task.ps1 api
.\task.ps1 web-dev
```

## Run

Paper mode is the default safe mode:

```powershell
.\task.ps1 run
```

Fully local Binance Futures simulator:

```powershell
.\task.ps1 sim
```

This mode uses deterministic generated candles and a fake account balance. It does not call Binance or require API keys.

Multi-candle simulation report:

```powershell
.\task.ps1 report
```

This exports analysis files under `reports/local_test/`:

- `summary.json`
- `trades.csv`
- `signals.csv`
- `equity_curve.csv`

Attach these files to ChatGPT when you want strategy analysis.

Robustness suite:

```powershell
.\task.ps1 batch
```

This runs multiple seeds across several simulated regimes and writes:

- `reports/local_test/batch/aggregate.json`
- `reports/local_test/batch/runs.csv`
- per-run reports under `reports/local_test/batch/<regime>/seed_<n>/`

API:

```powershell
.\task.ps1 api
```

React dashboard:

```powershell
.\task.ps1 web-install
.\task.ps1 api
.\task.ps1 web-dev
```

Open `http://127.0.0.1:5173`. The dashboard reads FastAPI data, displays reports, trades, signals, equity, and exposes safe local controls for simulator/paper state.

Tests:

```powershell
.\task.ps1 test
```

## Local Testing

Use `configs/local_test.yaml` for repeatable local testing. The config selects `simulated_binance_futures`, which is implemented by `app.exchange.simulator.SimulatedBinanceFuturesClient` and supports:

- `fetch_klines(symbol, interval, limit)` with Binance-like candle objects
- `account()` with fake testnet account data
- no network access

The main bot code uses `app.exchange.factory.build_market_data_client`, so switching between local simulation and Binance testnet is done through config instead of code changes.

For deeper analysis, run `.\task.ps1 report` or `.\task.ps1 batch`. The report uses `simulation` settings from `configs/local_test.yaml`, including candle count, market regime, seed, stop loss, take profit, fees, spread, slippage, funding, and output directory.

## Safety

The MVP is configured for paper/testnet use. Do not use real Binance Futures credentials until strategy, risk, and executor behavior have been reviewed and tested.
