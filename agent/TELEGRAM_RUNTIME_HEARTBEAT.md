# Telegram Runtime Heartbeat

## Goal

Provide lightweight operational visibility for the runtime using Telegram.

This feature is intentionally NOT a full notification/event infrastructure.

The purpose is:

- periodic runtime heartbeat visibility;
- lightweight runtime monitoring;
- quick operational inspection from mobile;
- low-noise runtime status reporting.

The intended workflow is:

1. Runtime starts.
2. Background reporter task starts.
3. Reporter periodically updates a Telegram message.
4. Operator can quickly inspect runtime health from Telegram.

---

# Design Constraints

The implementation should remain intentionally simple.

Avoid:

- event buses;
- Redis;
- Kafka;
- Celery;
- notification microservices;
- synchronous runtime-blocking notification logic.

Tradebot is currently:

- low-frequency;
- single-runtime;
- conservative;
- operationally simple.

The Telegram heartbeat should match that philosophy.

---

# Recommended Architecture

```text
Runtime Supervisor
    -> background asyncio task
        -> TelegramReporter
            -> Telegram Bot API
```

The reporter should:

- run independently from the trading cycle;
- never block runtime execution;
- tolerate Telegram/API failures;
- continue operating even if Telegram becomes unavailable.

---

# Telegram Requirements

A Telegram bot is required.

Configuration should use environment variables:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Do NOT hardcode credentials.

---

# Heartbeat Behavior

Recommended interval:

```text
15-30 minutes
```

The heartbeat should preferably:

- create one message initially;
- continuously update that message using editMessageText.

This avoids Telegram spam and creates a lightweight operational dashboard.

---

# Suggested Runtime Status Fields

Recommended heartbeat contents:

- runtime state;
- runtime profile;
- watchdog health;
- runtime uptime;
- equity;
- available balance;
- open position count;
- exposure percentage;
- realized PnL;
- unrealized PnL;
- last runtime cycle timestamp;
- reconciliation status.

Example:

```text
🤖 TradeBot

Profile: testnet
Runtime: RUNNING
Watchdog: HEALTHY

Equity: $1044.22
Available: $1001.14
PnL today: +14.11

Open positions: 2
Exposure: 8%

Last cycle:
2026-05-10 18:55 UTC
```

---

# Alert Philosophy

The heartbeat should remain low-noise.

Avoid sending separate messages for normal runtime operation.

Separate alert messages should only be used for critical situations:

- runtime paused;
- watchdog unhealthy;
- reconciliation failed;
- repeated runtime failures;
- exchange unavailable.

---

# Failure Handling

Telegram failures must NOT:

- stop the runtime;
- pause execution;
- interrupt reconciliation;
- block candle processing.

Reporter failures should:

- be logged;
- retry naturally on the next interval.

---

# Future Direction

Possible future improvements:

- Slack transport;
- Discord transport;
- multi-recipient support;
- structured alert severity;
- alert cooldown/rate limiting;
- runtime charts/images.

These are intentionally out of scope for the initial implementation.
