# Tradebot

Tradebot is a conservative autonomous crypto trading runtime focused on:

- low-frequency trading;
- low leverage;
- operational safety;
- runtime reliability;
- minimal user babysitting;
- transparent runtime behavior.

The intended workflow is intentionally simple:

1. Deposit a controlled amount of capital.
2. Start the runtime.
3. Let the bot operate conservatively.
4. Review results later.
5. Allow the runtime to pause itself automatically if conditions become unsafe.

Tradebot is intentionally NOT designed to be:

- a high-frequency trading system;
- a martingale bot;
- a gambling engine;
- a "trade every candle" strategy;
- a complicated professional terminal.

---

# Current Project State

The project has evolved beyond a pure simulator.

Current architecture includes:

## Backend

- FastAPI runtime API
- candle-driven runtime engine
- runtime supervisor
- reconciliation layer
- dry-run execution layer
- guarded Binance Futures testnet foundation
- runtime persistence
- watchdog/failsafe foundation
- recovery foundation
- runtime operations storage
- autonomous scheduler foundation

## Frontend

- React/Vite dashboard
- runtime health visibility
- supervisor visibility
- engine cycle visibility
- runtime operations panel
- equity curve visualization
- runtime controls

## Infrastructure

- SQLite runtime persistence
- CI workflows
- pytest coverage
- operational audit foundation

---

# Runtime Profiles

Defined in:

```text
app/runtime/profiles.py
```

Profiles:

- `simulation`
- `binance_testnet`
- `binance_live`

Current behavior:

| Profile | Status |
|---|---|
| simulation | enabled |
| binance_testnet | guarded runtime execution |
| binance_live | intentionally blocked |

The live profile is intentionally blocked until operational reliability is significantly stronger.

---

# Runtime Architecture

Main runtime modules:

```text
app/runtime/engine.py
app/runtime/operations.py
```

The runtime is now candle-driven.

Current runtime cycle:

1. Fetch candles
2. Validate market conditions
3. Generate execution intent
4. Run safety checks
5. Reconcile exchange state
6. Execute dry-run/testnet flow
7. Persist runtime metadata
8. Update watchdog/runtime state

This is intentionally different from the original report-style simulation loop.

---

# Execution Modes

Supported execution modes:

```text
DRY_RUN
TESTNET
```

## Dry Run

Purpose:

- runtime orchestration testing;
- strategy evaluation;
- reconciliation testing;
- safety validation.

No real exchange orders are submitted.

## Testnet

Purpose:

- guarded Binance integration;
- reconciliation validation;
- restart/recovery testing;
- operational runtime validation.

Live execution remains blocked.

---

# Runtime Supervisor

The runtime supervisor manages:

- autonomous scheduling;
- long-running runtime loops;
- watchdog health;
- duplicate execution prevention;
- cooldown handling;
- exposure policies;
- reconciliation persistence;
- pending recovery visibility.

Current runtime persistence stores:

- runtime operations;
- reconciliation records;
- watchdog state;
- runtime metadata;
- pending recovery state.

---

# Dashboard

The dashboard is intentionally operationally simple.

Current visibility includes:

- runtime state;
- watchdog health;
- engine cycle state;
- runtime operations;
- equity curve;
- runtime failures;
- supervisor state.

Current controls include:

- Start
- Stop
- Pause
- Supervisor Start
- Profile selection
- Strategy selection

---

# Runtime Safety Philosophy

Tradebot should prefer:

- pausing over forcing trades;
- reducing exposure over increasing activity;
- no position over uncertain state;
- reconciliation over assumptions;
- preserving runtime state over resetting blindly.

The runtime should automatically pause when:

- reconciliation becomes unhealthy;
- watchdog health degrades;
- repeated runtime failures occur;
- stale market data appears;
- exchange state becomes uncertain.

---

# Current API Endpoints

## Runtime

```text
/api/runtime
/api/runtime/audit
/api/runtime/operations
```

## Engine

```text
/api/runtime/engine
/api/runtime/engine/cycle
/api/runtime/engine/recover
```

## Supervisor

```text
/api/runtime/supervisor
/api/runtime/supervisor/start
/api/runtime/supervisor/stop
```

---

# Important Safety Constraint

Do NOT enable live trading by:

- removing the live execution guard;
- wiring market orders directly into Start;
- bypassing reconciliation;
- trusting only in-memory runtime state;
- disabling runtime safety checks.

Operational reliability matters more than enabling live mode quickly.

---

# Local Development

## Python

```text
3.13.12
```

## Frontend

```text
Node v24.13.0
npm 11.6.2
```

## Commands

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

---

# Current Known Remaining Gaps

Still unfinished:

1. Production deployment infrastructure
2. Monitoring/alerting
3. Full frontend test coverage
4. Full supervisor API test coverage
5. Long-duration runtime soak testing
6. Production auth/security hardening
7. Production secrets management
8. Restart-safe open-order synchronization
9. Real production operational validation
10. Live execution hardening

---

# Runtime Philosophy Summary

Tradebot should behave more like:

- a cautious autonomous runtime operator;

and less like:

- an aggressive always-on gambling engine.
