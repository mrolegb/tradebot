# Telegram Bot Setup

## Purpose

Tradebot can periodically send runtime heartbeat updates to Telegram.

The heartbeat is intentionally simple:

- one background asyncio task;
- one Telegram message;
- periodically updated status;
- lightweight runtime visibility from mobile.

This is NOT intended to become a large notification infrastructure.

---

# 1. Create Telegram Bot

Open Telegram.

Find:

```text
BotFather
```

Run:

```text
/newbot
```

Telegram will return:

```text
BOT_TOKEN
```

Example:

```text
123456:ABCDEF...
```

Save this token securely.

Do NOT commit it into git.

---

# 2. Get Telegram Chat ID

Send any message to your newly created bot.

Open:

```text
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```

Replace:

```text
<BOT_TOKEN>
```

with your real token.

Inside the response find:

```json
"chat": {
  "id": 123456789
}
```

That value is your:

```text
TELEGRAM_CHAT_ID
```

---

# 3. Configure Environment Variables

Add:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Optional:

```text
TELEGRAM_HEARTBEAT_INTERVAL_SECONDS=900
```

Recommended interval:

```text
900-1800 seconds
```

(15-30 minutes)

---

# 4. Runtime Behavior

When the runtime supervisor starts:

- Telegram reporter task starts automatically;
- one Telegram status message is created;
- the same message is updated periodically using editMessageText.

This avoids Telegram spam.

---

# 5. Recommended Runtime Information

The heartbeat should contain:

- runtime state;
- execution mode;
- symbol;
- watchdog health;
- last runtime error;
- reconciliation health;
- active positions;
- pending records;
- last intent;
- last execution result;
- last cycle timestamp.

---

# 6. Failure Behavior

Telegram failures must NEVER:

- stop the runtime;
- interrupt the supervisor;
- break reconciliation;
- block runtime execution.

Telegram errors should:

- log;
- retry naturally on the next interval.

---

# 7. Important Constraint

This feature must NOT:

- enable Binance live trading;
- bypass reconciliation;
- modify execution safety;
- interfere with runtime execution.

The feature is operational visibility only.
