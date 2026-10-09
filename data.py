import asyncio
import json
import websockets
from config import DERIV_SYMBOL, WS_URLS, HISTORY_BOOTSTRAP_CANDLES, HISTORY_BATCH_SIZE


class DerivTicks:
    def __init__(self, symbol=DERIV_SYMBOL):
        self.symbol = symbol
        self.ws = None
        self.url = None

    async def connect(self):
        last_error = None
        for url in WS_URLS:
            try:
                print(f"[DATA] Connecting: {url}", flush=True)
                self.ws = await websockets.connect(
                    url, ping_interval=20, ping_timeout=20, close_timeout=5, open_timeout=15
                )
                self.url = url
                print(f"[DATA] WebSocket connected: {url}", flush=True)
                return
            except Exception as exc:
                last_error = exc
                print(f"[DATA] Connection failed on {url}: {type(exc).__name__}: {exc}", flush=True)
                try:
                    if self.ws:
                        await self.ws.close()
                except Exception:
                    pass
                self.ws = None
        raise last_error or RuntimeError("Unable to connect to Deriv WebSocket")

    async def subscribe(self):
        if not self.ws:
            raise RuntimeError("WebSocket is not connected")
        req_id = 2
        print(f"[DATA] Subscribing to live ticks: {self.symbol}", flush=True)
        await self.ws.send(json.dumps({"ticks": self.symbol, "subscribe": 1, "req_id": req_id}))
        deadline = asyncio.get_running_loop().time() + 10
        while True:
            remaining = max(0.1, deadline - asyncio.get_running_loop().time())
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), remaining))
            if msg.get("error"):
                err = msg["error"]
                raise RuntimeError(f"Tick subscription error: {err.get('code','DerivError')}: {err.get('message','Deriv error')}")
            if msg.get("msg_type") == "tick":
                print(f"[DATA] First live tick received: {msg.get('tick', {}).get('quote')}", flush=True)
                return

    async def bootstrap_candles(self, target=HISTORY_BOOTSTRAP_CANDLES):
        """Download historical M1 candles in <=1000-candle pages.

        The current public API may return only 1000 candles even when a larger
        count is requested, so we walk backwards using the end epoch. Each
        request is one-shot (no subscribe field) and pages are deduplicated.
        """
        if not self.ws:
            raise RuntimeError("WebSocket is not connected")
        target = max(0, int(target))
        if not target:
            return []

        batch = max(100, min(int(HISTORY_BATCH_SIZE), 1000))
        collected = {}
        end = "latest"
        req_id = 1000

        print(f"[DATA] Deep history bootstrap target: {target} M1 candles", flush=True)

        while len(collected) < target:
            req_id += 1
            count = min(batch, target - len(collected))
            request = {
                "ticks_history": self.symbol,
                "end": end,
                "count": count,
                "style": "candles",
                "granularity": 60,
                "req_id": req_id,
            }
            await self.ws.send(json.dumps(request))

            candles = None
            while candles is None:
                msg = json.loads(await asyncio.wait_for(self.ws.recv(), 20))
                if msg.get("error"):
                    err = msg["error"]
                    raise RuntimeError(f"{err.get('code','DerivError')}: {err.get('message','Deriv history error')}")
                if msg.get("msg_type") == "candles":
                    candles = msg.get("candles") or []

            page = []
            for c in candles:
                try:
                    page.append({
                        "ts": int(c["epoch"]),
                        "open": float(c["open"]),
                        "high": float(c["high"]),
                        "low": float(c["low"]),
                        "close": float(c["close"]),
                        "volume": 0,
                    })
                except (KeyError, TypeError, ValueError):
                    continue

            if not page:
                break

            before = len(collected)
            for c in page:
                collected[c["ts"]] = c

            ordered = sorted(collected)
            oldest = ordered[0]
            print(f"[DATA] History page: +{len(collected)-before} unique | total={len(collected)}/{target}", flush=True)

            if len(collected) >= target:
                break
            if len(page) < count:
                print("[DATA] History page shorter than requested; reached available history.", flush=True)
                break

            # Request the next page strictly before the oldest returned candle.
            end = str(oldest - 60)
            await asyncio.sleep(0.25)

        result = [collected[k] for k in sorted(collected)]
        print(f"[DATA] Historical M1 candles received: {len(result)}", flush=True)
        if not result:
            raise RuntimeError("Deriv returned empty candle history")
        return result[-target:]

    async def stream(self):
        last_heartbeat = asyncio.get_running_loop().time()
        tick_count = 0
        while True:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), 45))
            if msg.get("error"):
                raise RuntimeError(msg["error"].get("message", "Deriv error"))
            if msg.get("msg_type") == "tick":
                t = msg.get("tick") or {}
                if t.get("quote") is not None and t.get("epoch") is not None:
                    tick_count += 1
                    now = asyncio.get_running_loop().time()
                    if now - last_heartbeat >= 30:
                        print(f"[HEARTBEAT] Live ticks flowing | count={tick_count} | last_price={t.get('quote')}", flush=True)
                        last_heartbeat = now
                    yield {"epoch": int(t["epoch"]), "quote": float(t["quote"]), "symbol": t.get("symbol", self.symbol)}

    async def close(self):
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
