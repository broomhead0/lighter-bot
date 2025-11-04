# scripts/mock_rest.py — tiny local REST for MakerEngineV1
import time
from aiohttp import web

ORDERS = {}


async def create_order(request: web.Request):
    t0 = time.time()
    payload = await request.json()
    order_id = f"mock-{int(time.time()*1000)}"
    ORDERS[order_id] = {
        "id": order_id,
        "data": payload,
        "ts": t0,
        "status": "open",
    }
    latency = (time.time() - t0) * 1000
    print(f"[mock_rest] POST /orders -> 200 ({latency:.1f} ms) {payload}")
    return web.json_response({"ok": True, "order_id": order_id})


async def cancel_order(request: web.Request):
    t0 = time.time()
    payload = await request.json()
    oid = payload.get("order_id")
    if oid in ORDERS:
        ORDERS[oid]["status"] = "canceled"
        latency = (time.time() - t0) * 1000
        print(
            f"[mock_rest] DELETE /orders/cancel -> 200 ({latency:.1f} ms) order_id={oid}"
        )
        return web.json_response({"ok": True, "order_id": oid})
    latency = (time.time() - t0) * 1000
    print(f"[mock_rest] DELETE /orders/cancel -> 404 ({latency:.1f} ms) order_id={oid}")
    return web.json_response({"ok": False, "error": "not_found"}, status=404)


async def get_health(request: web.Request):
    return web.json_response({"status": "ok", "open_orders": len(ORDERS)})


def make_app():
    app = web.Application()
    app.router.add_post("/orders", create_order)
    app.router.add_delete("/orders/cancel", cancel_order)
    app.router.add_get("/health", get_health)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="127.0.0.1", port=8787)
