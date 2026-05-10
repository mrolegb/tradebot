# Adaptive LLM Orchestration — Technical Specification

## Purpose

This document describes the full target architecture for adding a local adaptive LLM feedback loop to Tradebot.

The goal is to build a self-hosted, Dockerized, observable and rollback-safe trading system where:

1. Tradebot runs the actual trading strategy and exchange execution.
2. n8n orchestrates the hourly optimization workflow.
3. Existing positions are allowed to close naturally before optimization.
4. A local LLM proposes bounded parameter changes only.
5. A validation and backtesting layer decides whether the proposal can be applied.
6. Tradebot applies a new strategy parameter version and resumes trading.

The LLM must never be allowed to freely rewrite the strategy or place trades directly.

---

# Target Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         Docker Host / VPS / Local Box                 │
│                                                                      │
│  ┌────────────────────┐        ┌────────────────────┐                │
│  │     Tradebot       │◄──────►│        n8n         │                │
│  │                    │  HTTP  │                    │                │
│  │ execution engine   │        │ workflow engine    │                │
│  │ strategy runtime   │        │ scheduler          │                │
│  │ runtime API        │        │ retry logic        │                │
│  └─────────┬──────────┘        └─────────┬──────────┘                │
│            │                             │                           │
│            │                             │ HTTP                      │
│            │                             ▼                           │
│            │                   ┌────────────────────┐                │
│            │                   │  Optimizer API     │                │
│            │                   │                    │                │
│            │                   │ prompt builder     │                │
│            │                   │ schema validator   │                │
│            │                   │ safety gates       │                │
│            │                   └─────────┬──────────┘                │
│            │                             │                           │
│            │                             │ HTTP                      │
│            │                             ▼                           │
│            │                   ┌────────────────────┐                │
│            │                   │ Ollama / Local LLM │                │
│            │                   │                    │                │
│            │                   │ Qwen / Llama /     │                │
│            │                   │ DeepSeek distilled │                │
│            │                   └────────────────────┘                │
│            │                                                         │
│            ▼                                                         │
│  ┌────────────────────┐        ┌────────────────────┐                │
│  │    PostgreSQL      │        │       Redis        │                │
│  │                    │        │                    │                │
│  │ trades             │        │ runtime state      │                │
│  │ metrics            │        │ locks              │                │
│  │ strategy versions  │        │ queues             │                │
│  │ optimization logs  │        │ short-lived cache  │                │
│  └────────────────────┘        └────────────────────┘                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

# Architectural Principles

## 1. Tradebot Owns Trading

Tradebot remains the only service that:

- opens positions
- closes positions
- manages live orders
- talks to exchanges
- enforces risk limits
- applies strategy configuration

n8n and the LLM do not trade directly.

---

## 2. LLM Is a Parameter Advisor, Not a Trader

The LLM is used only as a constrained optimizer.

It MAY suggest changes to mutable strategy parameters:

- risk per trade
- ATR multipliers
- stop loss percentages
- take profit percentages
- RSI thresholds
- volatility filters
- confirmation thresholds
- maximum concurrent positions

It MUST NOT:

- rewrite the strategy
- add new indicators
- remove existing risk checks
- invert long/short logic
- change exchange execution logic
- place orders
- bypass validation
- directly write config files

---

## 3. Immutable Core, Mutable Parameters

The strategy should be split into two layers:

```text
core_strategy_logic = immutable
adaptive_parameters = mutable
```

Example:

```json
{
  "strategy_id": "mean_reversion_v1",
  "core_logic_hash": "sha256:...",
  "mutable_parameters": {
    "risk_per_trade": 0.005,
    "atr_multiplier": 1.8,
    "rsi_entry": 30,
    "rsi_exit": 67,
    "max_positions": 2
  }
}
```

The adaptive loop can only modify `mutable_parameters`.

---

## 4. Safety Before Adaptation

Every optimization proposal must pass:

