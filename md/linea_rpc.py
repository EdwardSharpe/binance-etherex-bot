import asyncio
import json
import time
import websockets

from config import LINEA_WSS, WS_PING_INTERVAL, WS_PING_TIMEOUT


class LineaRpcClient:
    def __init__(self, ws_url: str = LINEA_WSS) :
        self.url = ws_url
        self.next_id = 0
        self.ws = None
        self.pending = {}
        self.subscriptions = {}
        self.recv_task = None
        self.connected = False

    async def connect(self) :
        print(f"[linea] connecting to {self.url}")
        self.ws = await websockets.connect(
            self.url,
            ping_interval=WS_PING_INTERVAL,
            ping_timeout=WS_PING_TIMEOUT,
            max_queue=1,
        )
        self.connected = True
        print("[linea] connected")
        self.recv_task = asyncio.create_task(self.recv_loop())

    async def close(self) :
        self.connected = False
        if self.recv_task:
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        print("[linea] connection closed")

    async def recv_loop(self) :
        assert self.ws is not None
        try:
            async for message in self.ws:
                data = json.loads(message)

                if "id" in data:
                    future = self.pending.pop(data["id"], None)
                    if future and not future.done():
                        future.set_result(data)
                    continue

                if data.get("method") == "eth_subscription":
                    params = data.get("params", {})
                    sub_id = params.get("subscription")
                    queue = self.subscriptions.get(sub_id)
                    if queue:
                        result = params.get("result")
                        if isinstance(result, dict):
                            result["received_at"] = time.time()
                        if queue.full():
                            try:
                                queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        try:
                            queue.put_nowait(result)
                        except asyncio.QueueFull:
                            pass
        except websockets.ConnectionClosed:
            self.connected = False
            print("[linea] connection closed unexpectedly")
        except Exception as e:
            self.connected = False
            print(f"[linea] receive error: {e}")

    async def request(self, method: str, params: list) :
        if not self.ws:
            raise RuntimeError("Not connected to Linea")

        self.next_id += 1
        request_id = self.next_id
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future

        await self.ws.send(json.dumps(payload))
        response = await future

        if "error" in response:
            raise RuntimeError(f"RPC error: {response['error']}")

        return response

    async def eth_gas_price(self) :
        response = await self.request("eth_gasPrice", [])
        return int(response["result"], 16)

    async def subscribe_new_heads(self) :
        response = await self.request("eth_subscribe", ["newHeads"])
        sub_id = response["result"]

        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self.subscriptions[sub_id] = queue

        print(f"[linea] subscribed to newHeads ({sub_id})")
        return queue
