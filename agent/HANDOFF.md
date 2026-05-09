# Tradebot Agent Handoff

## Product Goal

Tradebot is evolving from a report-style simulator into a conservative autonomous trading runtime.

The intended user experience is intentionally simple:

1. User deposits a controlled amount of money.
2. User starts the runtime.
3. Bot trades conservatively.
4. Bot pauses itself automatically if conditions become unsafe.
5. User checks results later.

The project is intentionally NOT trying to become:

- a high-frequency system;
- an aggressive leverage bot;
- a martingale engine;
- a complicated trader terminal;
- a "trade every minute" machine.

The core philosophy is:

- safety first;
- runtime reliability first;
- low operational stress;
- transparency over aggressiveness.

## Current Architecture

The repository now contains:

### Backend

- FastAPI runtime API
- runtime supervisor
- candle runtime engine
- reconciliation layer
- dry-run execution layer
- guarded Binance testnet execution foundation
- runtime persistence
- audit logging
- watchdog/failsafe foundation
- runtime recovery foundation
- runtime operations storage
- autonomous scheduler foundation

### Frontend

- React/Vite dashboard
- runtime health visibility
- supervisor visibility
- engine cycle visibility
- runtime operations panel
- equity curve charting
- runtime control panel

### Infrastructure

- SQLite runtime storage
- CI workflow
- pytest coverage
- runtime persistence layer
- operational audit trail foundation

## Current Runtime Profiles

Defined in:

```text
app/runtime/profiles.py
```

Profiles:

- `simulation`
- `binance_testnet`
- `binance_live`

Current behavior:

- `simulation` works.
- `binance_testnet` supports guarded runtime engine execution.
- `binance_live` is intentionally blocked.

The live block is intentional.

Do NOT casually remove it.

## Runtime Engine

Main runtime module:

```text
app/runtime/engine.py
```

Current engine architecture:

1. Fetch candles
2. Validate runtime conditions
3. Generate execution intent
4. Run safety evaluation
5. Reconcile exchange state
6. Execute dry-run/testnet flow
7. Persist runtime metadata
8. Update watchdog/runtime state

The runtime is now candle-driven instead of purely report-driven.

## Execution Modes

Supported modes:

```text
DRY_RUN
TESTNET
```

### Dry Run

Purpose:

- autonomous runtime validation;
- strategy evaluation;
- safety validation;
- reconciliation validation;
- runtime orchestration testing.

No real exchange orders are submitted.

### Testnet

Purpose:

- guarded exchange integration;
- runtime operational testing;
- reconciliation testing;
- restart/recovery validation.

Live execution still remains blocked.

## Runtime Supervisor

Main module:

```text
app/runtime/operations.py
```

Current capabilities:

- autonomous runtime scheduling;
- long-running loop orchestration;
- watchdog monitoring;
- duplicate execution prevention;
- exposure policy validation;
- cooldown handling;
- runtime persistence;
- pending recovery inspection;
- reconciliation persistence.

## Runtime Safety Philosophy

Tradebot should prefer:

- pausing over forcing trades;
- reducing exposure over increasing activity;
- no position over uncertain state;
- reconciliation over assumptions;
- preserving state over resetting blindly.

The runtime should automatically pause when:

- reconciliation becomes unhealthy;
- exchange state becomes uncertain;
- repeated runtime failures occur;
- watchdog health degrades;
- stale market data appears;
- runtime recovery cannot guarantee consistency.

## Runtime Operations Storage

Current SQLite runtime storage tracks:

- runtime records;
- reconciliation records;
- pending recovery state;
- runtime actions;
- watchdog state;
- runtime metadata.

This exists to support:

- restart recovery;
- auditability;
- operational debugging;
- reconciliation consistency.

## Current Runtime API

Important endpoints now include:

### Runtime

```text
/api/runtime
/api/runtime/audit
/api/runtime/operations
```

### Engine

```text
/api/runtime/engine
/api/runtime/engine/cycle
/api/runtime/engine/recover
```

### Supervisor

```text
/api/runtime/supervisor
/api/runtime/supervisor/start
/api/runtime/supervisor/stop
```

## Dashboard Direction

The dashboard is intentionally simple.

Desired operational visibility:

- runtime state;
- watchdog health;
- pause reasons;
- execution status;
- reconciliation state;
- runtime operations;
- equity curve;
- recent failures.

Avoid turning the project into a cluttered exchange terminal.

## Current Known Remaining Gaps

Still unfinished:

1. Production deployment infrastructure
2. Structured monitoring/alerting
3. Full frontend test coverage
4. Full supervisor API test coverage
5. Long-duration soak testing
6. Production authentication/authorization
7. Production secrets management
8. Live execution hardening
9. Restart-safe open-order synchronization
10. Real production operational validation

## Important Live Trading Constraint

Do NOT enable live trading by:

- removing the live execution guard;
- wiring market orders directly into Start;
- trusting only in-memory runtime state;
- skipping reconciliation;
- bypassing runtime safety checks.

Operational reliability matters more than enabling live mode quickly.

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

- a cautious autonomous runtime operator;

and less like:

- an aggressive always-on gambling engine.