1. JSON schema validation
2. parameter range validation
3. max delta validation
4. risk validation
5. optional micro-backtest
6. optional shadow-mode validation
7. audit logging
8. rollback readiness

---

# Main Feedback Loop

The system runs a scheduled optimization cycle, usually every hour.

```text
Cron / Schedule
  ↓
n8n starts adaptive cycle
  ↓
Tradebot enters closing_only mode
  ↓
No new trades are opened
  ↓
Existing positions continue to be managed
  ↓
n8n polls until open_positions == 0
  ↓
Tradebot exports strategy snapshot + performance metrics
  ↓
Optimizer API builds constrained prompt
  ↓
Local LLM returns JSON proposal
  ↓
Validator checks proposal
  ↓
Backtest compares candidate vs baseline
  ↓
If accepted: apply new parameter version
  ↓
If rejected: keep current version
  ↓
Tradebot resumes trading
```

---

# Service Responsibilities

## Tradebot

Primary responsibility: live trading execution and strategy runtime.

Required modules:

- exchange adapters
- strategy runtime
- risk manager
- order manager
- position manager
- metrics exporter
- strategy config manager
- runtime state controller
- REST API

Tradebot exposes the control surface used by n8n.

---

## n8n

Primary responsibility: workflow orchestration.

n8n handles:

- hourly schedule
- API calls to Tradebot
- polling open positions
- branching logic
- retries
- failure notifications
- optimizer invocation
- workflow execution history

n8n should not contain trading logic.

---

## Optimizer API

Primary responsibility: safe interface between n8n and the local LLM.

Responsibilities:

- receive optimization payload from n8n
- build prompt from current metrics and constraints
- call Ollama or another local inference runtime
- request strict JSON output
- validate response schema
- normalize proposal
- reject unsafe or malformed responses
- return candidate parameters to n8n or Tradebot

This service may be implemented as a small FastAPI service.

---

## Ollama / Local LLM

Primary responsibility: generate bounded parameter suggestions.

Recommended local model families:

- Qwen
- Llama
- DeepSeek distilled models
- Mistral

The model should be treated as non-deterministic and untrusted.

All outputs must be validated.

---

## PostgreSQL

Primary responsibility: durable system memory.

Stores:

- trades
- fills
- candles if needed
- strategy versions
- strategy performance snapshots
- optimization requests
- optimization proposals
- accepted/rejected decisions
- backtest results
- audit events

---

## Redis

Primary responsibility: runtime coordination.

Stores:

- optimization locks
- current runtime mode cache
- temporary workflow state
- queues
- short-lived orchestration flags

---

# Tradebot Runtime Modes

Tradebot must support explicit runtime modes.

```json
{
  "mode": "trading | closing_only | paused"
}
```

| Mode | New Entries | Existing Position Management | Order Management |
|---|---:|---:|---:|
| `trading` | yes | yes | yes |
| `closing_only` | no | yes | yes |
| `paused` | no | no / emergency only | cancel or hold by config |

## Mode Behavior

### trading

Normal operation.

### closing_only

Used during adaptive optimization.

Rules:

- block new entries
- continue managing open positions
- continue stop loss / take profit / trailing logic
- allow risk-reducing exits
- allow emergency exits
- do not apply new parameters until flat

### paused

Manual or emergency mode.

Rules:

- no entries
- no non-emergency actions
- used for maintenance or failure containment

---

# Required Tradebot API

## Runtime Control

### Enter closing-only mode

```http
POST /api/runtime/closing-only
```

Response:

```json
{
  "ok": true,
  "mode": "closing_only"
}
```

### Resume trading

```http
POST /api/runtime/resume
```

Response:

```json
{
  "ok": true,
  "mode": "trading",
  "strategy_version": "v18"
}
```

### Pause runtime

```http
POST /api/runtime/pause
```

### Runtime status

```http
GET /api/runtime/status
```

Response:

```json
{
  "mode": "closing_only",
  "strategy_version": "v17",
  "open_positions": 2,
  "pending_orders": 0,
  "last_heartbeat_at": "2026-05-10T17:00:00Z"
}
```

