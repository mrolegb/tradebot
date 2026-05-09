# Tradebot

Tradebot is a conservative Binance Futures trading bot project.

The long-term goal is simple: put a controlled amount of capital into Binance Futures, start the bot in the morning, leave it running with minimal manual control, and review the result in the evening. The bot should trade slowly, avoid overactivity, stop when conditions look unsafe, and explain what it did.

This repository is not trying to become a high-frequency trading system or a black-box money printer. It is a safety-first automation project for boring, cautious, rule-based trading.

## Current Status

The project is currently an MVP with:

- a local market simulator;
- strategy implementations;
- risk controls;
- cooldown handling;
- report generation;
- batch robustness simulations;
- a FastAPI backend;
- a React/Vite dashboard;
- SQLite persistence foundations;
- CI for Python tests and frontend build.

Live Binance trading is intentionally blocked. Binance testnet can be selected in the UI, but the testnet trading loop is not enabled yet. This is deliberate: the runtime, failsafe, order execution, and recovery layers must be built before real exchange execution is allowed.

## Product Idea in Plain English

The final product should work like this:

1. You configure a small set of symbols, for example BTCUSDT and ETHUSDT.
2. You choose a conservative strategy and risk profile.
3. You press Start.
4. The bot watches fresh market candles.
5. If the strategy sees a clean setup, the bot checks risk limits before entering.
6. The bot opens at most a very small number of positions.
7. Every trade has predefined risk limits, stop logic, and exit logic.
8. If market data becomes stale, Binance becomes slow, the API starts failing, or losses accumulate, the bot pauses instead of forcing trades.
9. When the pause expires and conditions look healthy again, the bot may continue.
10. At the end of the day you can see what happened: trades, PnL, drawdown, pauses, errors, and reasons for decisions.

The important part is not maximum profit. The important part is controlled behavior, transparent decisions, and predictable failure handling.

## Safety Philosophy

Tradebot should prefer doing nothing over doing something unsafe.

The intended safety rules are:

- no live trading until testnet execution is implemented and tested;
- no removing live guards just to “make it work”;
- no martingale;
- no averaging down;
- no high leverage by default;
- no unlimited position count;
- no trading when data is stale;
- no trading during API instability;
- no trading after daily loss limits are hit;
- no hidden state that disappears silently after a restart.

For a small account, the target style is slow and defensive. A normal day may include zero trades.

## Repository Layout

```text
app/
  api.py                    FastAPI backend and dashboard/control endpoints
  config/
    loader.py               YAML config loader and typed config dataclasses
  exchange/
    binance_client.py       Binance Futures REST client foundation
    factory.py              Builds the correct market data client from config
    simulator.py            Local Binance-like simulated market data client
  market/
    candles.py              Candle conversion helpers
    indicators.py           EMA, RSI, volatility and other market indicators
  reporting/
    readers.py              Reads latest report files for the dashboard/API
  risk/
    cooldown_manager.py     Cooldown rules after losing trades
    risk_manager.py         Position sizing and basic risk acceptance logic
  runtime/
    profiles.py             simulation / binance_testnet / binance_live profiles
    state.py                Runtime UI/control state
    storage.py              SQLite runtime snapshot and audit-log foundation
  simulation/
    batch.py                Multi-run robustness simulations
    cli.py                  CLI entry points for simulation/reporting
    report.py               JSON/CSV report writers
    runner.py               Report-style multi-candle simulator
  strategies/
    breakout.py             Breakout strategy with trend/volatility filters
    ema_cross.py            EMA cross strategy
    rsi_mean_reversion.py   RSI mean reversion strategy
configs/
  local_test.yaml           Safe local simulator config
  binance_testnet.yaml      Binance Futures testnet config, guarded
  binance_live.yaml         Binance Futures live config, blocked
web/
  src/main.jsx              React dashboard
  src/styles.css            Dashboard styling
  package.json              Frontend dependencies and scripts
tests/                       Python test suite
agent/
  HANDOFF.md                Current project handoff for future AI agents
reports/                     Generated simulation/report outputs, git-ignored
data/                        SQLite runtime/storage files, git-ignored
```

## Main Runtime Profiles

Tradebot has three runtime profiles.

### `simulation`

This is the only profile that can currently be started.

It uses generated market data and fake account balances. It is useful for developing strategies, reports, dashboard behavior, and risk logic without touching Binance.

### `binance_testnet`

This profile points at Binance Futures testnet configuration, but `Start` is blocked until the autonomous testnet trading loop exists.

The next major implementation work is to make this profile run safely with dry-run/testnet-only execution, persistent runtime state, and recovery logic.

### `binance_live`

This profile is intentionally blocked.

Live mode must not be enabled until testnet behavior, safeguards, exchange reconciliation, emergency stop, durable state, and audit logging are all implemented and reviewed.

## Common Commands

