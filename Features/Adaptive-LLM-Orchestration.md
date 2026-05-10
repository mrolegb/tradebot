# Adaptive LLM Orchestration — Technical Specification

## Overview

This document describes the architecture and implementation plan for integrating adaptive local LLM optimization into Tradebot.

Goal:

- Pause new entries periodically
- Allow existing trades to close naturally
- Export runtime metrics and strategy state
- Send metrics to a local LLM optimizer
- Receive optimized parameters
- Validate parameters
- Apply updated configuration safely
- Resume trading

The system must preserve the core strategy logic while allowing controlled adaptive parameter tuning.

---

# High-Level Architecture

```text
Tradebot
  ↓
n8n Orchestrator
  ↓
LLM Optimizer API
  ↓
Validation Layer
  ↓
Tradebot Config API
```

Infrastructure:

```text
┌────────────────────┐
│     Tradebot       │
│ execution engine   │
└─────────┬──────────┘
          │ REST/WebSocket
┌─────────▼──────────┐
│        n8n         │
│ workflow engine    │
└─────────┬──────────┘
          │ HTTP API
┌─────────▼──────────┐
│    Ollama / LLM    │
│ local inference    │
└─────────┬──────────┘
          │
┌─────────▼──────────┐
│ PostgreSQL / Redis │
│ memory + metrics   │
└────────────────────┘
```

---

# Core Principles

## Immutable Core Strategy

The adaptive system MUST NOT:

- change strategy philosophy
- invert long/short logic
- introduce new indicators
- modify timeframe
- rewrite execution engine logic
- bypass risk controls

The adaptive system MAY:

- tune thresholds
- tune ATR multipliers
- tune stop loss values
- tune take profit values
- tune risk percentage
- tune volatility filters
- tune confirmation thresholds

---

# Tradebot Requirements

## 1. Trading State Controller

Implement runtime state controller.

Required states:

```json
{
  "mode": "trading | closing_only | paused"
}
```

Behavior:

| Mode | New Entries | Position Management |
|---|---|---|
| trading | allowed | allowed |
| closing_only | blocked | allowed |
| paused | blocked | blocked |

---

## 2. Runtime Control API

Required endpoints:

### Pause entries

```http
POST /api/runtime/closing-only
```

### Resume trading

```http
POST /api/runtime/resume
```

### Runtime status

```http
GET /api/runtime/status
```

Example response:

```json
{
  "mode": "closing_only",
  "open_positions": 2,
  "pending_orders": 0
}
```

---

## 3. Open Position Monitoring

Required endpoint:

```http
GET /api/positions/open-count
```

Response:

```json
{
  "open_positions": 0
}
```

This endpoint is used by n8n polling loops.

---

## 4. Strategy Export API

Required endpoint:

```http
GET /api/strategy/export
```

Must include:

- current strategy parameters
- last N trades
- drawdown
- Sharpe ratio
- volatility metrics
- current market regime
- winrate
- profit factor
- exposure metrics
- current strategy version

Example:

```json
{
  "strategy_version": "v17",
  "parameters": {
    "risk_per_trade": 0.005,
    "atr_multiplier": 1.8,
    "rsi_entry": 30
  },
  "metrics": {
    "winrate": 0.54,
    "profit_factor": 1.32,
    "max_drawdown": 0.08
  }
}
```

---

## 5. Strategy Apply API

Required endpoint:

```http
POST /api/strategy/apply
```

Payload:

```json
{
  "strategy_version": "v18",
  "parameters": {
    "risk_per_trade": 0.004,
    "atr_multiplier": 1.6
  }
}
```

Requirements:

- atomic updates
- rollback support
- config validation
- audit logging
- version history

---

## 6. Strategy Versioning

Required:

- version identifier
- timestamp
- performance snapshot
- rollback capability

Suggested structure:

```text
strategies/
  v17.json
  v18.json
  v19.json
```

---

## 7. Validation Layer

All LLM outputs MUST pass validation.

Example constraints:

```python
ALLOWED_RANGES = {
    "risk_per_trade": [0.001, 0.02],
    "atr_multiplier": [0.5, 5.0],
    "rsi_entry": [10, 45],
    "rsi_exit": [55, 90]
}
```

Additional rules:

- max parameter delta per iteration
- reject invalid JSON
- reject missing fields
- reject confidence below threshold
- reject unsafe risk changes

---

## 8. Backtesting Layer

Before applying strategy changes:

1. run micro-backtest
2. compare against baseline
3. reject statistically weaker candidate

Required metrics:

- Sharpe
- drawdown
- profit factor
- expectancy
- winrate

