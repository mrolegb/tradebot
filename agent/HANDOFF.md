# Tradebot Agent Handoff

## Current Direction

The project direction changed from a pure simulation MVP into a conservative autonomous trading runtime project.

The intended product is:

- low-frequency;
- low-leverage;
- minimal user interaction;
- safety-first;
- capable of running unattended for long periods;
- capable of pausing itself safely;
- able to recover state after restart;
- transparent about decisions and failures.

The user does NOT want:
- high-frequency trading;
- aggressive leverage;
- martingale behavior;
- overcomplicated UI;
- constant manual babysitting.

The intended workflow is:

1. User deposits a controlled amount of capital.
2. User starts the bot.
3. Bot trades conservatively.
4. Bot pauses itself if conditions become unsafe.
5. User reviews results later.

## Important Safety Philosophy

Tradebot should prefer:

- pausing over forcing trades;
- reducing risk over maximizing activity;
- holding no position over uncertain execution;
- preserving state over resetting blindly.

The project should not evolve into an unsafe “always trade” system.

## Current State

Repository:

```text
git@github.com:mrolegb/tradebot.git
```

Python target:

```text
3.13.12
```

Frontend:

```text
Node v24.13.0
npm 11.6.2
```

Current architecture includes:

- FastAPI backend
- React/Vite dashboard
- local simulator
- report generator
- batch robustness testing
- strategy layer
- risk manager
- cooldown manager
- runtime state
- SQLite runtime persistence foundation
- CI workflow

## Important Runtime Reality

Current `Start` behavior still runs repeated report-style simulations.

This is NOT yet the intended final runtime.

The next architectural goal is a true candle-driven autonomous runtime engine.

## Existing Runtime Profiles

Defined in:

```text
app/runtime/profiles.py
```

Profiles:

- `simulation`
- `binance_testnet`
- `binance_live`

Current behavior:

- `simulation` can run.
- `binance_testnet` returns `501`.
- `binance_live` returns `403`.

These guards are intentional.

Do not remove them casually.

## Current Safe Development Sequence

The recommended implementation order is:

1. Runtime persistence
2. Runtime state machine
3. Runtime audit logging
4. Circuit breaker / failsafe layer
5. Binance testnet execution adapter
6. Candle-driven runtime engine
7. Recovery/reconciliation logic
8. Dashboard runtime visibility
9. Long-running testnet soak testing
10. Only then consider live mode

## Current Active Branch

Current autonomous runtime work branch:

```text
agent/autonomous-runtime-foundation
```

This branch is intended to become the main runtime/failsafe/testnet foundation PR.

## Runtime Persistence

`app/runtime/storage.py` now exists.

Purpose:

- persist runtime snapshots;
- persist audit events;
- provide future recovery foundation.

This is intentionally infrastructure-first.

## Intended Runtime State Machine

Target lifecycle states:

```text
IDLE
STARTING
RUNNING
PAUSED
STOPPING
STOPPED
ERROR
```

The future runtime engine should use explicit transitions instead of only a boolean `running` flag.

## Intended Failsafe Behavior

The runtime should eventually pause automatically when:

- Binance latency spikes;
- stale market data is detected;
- repeated API failures occur;
- reconciliation fails;
- max daily loss triggers;
- exchange state becomes uncertain.

Desired behavior:

- stop opening new positions;
- preserve runtime state;
- wait for cooldown/backoff;
- retry safely;
- expose pause reason in dashboard/API.

## Intended Runtime Loop

The future runtime should:

1. Fetch fresh candles.
2. Validate market data freshness.
3. Evaluate strategy.
4. Run risk checks.
5. Build execution intent.
6. Execute on testnet.
7. Reconcile positions/orders.
8. Persist runtime snapshot.
9. Emit audit events.
10. Sleep until next cycle.

This should be incremental candle processing, not repeated full-report simulations.

## Dashboard Direction

The dashboard should stay simple.

Desired controls:

- Start
- Stop
- Config selection
- Strategy selection

Desired visibility:

- runtime state
- pause reason
- heartbeat
- current position
- last execution
- PnL
- drawdown
- cooldown status
- recent audit events
- failsafe state

Avoid turning the dashboard into a cluttered exchange terminal.

## Current Strategy Direction

The current strongest strategy is still `BreakoutStrategy`.

Reason:

- trend filtering;
- volatility filtering;
- reduced choppy overtrading.

However:

- runtime reliability matters more than strategy complexity right now.
- execution safety is higher priority than alpha.

## Current Known Weaknesses

1. No real candle-driven runtime yet.
2. No exchange reconciliation.
3. No open-order synchronization.
4. No persistent runtime restore yet.
5. No API latency monitor.
6. No circuit breaker.
7. No true Binance testnet execution loop.
8. No durable open-position state.
9. No recovery logic after restart.
10. No historical Binance ingestion yet.

## Important Development Constraint

Do not implement live trading by simply:

- removing the API guard;
- wiring market orders directly into Start;
- trusting in-memory runtime state;
- ignoring exchange reconciliation.

The project must become operationally reliable before it becomes live.

## Local Commands

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

## Runtime Philosophy Summary

Tradebot should behave more like:

- a cautious autonomous operator;

and less like:

- an always-on gambling engine.
