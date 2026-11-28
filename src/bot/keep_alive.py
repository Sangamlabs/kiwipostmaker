"""
Keep-Alive Async Web Server for Render Web Service & UptimeRobot.
Render free Web Service ko port open rakhna zaroori hota hai, warna "No open ports detected" error aata hai.
"""
import logging
import os
from aiohttp import web

logger = logging.getLogger("Postbot.KeepAlive")


async def handle_root(request: web.Request) -> web.Response:
    """Root route '/' par simple text response bhejta hai UptimeRobot aur browser ke liye."""
    return web.Response(text="Bot is running", status=200)


async def handle_health(request: web.Request) -> web.Response:
    """Health check route '/health' par JSON status return karta hai Render health check ke liye."""
    return web.json_response({"status": "ok"}, status=200)


def create_web_app() -> web.Application:
    """aiohttp web application banata hai aur routes register karta hai."""
    app = web.Application()
    # GET aur HEAD dono requests handle karne ke liye routes add karo
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    return app


async def start_keep_alive() -> web.AppRunner:
    """
    Async web server ko bot ke hi event loop mein non-blocking tarike se start karta hai.
    Port Render ke PORT env var se leta hai (default 10000).
    """
    port = int(os.environ.get("PORT", 10000))
    host = "0.0.0.0"  # Render ke liye 0.0.0.0 par bind karna zaroori hai

    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    logger.info("Keep-alive web server started on http://%s:%s (routes: /, /health)", host, port)
    return runner


async def stop_keep_alive(runner: web.AppRunner | None) -> None:
    """Bot band hone par web server ko cleanly shutdown karta hai."""
    if runner is not None:
        await runner.cleanup()
        logger.info("Keep-alive web server stopped.")
