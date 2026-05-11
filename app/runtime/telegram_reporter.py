from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    interval_seconds: int = 900

    @classmethod
    def from_env(cls) -> "TelegramConfig | None":
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        interval_raw = os.getenv("TELEGRAM_HEARTBEAT_INTERVAL_SECONDS", "900")

        if not bot_token or not chat_id:
            return None

        try:
            interval_seconds = max(60, int(interval_raw))
        except ValueError:
            interval_seconds = 900

        return cls(
            bot_token=bot_token,
            chat_id=chat_id,
            interval_seconds=interval_seconds,
        )


class TelegramRuntimeReporter:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self.message_id: int | None = None

    async def run_forever(self, supervisor) -> None:
        while True:
            try:
                await self.publish_snapshot(supervisor.snapshot())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"telegram heartbeat failed: {exc}")

            await asyncio.sleep(self.config.interval_seconds)

    async def publish_snapshot(self, snapshot: dict[str, Any]) -> None:
        text = self.format_snapshot(snapshot)

        if self.message_id is None:
            self.message_id = await self._send_message(text)
            return

        await self._edit_message(text)

    def format_snapshot(self, snapshot: dict[str, Any]) -> str:
        state = snapshot.get("state", "unknown")
        watchdog = snapshot.get("watchdog") or {}
        last_cycle = snapshot.get("last_cycle") or {}
        reconciliation = last_cycle.get("reconciliation") or {}
        intent = last_cycle.get("intent") or {}
        execution = last_cycle.get("execution") or {}
        safety = last_cycle.get("safety") or {}
        pending_recovery = snapshot.get("pending_recovery") or {}
        pending_records = pending_recovery.get("pending_records") or []

        symbol = last_cycle.get("symbol", "n/a")
        mode = last_cycle.get("mode", "n/a")
        finished_at = last_cycle.get("finished_at", "n/a")
        reconciliation_healthy = reconciliation.get("healthy", "n/a")
        watchdog_errors = watchdog.get("consecutive_errors", 0)
        last_error = watchdog.get("last_error") or "none"
        open_order_symbols = reconciliation.get("open_order_symbols") or []
        active_positions = reconciliation.get("active_exchange_positions") or []

        return (
            "🤖 TradeBot Futures\n\n"
            f"State: {state}\n"
            f"Mode: {mode}\n"
            f"Symbol: {symbol}\n"
            f"Watchdog errors: {watchdog_errors}\n"
            f"Last error: {last_error}\n\n"
            f"Reconciliation healthy: {reconciliation_healthy}\n"
            f"Active exchange positions: {len(active_positions)}\n"
            f"Open order symbols: {', '.join(open_order_symbols) if open_order_symbols else 'none'}\n"
            f"Pending records: {len(pending_records)}\n\n"
            f"Last intent: {intent.get('intent', 'n/a')}\n"
            f"Intent reason: {intent.get('reason', 'n/a')}\n"
            f"Safety: {safety.get('reason', 'n/a')}\n"
            f"Execution: {execution.get('reason', 'n/a')}\n\n"
            f"Last cycle: {finished_at}\n"
            f"Updated: {datetime.now(timezone.utc).isoformat()}"
        )

    async def _send_message(self, text: str) -> int:
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"

        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return int(data["result"]["message_id"])

    async def _edit_message(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.config.bot_token}/editMessageText"

        payload = {
            "chat_id": self.config.chat_id,
            "message_id": self.message_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)

            if response.status_code == 400 and "message is not modified" in response.text.lower():
                return

            response.raise_for_status()
