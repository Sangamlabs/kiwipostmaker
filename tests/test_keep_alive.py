import os
import pytest
from aiohttp.test_utils import TestClient, TestServer
from src.bot.keep_alive import create_web_app, start_keep_alive, stop_keep_alive


@pytest.mark.asyncio
async def test_keep_alive_routes():
    """Verify '/' returns 'Bot is running' and '/health' returns {'status': 'ok'}."""
    app = create_web_app()
    async with TestClient(TestServer(app)) as client:
        resp_root = await client.get("/")
        assert resp_root.status == 200
        assert await resp_root.text() == "Bot is running"

        resp_health = await client.get("/health")
        assert resp_health.status == 200
        assert await resp_health.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_start_and_stop_keep_alive(monkeypatch):
    """Verify keep-alive server binds using PORT env var and shuts down cleanly."""
    monkeypatch.setenv("PORT", "18432")
    runner = await start_keep_alive()
    try:
        assert runner is not None
    finally:
        await stop_keep_alive(runner)
