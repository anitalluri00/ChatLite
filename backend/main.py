from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - optional runtime dependency
    redis = None


REDIS_URL = os.getenv("REDIS_URL", "")

app = FastAPI(title="ChatLite realtime backend")
local_channels: dict[str, set[WebSocket]] = defaultdict(set)


async def redis_client() -> Any | None:
    if not REDIS_URL or redis is None:
        return None
    return redis.from_url(REDIS_URL, decode_responses=True)


async def broadcast_event(conversation_id: str, encoded: str, client: Any | None = None) -> None:
    if client:
        await client.publish(f"chatlite:{conversation_id}", encoded)
        return
    disconnected = []
    for peer in local_channels[conversation_id]:
        try:
            await peer.send_text(encoded)
        except RuntimeError:
            disconnected.append(peer)
    for peer in disconnected:
        local_channels[conversation_id].discard(peer)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "redis": "enabled" if REDIS_URL else "disabled",
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@app.post("/publish/{conversation_id}")
async def publish(conversation_id: str, request: Request) -> dict[str, str]:
    payload = await request.json()
    event = {
        "conversation_id": conversation_id,
        "payload": json.dumps(payload),
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    client = await redis_client()
    try:
        await broadcast_event(conversation_id, json.dumps(event), client)
    finally:
        if client:
            await client.close()
    return {"status": "published"}


@app.websocket("/ws/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: str) -> None:
    await websocket.accept()
    local_channels[conversation_id].add(websocket)
    client = await redis_client()
    pubsub = None
    listener_task = None

    async def listen_to_redis() -> None:
        if not client:
            return
        channel = f"chatlite:{conversation_id}"
        local_pubsub = client.pubsub()
        await local_pubsub.subscribe(channel)
        try:
            async for event in local_pubsub.listen():
                if event.get("type") == "message":
                    await websocket.send_text(event.get("data", ""))
        finally:
            await local_pubsub.unsubscribe(channel)
            await local_pubsub.close()

    if client:
        pubsub = client
        listener_task = asyncio.create_task(listen_to_redis())

    try:
        while True:
            payload = await websocket.receive_text()
            event = {
                "conversation_id": conversation_id,
                "payload": payload,
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            encoded = json.dumps(event)
            await broadcast_event(conversation_id, encoded, client)
    except WebSocketDisconnect:
        pass
    finally:
        local_channels[conversation_id].discard(websocket)
        if listener_task:
            listener_task.cancel()
        if pubsub:
            await pubsub.close()