---

## Position Monitoring

```http
GET /api/positions/open-count
```

Response:

```json
{
  "open_positions": 0
}
```

---

## Strategy Export

```http
GET /api/strategy/export
```

Response:

```json
{
  "strategy_id": "mean_reversion_v1",
  "strategy_version": "v17",
  "core_logic_hash": "sha256:...",
  "parameters": {
    "risk_per_trade": 0.005,
    "atr_multiplier": 1.8,
    "rsi_entry": 30,
    "rsi_exit": 67,
    "max_positions": 2
  },
  "allowed_ranges": {
    "risk_per_trade": [0.001, 0.02],
    "atr_multiplier": [0.5, 5.0],
    "rsi_entry": [10, 45],
    "rsi_exit": [55, 90],
    "max_positions": [1, 5]
  },
  "max_delta_pct": 15,
  "metrics": {
    "window": "last_100_trades",
    "winrate": 0.54,
    "profit_factor": 1.32,
    "expectancy": 0.004,
    "max_drawdown": 0.08,
    "sharpe": 1.12,
    "net_pnl": 0.18
  },
  "market_regime": {
    "volatility": "medium",
    "trend_strength": "low",
    "chop": "high",
    "liquidity": "normal"
  }
}
```

---

## Strategy Apply

```http
POST /api/strategy/apply
```

Request:

```json
{
  "base_strategy_version": "v17",
  "new_strategy_version": "v18",
  "parameters": {
    "risk_per_trade": 0.0045,
    "atr_multiplier": 1.7,
    "rsi_entry": 29,
    "rsi_exit": 68,
    "max_positions": 2
  },
  "source": "llm_optimizer",
  "reason": "Reduce risk after drawdown and tighten entry sensitivity in choppy regime."
}
```

Requirements:

- reject if current version is not `base_strategy_version`
- reject while positions are open unless explicitly allowed
- validate before write
- write atomically
- record audit event
- keep rollback pointer

---

## Strategy Rollback

```http
POST /api/strategy/rollback
```

Request:

```json
{
  "target_strategy_version": "v17",
  "reason": "Candidate underperformed in shadow mode"
}
```

---

# Optimizer API Contract

## Optimization Request

```http
POST /api/optimizer/propose
```

Request body:

```json
{
  "strategy_snapshot": {
    "strategy_id": "mean_reversion_v1",
    "strategy_version": "v17",
    "core_logic_hash": "sha256:...",
    "parameters": {},
    "allowed_ranges": {},
    "max_delta_pct": 15,
    "metrics": {},
    "market_regime": {}
  },
  "constraints": {
    "mode": "parameter_tuning_only",
    "prefer_stability": true,
    "do_not_change_core_logic": true,
    "min_confidence": 0.65
  }
}
```

## Optimization Response

```json
{
  "accepted_by_optimizer": true,
  "candidate": {
    "base_strategy_version": "v17",
    "proposed_strategy_version": "v18-candidate",
    "confidence": 0.74,
    "parameters": {
      "risk_per_trade": 0.0045,
      "atr_multiplier": 1.7,
      "rsi_entry": 29,
      "rsi_exit": 68,
      "max_positions": 2
    },
    "reasoning": [
      "Recent drawdown increased",
      "Market regime is choppy",
      "Risk should be slightly reduced",
      "Entry should be tightened without changing strategy philosophy"
    ]
  },
  "validator_notes": []
}
```

---

# Prompt Architecture

The prompt must make the model act as a constrained parameter tuner.

## System Prompt Shape

```text
You are a constrained trading strategy parameter optimizer.

You do not trade.
You do not rewrite strategies.
You do not invent indicators.
You only tune explicitly allowed mutable parameters.

Preserve the strategy philosophy.
Prefer stability over aggressiveness.
Reduce risk after drawdown.
Avoid large parameter oscillations.
Return JSON only.
```

