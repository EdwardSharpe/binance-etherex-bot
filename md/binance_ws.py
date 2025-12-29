import asyncio
import json
import time
from decimal import Decimal
import websockets

try:
    import orjson

    def loads(data):
        return orjson.loads(data)
except ImportError:

    def loads(data):
        return json.loads(data)

from config import BINANCE_WS_PAIR, WS_PING_INTERVAL, WS_PING_TIMEOUT, WS_RECONNECT_DELAY
from models.types import OrderbookLevel


class BinanceOrderbookStream:
    def __init__(self, ws_url: str = BINANCE_WS_PAIR, label: str = "") :
        self.url = ws_url
        self.label = label
        self.bids = []
        self.asks = []
        self.last_update_ts: float = 0
        self.connected = False
        self.stream_task = None

    async def connect(self) :
        print(f"[binance] connecting to {self.url}")
        self.stream_task = asyncio.create_task(self.stream_loop())

    async def close(self) :
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
        self.connected = False
        print("[binance] stream stopped")

    def is_connected(self) :
        return self.connected

    def last_update_time(self) :
        return self.last_update_ts

    def get_orderbook(self) :
        return list(self.bids), list(self.asks)

    def depth_weighted_mid(self, levels: int) :
        if levels <= 0 or not self.bids or not self.asks:
            return None

        total_qty = Decimal("0")
        total_value = Decimal("0")

        for level in self.bids[:levels] + self.asks[:levels]:
            if level.price <= 0 or level.quantity <= 0:
                continue
            total_qty += level.quantity
            total_value += level.price * level.quantity

        if total_qty <= 0:
            return None

        return total_value / total_qty

    async def stream_loop(self) :
        while True:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                    max_queue=1,  # Drop old messages if we can't keep up
                    compression=None,
                ) as ws:
                    self.connected = True
                    print("[binance] connected")

                    async for message in ws:
                        self.process_message(message)

            except websockets.ConnectionClosed as e:
                self.connected = False
                print(f"[binance] connection closed: {e}")
            except Exception as e:
                self.connected = False
                print(f"[binance] stream error: {e}")

            # Reconnect after delay
            print(f"[binance] reconnecting in {WS_RECONNECT_DELAY}s...")
            await asyncio.sleep(WS_RECONNECT_DELAY)

    def process_message(self, message: str) :
        try:
            # Using orjson
            data = loads(message)

            raw_bids = data.get("bids")
            raw_asks = data.get("asks")
            # Compatiblity for Binance US - but need to change ws urls to .us from .com
            # Much less liquidity there too as its a separate entity
            if raw_bids is None or raw_asks is None:
                raw_bids = data.get("b", [])
                raw_asks = data.get("a", [])

            if not raw_bids or not raw_asks:
                return

            # Parse bids (highest price first)
            self.bids = [
                OrderbookLevel(
                    price=Decimal(price_str),
                    quantity=Decimal(qty_str),
                )
                for price_str, qty_str in raw_bids
            ]

            # Parse asks (lowest price first)
            self.asks = [
                OrderbookLevel(
                    price=Decimal(price_str),
                    quantity=Decimal(qty_str),
                )
                for price_str, qty_str in raw_asks
            ]

            self.last_update_ts = time.time()

            # Log first update
            if not hasattr(self, "first_update_logged"):
                self.first_update_logged = True
                label = f"{self.label} " if self.label else ""
                print(
                    f"[binance] {label}first orderbook update: "
                    f"best_bid={self.bids[0].price} best_ask={self.asks[0].price}"
                )

        except Exception as e:
            print(f"[binance] message parse error: {e}")