---

## 9. Shadow Trading Mode

Optional but recommended.

Candidate parameters run in parallel without real execution.

Purpose:

- validate optimizer quality
- compare versions
- reduce deployment risk

---

# LLM Optimizer Requirements

## Local Model Runtime

Recommended:

- Ollama
- Qwen
- Llama
- DeepSeek distilled models

Preferred architecture:

```text
n8n → Optimizer API → Ollama
```

---

## Structured Output

LLM MUST return JSON only.

Example:

```json
{
  "strategy_version": "v18",
  "confidence": 0.74,
  "changes": {
    "risk_per_trade": 0.004,
    "atr_multiplier": 1.6
  },
  "reasoning": [
    "volatility increased",
    "reduce exposure",
    "tighten risk"
  ]
}
```

---

## Prompt Constraints

Optimizer prompts MUST enforce:

- no strategy rewrites
- no indicator invention
- bounded parameter changes
- stability preference
- drawdown awareness
- risk preservation

---

# Docker Architecture

## Required Containers

### tradebot

Responsibilities:

- execution engine
- APIs
- metrics export
- strategy management

Port:

```text
8000
```

---

### n8n

Responsibilities:

- orchestration
- scheduling
- polling
- workflow automation

Port:

```text
5678
```

---

### ollama

Responsibilities:

- local inference
- structured output generation

Port:

```text
11434
```

---

### postgres

Responsibilities:

- strategy history
- metrics history
- optimization snapshots
- trade archive

---

### redis

Responsibilities:

- queues
- runtime state
- caching
- workflow synchronization

---

# Docker Compose Example

```yaml
services:

  tradebot:
    build: ./tradebot
    ports:
      - "8000:8000"

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

  postgres:
    image: postgres:16

  redis:
    image: redis:7

volumes:
  ollama_data:
```

---

# Internal Docker Network

All services MUST communicate via Docker network.

Examples:

```text
http://tradebot:8000
http://n8n:5678
http://ollama:11434
```

---

# GPU Support

Recommended for local inference.

Example:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          capabilities: [gpu]
```

---

# n8n Orchestration Workflow

## Hourly Adaptive Loop

```text
Cron Trigger
  ↓
Pause Entries
  ↓
Poll Open Positions
  ↓
Wait Until Flat
  ↓
Export Metrics
  ↓
Call Optimizer
  ↓
Validate Response
  ↓
Run Backtest
  ↓
Apply Parameters
  ↓
Resume Trading
```

---

# n8n Workflow Steps

## Step 1 — Cron Trigger

Run every hour.

---

## Step 2 — Pause New Entries

Request:

```http
POST /api/runtime/closing-only
```

---

## Step 3 — Poll Open Positions

Loop:

```http
GET /api/positions/open-count
```

Continue until:

```json
{
  "open_positions": 0
}
```

---

## Step 4 — Export Metrics

Request:

```http
GET /api/strategy/export
```

---

## Step 5 — Call LLM Optimizer

Request:

```http
POST http://ollama:11434/api/generate
```

Prompt includes:

- current metrics
- strategy parameters
- market regime
- optimization constraints
- allowed parameter ranges

---

## Step 6 — Validate Response

Validation checks:

- JSON validity
- schema validation
- parameter bounds
- confidence threshold
- risk constraints

---

## Step 7 — Run Backtest

Execute:

- recent rolling window
- candidate vs baseline comparison

---

## Step 8 — Apply Strategy

Request:

```http
POST /api/strategy/apply
```

---

## Step 9 — Resume Trading

Request:

```http
POST /api/runtime/resume
```

---

# Future Extensions

## Multi-Model Voting

Example:

- Qwen optimizer
- Llama optimizer
- Bayesian optimizer
- Rule-based optimizer

Final parameters selected via voting.

---

## Regime Memory

Store:

- market regimes
- historical performance
- parameter effectiveness
- optimization history

Purpose:

- avoid oscillation
- improve adaptation quality
- improve long-term stability

---

## Strategy Sandbox

Support isolated strategy runners:

```text
strategy-v17
strategy-v18
strategy-experimental
```

Purpose:

- paper trading
- parallel experiments
- safe rollout

---

# Security Requirements

Required:

- API authentication
- internal-only optimizer access
- request signing
- audit logging
- rollback support
- rate limiting

---

# Success Criteria

The implementation is considered successful when:

- adaptive loop executes automatically
- no unsafe parameter changes occur
- strategy logic remains stable
- optimization is measurable
- rollback is possible
- infrastructure is reproducible
- full system runs locally in Docker