## Optimization Instructions

```text
Allowed actions:
- adjust only parameters listed in allowed_ranges
- keep every value inside bounds
- keep each change within max_delta_pct
- explain each change briefly

Forbidden actions:
- changing core logic
- changing timeframe
- changing exchange execution
- adding indicators
- deleting risk controls
- increasing risk after poor performance without strong justification
```

---

# LLM Output Schema

The LLM output must match a strict schema.

```json
{
  "type": "object",
  "required": ["confidence", "parameters", "reasoning"],
  "properties": {
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "parameters": {
      "type": "object"
    },
    "reasoning": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  }
}
```

---

# Validation Layer

Validation must be deterministic and code-based.

The LLM output is never trusted by default.

## Validation Checks

Required checks:

- valid JSON
- valid schema
- all required parameters present
- no unknown parameters
- all parameters inside allowed ranges
- max delta per parameter respected
- confidence above threshold
- no risk increase during drawdown unless explicitly allowed
- no version mismatch
- no application while positions are open

Example ranges:

```python
ALLOWED_RANGES = {
    "risk_per_trade": [0.001, 0.02],
    "atr_multiplier": [0.5, 5.0],
    "rsi_entry": [10, 45],
    "rsi_exit": [55, 90],
    "max_positions": [1, 5],
}
```

Example delta rule:

```python
MAX_DELTA_PCT = 15
```

---

# Backtesting Gate

Before applying candidate parameters, run a lightweight backtest.

## Candidate vs Baseline

Compare:

- current active parameters
- proposed candidate parameters

On the same recent market window.

Required metrics:

- net PnL
- max drawdown
- Sharpe
- profit factor
- expectancy
- number of trades
- winrate

## Acceptance Rules

Candidate can be accepted if:

- drawdown does not materially increase
- risk-adjusted return is not worse
- profit factor is acceptable
- trade count is not too small
- no safety constraint is violated

If results are inconclusive, keep current parameters.

---

# Shadow Trading Mode

Shadow mode is recommended before fully enabling automatic application.

In shadow mode:

- current live strategy continues trading
- candidate strategy runs virtually
- candidate does not place orders
- performance is recorded
- candidate can be promoted later

Useful for:

- testing optimizer quality
- comparing model suggestions
- preventing bad live changes

---

# Strategy Versioning

Every applied parameter set must create a new version.

Suggested storage:

```text
strategies/
  mean_reversion_v1/
    v17.json
    v18.json
    v19.json
```

Each version should include:

```json
{
  "strategy_id": "mean_reversion_v1",
  "version": "v18",
  "base_version": "v17",
  "created_at": "2026-05-10T17:00:00Z",
  "source": "llm_optimizer",
  "core_logic_hash": "sha256:...",
  "parameters": {},
  "reasoning": [],
  "validation_result": {},
  "backtest_result": {}
}
```

---

# Memory Layer

The system should store optimization history to avoid parameter oscillation.

## Required Memory

Store:

- last N parameter versions
- performance per version
- market regime per version
- LLM reasoning
- accepted/rejected proposals
- rollback events

## Purpose

The memory layer helps answer:

- which parameters worked in high volatility
- which parameters failed in choppy markets
- whether the optimizer is oscillating
- whether a model consistently overfits

---

# Database Model Proposal

## strategy_versions

```text
id
strategy_id
version
base_version
core_logic_hash
parameters_json
source
created_at
is_active
```

## optimization_runs

```text
id
started_at
finished_at
base_strategy_version
status
market_regime_json
input_metrics_json
llm_model
prompt_hash
raw_llm_output
normalized_candidate_json
validation_result_json
backtest_result_json
final_decision
```

## trade_metrics_snapshots

```text
id
created_at
strategy_version
window
metrics_json
```

---

# n8n Orchestration

n8n is the workflow brain.

It should coordinate services but not own trading logic.

## Hourly Workflow

