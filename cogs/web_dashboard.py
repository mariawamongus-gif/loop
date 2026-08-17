import discord
from discord.ext import commands
from aiohttp import web
import asyncio
import os
import psutil
import time
import sys
from datetime import datetime
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, DecisionLogEntry, SupportTicket, UserLevel, ModerationCase
from core.config_manager import save_guild_config_field
from config import Config
import logging

logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>Dashboard Loading...</title>
</head>
<body>
  Dashboard Loading...
</body>
</html>"""

def cors_response(data, status=200):
    return web.json_response(data, status=status, headers={"Access-Control-Allow-Origin": "*"})

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
            
            # Serve static files for assets
            assets_path = os.path.join(os.getcwd(), 'assets')
            if not os.path.exists(assets_path):
                os.makedirs(assets_path, exist_ok=True)
            app.router.add_static('/assets/', path=assets_path, name='assets')

            app.router.add_get('/', self.handle_index)
            app.router.add_get('/favicon.ico', self.handle_favicon)
            
            # Existing endpoints
            app.router.add_get('/api/stats', self.handle_stats)
            app.router.add_get('/api/guilds', self.handle_guilds)
            app.router.add_get('/api/logs', self.handle_logs)
            
            # New endpoints
            app.router.add_get('/api/tickets', self.handle_tickets)
            app.router.add_get('/api/leaderboard', self.handle_leaderboard)
            app.router.add_get('/api/config/{guild_id}', self.handle_config)
            app.router.add_post('/api/toggle_feature', self.handle_toggle_feature)
            app.router.add_get('/api/cases', self.handle_cases)
            app.router.add_get('/api/system_health', self.handle_system_health)

            self.runner = web.AppRunner(app)
            await self.runner.setup()
            
            port = Config.DASHBOARD_PORT
            self.site = web.TCPSite(self.runner, '0.0.0.0', port)
            await self.site.start()
            logger.info(f"🌐 لوحة تحكم الويب Neon Dashboard تعمل بنجاح على: http://0.0.0.0:{port}")
        except Exception as e:
            logger.warning(f"تعذر تشغيل سيرفر لوحة التحكم Web Dashboard: {e}")

    async def handle_favicon(self, request):
        return web.Response(status=204)

    async def handle_index(self, request):
        try:
            candidate_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', 'index.html'),
                os.path.join(os.getcwd(), 'web', 'index.html'),
                '/app/web/index.html',
                'web/index.html'
            ]
            for p in candidate_paths:
                if os.path.exists(p):
                    try:
                        with open(p, 'r', encoding='utf-8') as f:
                            return web.Response(text=f.read(), content_type='text/html')
                    except Exception:
                        pass
            return web.Response(text=DEFAULT_DASHBOARD_HTML, content_type='text/html')
        except Exception as e:
            logger.error(f"Error in handle_index: {e}")
            return web.Response(text=DEFAULT_DASHBOARD_HTML, content_type='text/html')

    async def handle_stats(self, request):
        try:
            uptime_sec = int(time.time() - self.start_time)
            hours, remainder = divmod(uptime_sec, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"

            ram_mb = 0
            cpu_percent = 0
            try:
                process = psutil.Process()
                ram_mb = round(process.memory_info().rss / (1024 * 1024), 1)
                cpu_percent = psutil.cpu_percent(interval=None)
            except Exception:
                pass

            total_commands = len(self.bot.tree.get_commands()) if hasattr(self.bot, 'tree') else 0

            data = {
                "latency_ms": round(self.bot.latency * 1000) if self.bot.latency else 0,
                "uptime": uptime_str,
                "guilds_count": len(self.bot.guilds),
                "total_users": sum(g.member_count for g in self.bot.guilds if g.member_count),
                "cogs_count": len(self.bot.cogs),
                "ram_mb": ram_mb,
                "cpu_percent": cpu_percent,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "discord_version": discord.__version__,
                "total_commands": total_commands
            }
            return cors_response(data)
        except Exception as e:
            logger.error(f"Error in handle_stats: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_guilds(self, request):
        try:
            guilds_data = []
            async with AsyncSessionLocal() as session:
                for g in self.bot.guilds:
                    res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == g.id))
                    config = res.scalars().first()
                    
                    protection = config.protection_enabled if config else True
                    admin_role_id = config.admin_role_id if config else None
                    mod_role_id = config.mod_role_id if config else None

                    icon_url = g.icon.url if g.icon else None

                    guilds_data.append({
                        "id": str(g.id),
                        "name": g.name,
                        "member_count": g.member_count,
                        "channels_count": len(g.channels),
                        "protection": protection,
                        "icon_url": icon_url,
                        "admin_role_id": str(admin_role_id) if admin_role_id else None,
                        "mod_role_id": str(mod_role_id) if mod_role_id else None
                    })
            return cors_response(guilds_data)
        except Exception as e:
            logger.error(f"Error in handle_guilds: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_logs(self, request):
        try:
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
            return cors_response(logs_data)
        except Exception as e:
            logger.error(f"Error in handle_logs: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_tickets(self, request):
        try:
            tickets_data = []
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(SupportTicket)
                    .where(SupportTicket.status.in_(["OPEN", "ESCALATED"]))
                    .order_by(SupportTicket.created_at.desc())
                )
                tickets = res.scalars().all()
                for t in tickets:
                    tickets_data.append({
                        "ticket_id": t.ticket_id,
                        "guild_id": str(t.guild_id),
                        "user_id": str(t.user_id),
                        "status": t.status,
                        "severity": t.severity,
                        "category": t.category,
                        "evidence_status": t.evidence_status,
                        "created_at": t.created_at.isoformat() if t.created_at else None
                    })
            return cors_response(tickets_data)
        except Exception as e:
            logger.error(f"Error in handle_tickets: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_leaderboard(self, request):
        try:
            leaderboard_data = []
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(UserLevel).order_by(UserLevel.level.desc(), UserLevel.xp.desc()).limit(15)
                )
                users = res.scalars().all()
                for u in users:
                    leaderboard_data.append({
                        "guild_id": str(u.guild_id),
                        "user_id": str(u.user_id),
                        "level": u.level,
                        "xp": u.xp
                    })
            return cors_response(leaderboard_data)
        except Exception as e:
            logger.error(f"Error in handle_leaderboard: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_config(self, request):
        try:
            guild_id_str = request.match_info.get('guild_id', None)
            if not guild_id_str or not guild_id_str.isdigit():
                return cors_response({"error": "Invalid guild ID"}, status=400)
            
            guild_id = int(guild_id_str)
            config_data = {}
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
                config = res.scalars().first()
                if config:
                    config_data = {
                        "guild_id": str(config.guild_id),
                        "protection_enabled": config.protection_enabled,
                        "moderation_enabled": config.moderation_enabled,
                        "tickets_enabled": config.tickets_enabled,
                        "leveling_enabled": config.leveling_enabled,
                        "welcome_enabled": config.welcome_enabled,
                        "logging_enabled": config.logging_enabled,
                        "ai_enabled": config.ai_enabled,
                        "stats_enabled": config.stats_enabled,
                        "silent_protocol": config.silent_protocol
                    }
                else:
                    return cors_response({"error": "Config not found"}, status=404)
            return cors_response(config_data)
        except Exception as e:
            logger.error(f"Error in handle_config: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_toggle_feature(self, request):
        try:
            data = await request.json()
            guild_id = data.get("guild_id")
            feature_name = data.get("feature_name")

            if not guild_id or not feature_name:
                return cors_response({"error": "Missing guild_id or feature_name"}, status=400)

            guild_id = int(guild_id)
            
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
                config = res.scalars().first()
                if not config:
                    return cors_response({"error": "Guild config not found"}, status=404)
                
                if not hasattr(config, feature_name):
                    return cors_response({"error": "Invalid feature name"}, status=400)
                
                current_value = getattr(config, feature_name)
                if not isinstance(current_value, bool):
                    return cors_response({"error": "Feature is not a boolean toggle"}, status=400)
                
                new_value = not current_value
            
            await save_guild_config_field(guild_id, feature_name, new_value)
            
            return cors_response({"success": True, "feature_name": feature_name, "new_value": new_value})
        except Exception as e:
            logger.error(f"Error in handle_toggle_feature: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_cases(self, request):
        try:
            cases_data = []
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(ModerationCase).order_by(ModerationCase.created_at.desc()).limit(30)
                )
                cases = res.scalars().all()
                for c in cases:
                    cases_data.append({
                        "case_id": c.case_id,
                        "guild_id": str(c.guild_id),
                        "user_id": str(c.user_id),
                        "mod_id": str(c.mod_id),
                        "action": c.action,
                        "reason": c.reason,
                        "duration": c.duration,
                        "created_at": c.created_at.isoformat() if c.created_at else None
                    })
            return cors_response(cases_data)
        except Exception as e:
            logger.error(f"Error in handle_cases: {e}")
            return cors_response({"error": str(e)}, status=500)

    async def handle_system_health(self, request):
        try:
            ram_mb = 0
            cpu_percent = 0
            disk_usage = 0
            try:
                process = psutil.Process()
                ram_mb = round(process.memory_info().rss / (1024 * 1024), 1)
                cpu_percent = psutil.cpu_percent(interval=None)
                disk = psutil.disk_usage('/')
                disk_usage = disk.percent
            except Exception:
                pass
            
            db_status = "OK"
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(select(GuildConfig).limit(1))
            except Exception:
                db_status = "ERROR"

            health_data = {
                "cpu_percent": cpu_percent,
                "ram_mb": ram_mb,
                "disk_usage_percent": disk_usage,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "discord_version": discord.__version__,
                "database_status": db_status
            }
            return cors_response(health_data)
        except Exception as e:
            logger.error(f"Error in handle_system_health: {e}")
            return cors_response({"error": str(e)}, status=500)

async def setup(bot: commands.Bot):
    await bot.add_cog(WebDashboardCog(bot))