The project is designed for Windows PowerShell workflow.

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

## Setup

Requirements:

- Python `3.13.12`
- Node `24.x`
- npm `11.x`

Install Python dependencies:

```powershell
.\task.ps1 setup
```

Install frontend dependencies:

```powershell
.\task.ps1 web-install
```

## Running the Backend and Dashboard

Start the FastAPI backend:

```powershell
.\task.ps1 api
```

Backend URL:

```text
http://127.0.0.1:8000
```

Start the React dashboard:

```powershell
.\task.ps1 web-dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

The dashboard polls `/api/dashboard` and shows the selected config, selected strategy, runtime status, reports, trades, signals, equity curve, and batch results.

## Running Tests

```powershell
.\task.ps1 test
```

The test suite covers API guards, config loading, risk and cooldown behavior, strategy filters, simulation reports, batch aggregation, reporting readers, runtime state, Binance client guard behavior, and storage foundations.

## Running a Single Report

```powershell
.\task.ps1 report
```

This runs one simulation using the selected local config and writes:

```text
reports/local_test/summary.json
reports/local_test/trades.csv
reports/local_test/signals.csv
reports/local_test/equity_curve.csv
```

Use this when you want to inspect how one strategy/config behaved in one simulated market run.

## Running Batch Robustness Tests

```powershell
.\task.ps1 batch
```

This runs many simulations across configured seeds and regimes. It writes:

```text
reports/local_test/batch/aggregate.json
reports/local_test/batch/runs.csv
reports/local_test/batch/<regime>/seed_<n>/
```

Batch output is useful for seeing whether a strategy only works in one lucky scenario or behaves reasonably across different simulated regimes.

## How the Current Simulator Works

The current simulator is report-style. It loads a generated candle series, walks through candles, generates strategy signals, opens simulated positions, closes them by stop loss, take profit, or reverse signal, and writes reports.

It models:

- spread;
- slippage;
- fees;
- funding cost;
- stop loss;
- take profit;
- cooldown after losing trades;
- max daily loss kill switch.

It is useful, but it is not yet the final autonomous trading loop. The current Start button repeatedly runs report-style simulations with different seeds. The future runtime should instead process candles incrementally and preserve state between loops and restarts.

## Strategies

The currently most developed strategy is `BreakoutStrategy`.

It looks for a close-based breakout with:

- lookback high/low levels;
- breakout buffer;
- EMA fast/slow trend confirmation;
- minimum trend gap;
- volatility minimum and maximum filters;
- optional short trades.

Other available strategies are EMA cross and RSI mean reversion. They are useful as simple baselines, but the project should prioritize safety, filtering, and robust behavior over strategy complexity.

## Risk Controls

The current risk configuration supports:

- max risk per trade;
- max daily loss;
- max open positions;
- cooldown after losses.

For conservative operation on a small account, safer future defaults should probably be closer to:

- leverage: `1x`;
- max open positions: `1`;
- max risk per trade: `0.25%` to `0.5%`;
- max daily loss: `1%` to `2%`;
- symbols: BTCUSDT and/or ETHUSDT only at first;
- live shorts disabled initially.

These are not guarantees of profit or safety. They are just more conservative operating constraints.

## Persistence and Audit Log

`app/runtime/storage.py` introduces SQLite runtime persistence foundations.

The purpose is to stop important runtime information from existing only in memory. Future runtime work should persist:

- current lifecycle state;
- selected profile;
- selected strategy;
- pause reason;
- cooldown expiry;
- last heartbeat;
- last processed candle;
- open position snapshot;
- order snapshot;
- audit events.

This is important because a trading bot must be able to restart and understand what it was doing before it crashed or was stopped.

## Next Major Work

The next development target is the autonomous runtime foundation:

1. Add an explicit runtime state machine.
2. Wire runtime state into SQLite persistence.
3. Add failsafe/circuit breaker logic for API errors, latency spikes, and stale data.
4. Expand the Binance testnet adapter with safe execution primitives.
5. Build a candle-driven runtime engine.
6. Expose runtime health, pause reasons, and audit events in the dashboard.
7. Add tests around recovery, failsafe behavior, and guarded execution.

## What Not To Do Yet

Do not enable live trading by removing guards.

Do not wire real Binance order placement directly to the Start button before these exist:

- exchange position reconciliation;
- open order reconciliation;
- precision and min-notional handling;
- leverage setup verification;
- balance checks;
- stop-loss/take-profit order handling;
- emergency stop;
- API retry/backoff;
- durable state;
- audit log;
- long-running testnet validation.

## Generated Files

The following are generated locally and should not be committed:

- `reports/`
- `data/`
- `web/node_modules/`
- `web/dist/`

## Disclaimer

This is trading software. It can lose money. The project should be treated as engineering infrastructure first and trading automation second. The safest bot is often the one that decides not to trade.