```text
Cron Trigger
  ↓
Acquire optimization lock
  ↓
POST tradebot /api/runtime/closing-only
  ↓
Poll /api/positions/open-count
  ↓
IF open_positions > 0: wait and retry
  ↓
GET /api/strategy/export
  ↓
POST optimizer /api/optimizer/propose
  ↓
IF optimizer rejected: resume trading
  ↓
POST tradebot /api/backtest/run or internal backtest service
  ↓
IF backtest failed: resume trading
  ↓
POST tradebot /api/strategy/apply
  ↓
POST tradebot /api/runtime/resume
  ↓
Release optimization lock
  ↓
Notify result
```

---

# n8n Failure Handling

Required failure behavior:

- if optimizer fails, keep current strategy and resume trading
- if validation fails, keep current strategy and resume trading
- if backtest fails, keep current strategy and resume trading
- if apply fails, keep current strategy and alert
- if resume fails, alert immediately
- always release optimization lock in final step

---

# Docker Architecture

The project should run as a multi-container stack.

## Containers

### tradebot

Responsibilities:

- strategy execution
- exchange integration
- REST API
- metrics export
- strategy apply/rollback

### n8n

Responsibilities:

- orchestration
- cron
- retries
- workflow history

### optimizer-api

Responsibilities:

- prompt building
- LLM calls
- schema validation
- proposal normalization

### ollama

Responsibilities:

- local LLM inference
- model storage

### postgres

Responsibilities:

- durable storage

### redis

Responsibilities:

- locks
- queues
- transient runtime coordination

---

# Docker Compose Target

```yaml
services:

  tradebot:
    build:
      context: ./tradebot
    container_name: tradebot
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    networks:
      - tradebot_net

  n8n:
    image: n8nio/n8n:latest
    container_name: tradebot_n8n
    ports:
      - "5678:5678"
    env_file:
      - .env
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - tradebot
      - optimizer-api
    networks:
      - tradebot_net

  optimizer-api:
    build:
      context: ./optimizer-api
    container_name: tradebot_optimizer
    ports:
      - "8010:8010"
    env_file:
      - .env
    depends_on:
      - ollama
      - postgres
    networks:
      - tradebot_net

  ollama:
    image: ollama/ollama:latest
    container_name: tradebot_ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - tradebot_net

  postgres:
    image: postgres:16
    container_name: tradebot_postgres
    env_file:
      - .env
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - tradebot_net

  redis:
    image: redis:7
    container_name: tradebot_redis
    volumes:
      - redis_data:/data
    networks:
      - tradebot_net

networks:
  tradebot_net:
    driver: bridge

volumes:
  n8n_data:
  ollama_data:
  postgres_data:
  redis_data:
```

---

# Internal Service URLs

Inside Docker network:

```text
Tradebot:      http://tradebot:8000
n8n:           http://n8n:5678
Optimizer API: http://optimizer-api:8010
Ollama:        http://ollama:11434
PostgreSQL:    postgres:5432
Redis:         redis:6379
```

Do not use `localhost` between containers.

---

# GPU Support

For NVIDIA GPU inference, Ollama container should support GPU access.

Example:

```yaml
ollama:
  image: ollama/ollama:latest
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

Exact configuration may differ between local Docker Compose and server deployment.

---

# Environment Variables

Suggested `.env` values:

```text
TRADEBOT_API_PORT=8000
OPTIMIZER_API_PORT=8010
N8N_PORT=5678

POSTGRES_DB=tradebot
POSTGRES_USER=tradebot
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql://tradebot:change_me@postgres:5432/tradebot

REDIS_URL=redis://redis:6379/0

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen:latest

OPTIMIZATION_INTERVAL_MINUTES=60
OPTIMIZATION_MIN_CONFIDENCE=0.65
OPTIMIZATION_MAX_DELTA_PCT=15

