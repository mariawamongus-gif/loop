import discord
from discord.ext import commands
from aiohttp import web
import asyncio
import os
import psutil
import time
from datetime import datetime
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, DecisionLogEntry
from config import Config
import logging

logger = logging.getLogger(__name__)


class WebDashboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.runner = None
        self.site = None

    async def cog_load(self):
        if Config.DASHBOARD_ENABLED:
            asyncio.create_task(self._start_web_server())

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()

    async def _start_web_server(self):
        await self.bot.wait_until_ready()
        try:
            app = web.Application()
            app.router.add_get('/', self.handle_index)
            app.router.add_get('/api/stats', self.handle_stats)
            app.router.add_get('/api/guilds', self.handle_guilds)
            app.router.add_get('/api/logs', self.handle_logs)

            self.runner = web.AppRunner(app)
            await self.runner.setup()
            
            port = Config.DASHBOARD_PORT
            self.site = web.TCPSite(self.runner, '0.0.0.0', port)
            await self.site.start()
            logger.info(f"🌐 لوحة تحكم الويب Neon Dashboard تعمل بنجاح على: http://0.0.0.0:{port}")
        except Exception as e:
            logger.warning(f"تعذر تشغيل سيرفر لوحة التحكم Web Dashboard: {e}")

    async def handle_index(self, request):
        index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                return web.Response(text=f.read(), content_type='text/html')
        return web.Response(text="<h1>Neon Dashboard UI is loading...</h1>", content_type='text/html')

    async def handle_stats(self, request):
        uptime_sec = int(time.time() - self.start_time)
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        ram_mb = 0
        try:
            ram_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
        except Exception:
            pass

        data = {
            "latency_ms": round(self.bot.latency * 1000) if self.bot.latency else 0,
            "uptime": uptime_str,
            "guilds_count": len(self.bot.guilds),
            "total_users": sum(g.member_count for g in self.bot.guilds if g.member_count),
            "cogs_count": len(self.bot.cogs),
            "ram_mb": ram_mb
        }
        return web.json_response(data)

    async def handle_guilds(self, request):
        guilds_data = []
        async with AsyncSessionLocal() as session:
            for g in self.bot.guilds:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == g.id))
                config = res.scalars().first()
                protection = config.protection_enabled if config else True

                guilds_data.append({
                    "id": str(g.id),
                    "name": g.name,
                    "member_count": g.member_count,
                    "channels_count": len(g.channels),
                    "protection": protection
                })
        return web.json_response(guilds_data)

    async def handle_logs(self, request):
        logs_data = []
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DecisionLogEntry).order_by(DecisionLogEntry.timestamp.desc()).limit(20)
            )
            logs = res.scalars().all()
            for l in logs:
                logs_data.append({
                    "time": l.timestamp.strftime("%H:%M:%S") if l.timestamp else "--:--",
                    "command": l.command[:25],
                    "outcome": l.outcome[:60]
                })
        return web.json_response(logs_data)


async def setup(bot: commands.Bot):
    await bot.add_cog(WebDashboardCog(bot))
