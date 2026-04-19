import asyncio
import json
import os
import re
import time

from loguru import logger

SOCKET_PATH = os.getenv("SOCKET_PATH", "/shared/account.sock")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "default")


class EventEmitter:
    def __init__(self, socket_path: str = SOCKET_PATH):
        self._socket_path = socket_path
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def _connect(self):
        try:
            _, self._writer = await asyncio.open_unix_connection(self._socket_path)
            logger.info(f"UDS connected: {self._socket_path}")
        except Exception as e:
            logger.warning(f"UDS connect failed: {e}")
            self._writer = None

    async def emit(self, event: dict):
        async with self._lock:
            if self._writer is None or self._writer.is_closing():
                await self._connect()
            if self._writer is None:
                logger.error("Cannot emit event: UDS not connected")
                return
            try:
                line = json.dumps(event, ensure_ascii=False) + "\n"
                self._writer.write(line.encode())
                await self._writer.drain()
                logger.info(
                    f"Event emitted: {event.get('event_type')} order={event.get('order_id')}"
                )
            except Exception as e:
                logger.error(f"Event emit failed: {e}")
                self._writer = None


def extract_order_id(message: dict) -> str:
    raw = json.dumps(message, ensure_ascii=False)
    for pattern in [
        r"orderId[=:](\d+)",
        r"bizOrderId[=:](\d+)",
        r"order_detail\?id=(\d+)",
    ]:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    return ""


def extract_item_id(message: dict) -> str:
    raw = json.dumps(message, ensure_ascii=False)
    m = re.search(r"itemId[=:](\d+)", raw)
    return m.group(1) if m else ""


def extract_chat_id(message: dict) -> str:
    try:
        if isinstance(message.get("1"), str) and "@" in message["1"]:
            return message["1"].split("@")[0]
        if isinstance(message.get("1"), dict) and "2" in message["1"]:
            return message["1"]["2"].split("@")[0]
    except Exception:
        pass
    return ""