TRADEBOT_INTERNAL_API_KEY=change_me
OPTIMIZER_INTERNAL_API_KEY=change_me
```

---

# MVP Implementation Plan

## Phase 1 — Tradebot Runtime Control

Implement:

- runtime modes
- closing-only mode
- open position count endpoint
- strategy export endpoint
- strategy apply endpoint

Deliverable:

- n8n can pause entries, wait until flat and resume trading.

---

## Phase 2 — Dockerization

Implement:

- Tradebot Dockerfile
- Docker Compose stack
- Postgres container
- Redis container
- n8n container
- Ollama container

Deliverable:

- full local stack starts with one command.

---

## Phase 3 — Optimizer API

Implement:

- FastAPI optimizer service
- Ollama integration
- prompt builder
- schema validation
- normalized JSON response

Deliverable:

- n8n can request a candidate parameter set.

---

## Phase 4 — Validation and Backtesting

Implement:

- deterministic validation
- parameter bounds
- delta checks
- micro-backtest
- candidate vs baseline comparison

Deliverable:

- unsafe or weak candidates are rejected before live application.

---

## Phase 5 — n8n Workflow

Implement:

- hourly workflow
- failure branches
- retry logic
- notifications
- execution logging

Deliverable:

- full adaptive loop runs automatically.

---

## Phase 6 — Memory and Shadow Mode

Implement:

- optimization history
- strategy performance memory
- shadow strategy runner
- candidate promotion logic

Deliverable:

- adaptive loop becomes measurable and safer over time.

---

# Acceptance Criteria

The feature is complete when:

- the full stack runs locally through Docker Compose
- Tradebot exposes required runtime and strategy APIs
- n8n runs the adaptive workflow on schedule
- Tradebot blocks new entries during optimization
- existing trades are allowed to finish naturally
- optimization starts only when open positions are zero
- LLM output is strict JSON
- LLM can only tune allowed mutable parameters
- validation rejects unsafe proposals
- backtest gate compares candidate vs baseline
- accepted parameters are versioned
- rejected proposals are logged
- rollback is available
- Tradebot resumes trading after the cycle
- failures do not leave the bot stuck in closing-only mode without alerting

---

# Future Extensions

## Multi-Model Voting

Use multiple optimizers:

- Qwen optimizer
- Llama optimizer
- rules-based optimizer
- Bayesian optimizer

Select candidate via voting or scoring.

---

## Regime-Aware Memory

Use stored regime history to answer:

- what worked in high volatility
- what worked in sideways markets
- what failed after drawdowns

---

## Strategy Sandbox Containers

Run isolated strategy containers:

```text
strategy-runner-current
strategy-runner-candidate
strategy-runner-experimental
```

This enables parallel shadow testing.

---

## Remote GPU Node

If local CPU inference is too slow, move only Ollama / inference to a GPU host while keeping Tradebot and n8n on the main server.

---

# Security Requirements

Required:

- internal API authentication
- Docker network isolation
- no public Ollama exposure in production
- no public optimizer exposure in production
- signed or token-protected internal requests
- audit logs for every applied parameter change
- rollback for every applied strategy version
- rate limits on control endpoints
- emergency pause endpoint

---

# Operational Notes

## Default Safe Behavior

When uncertain, the system should do nothing.

Examples:

- invalid LLM response → reject
- low confidence → reject
- weak backtest → reject
- open positions remain → keep closing-only until timeout or manual intervention
- optimizer unavailable → resume current strategy

---

## Observability

Recommended logs and dashboards:

- current runtime mode
- active strategy version
- open positions
- last optimization run
- last accepted proposal
- last rejected proposal
- model used
- validation failures
- backtest comparison
- rollback events

---

# Final Target State

The final system should be a self-hosted adaptive trading platform:

```text
Dockerized Tradebot
  + n8n workflow orchestration
  + local LLM optimizer
  + deterministic safety validation
  + backtesting gate
  + strategy versioning
  + rollback
  + durable optimization memory
```

The LLM improves the strategy only by carefully tuning bounded parameters, while Tradebot remains the sole owner of live trading execution and risk control.
