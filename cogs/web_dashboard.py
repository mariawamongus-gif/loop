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

# المظهر الافتراضي الكامل للوحة التحكم في حال عدم العثور على ملف خارجي
DEFAULT_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Neon Engine | Tactical Cyber Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #07090e;
      --bg-card: rgba(16, 22, 34, 0.75);
      --bg-card-hover: rgba(22, 30, 46, 0.85);
      --border-subtle: rgba(0, 245, 255, 0.15);
      --border-glow: rgba(0, 245, 255, 0.4);
      --neon-cyan: #00f5ff;
      --neon-green: #50fa7b;
      --neon-purple: #bd93f9;
      --neon-red: #ff5555;
      --neon-yellow: #ffb86c;
      --text-main: #f8f9fa;
      --text-muted: #8b9bb4;
      --font-ui: 'Cairo', sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: var(--font-ui);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 10% 20%, rgba(0, 245, 255, 0.05) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(189, 147, 249, 0.05) 0%, transparent 40%);
    }
    header {
      padding: 1.25rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-subtle);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(7, 9, 14, 0.8);
    }
    .brand { display: flex; align-items: center; gap: 1rem; }
    .brand-icon {
      width: 42px; height: 42px; border-radius: 10px;
      background: linear-gradient(135deg, #00f5ff, #bd93f9);
      display: flex; align-items: center; justify-content: center;
      font-weight: 900; font-size: 1.3rem; color: #07090e;
      box-shadow: 0 0 15px rgba(0, 245, 255, 0.3);
    }
    .brand-title { font-size: 1.4rem; font-weight: 900; }
    .brand-title span { color: var(--neon-cyan); }
    .system-status {
      display: flex; align-items: center; gap: 0.6rem;
      font-size: 0.85rem; font-weight: 600; padding: 0.4rem 0.9rem;
      background: rgba(80, 250, 123, 0.1);
      border: 1px solid rgba(80, 250, 123, 0.3);
      border-radius: 20px; color: var(--neon-green);
    }
    .pulse-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background-color: var(--neon-green);
      box-shadow: 0 0 8px var(--neon-green);
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
    main { flex: 1; padding: 2rem; max-width: 1400px; margin: 0 auto; width: 100%; }
    .grid-stats {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.25rem; margin-bottom: 2rem;
    }
    .stat-card {
      background: var(--bg-card); border: 1px solid var(--border-subtle);
      border-radius: 14px; padding: 1.25rem; backdrop-filter: blur(10px);
      transition: all 0.25s ease; display: flex; flex-direction: column; justify-content: space-between;
    }
    .stat-card:hover { border-color: var(--border-glow); transform: translateY(-2px); background: var(--bg-card-hover); }
    .stat-label { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 600; }
    .stat-value { font-size: 1.8rem; font-weight: 900; font-family: var(--font-mono); color: var(--neon-cyan); }
    .stat-extra { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.4rem; }
    .dashboard-body { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
    @media (max-width: 960px) { .dashboard-body { grid-template-columns: 1fr; } }
    .section-box {
      background: var(--bg-card); border: 1px solid var(--border-subtle);
      border-radius: 14px; padding: 1.5rem; backdrop-filter: blur(10px);
    }
    .section-title {
      font-size: 1.1rem; font-weight: 700; margin-bottom: 1.25rem;
      display: flex; align-items: center; gap: 0.6rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06); padding-bottom: 0.75rem;
    }
    .server-list { display: flex; flex-direction: column; gap: 0.75rem; }
    .server-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 1rem; background: rgba(0, 0, 0, 0.25);
      border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;
    }
    .server-info { display: flex; align-items: center; gap: 0.8rem; }
    .server-icon {
      width: 36px; height: 36px; border-radius: 50%;
      background: #1e2638; display: flex; align-items: center; justify-content: center; font-weight: 700;
    }
    .badge-on {
      background: rgba(80, 250, 123, 0.15); color: var(--neon-green);
      padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 700;
    }
    .terminal-window {
      background: #040609; border: 1px solid rgba(0, 245, 255, 0.15);
      border-radius: 10px; padding: 1rem; font-family: var(--font-mono); font-size: 0.8rem;
      height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.5rem;
    }
    .log-row {
      display: flex; gap: 0.6rem; line-height: 1.4;
      border-bottom: 1px solid rgba(255, 255, 255, 0.03); padding-bottom: 0.4rem;
    }
    .log-time { color: var(--text-muted); min-width: 70px; }
    .log-cmd { color: var(--neon-cyan); font-weight: 700; }
    .log-outcome { color: var(--text-main); }
    footer {
      padding: 1.5rem 2rem; text-align: center; font-size: 0.85rem;
      color: var(--text-muted); border-top: 1px solid var(--border-subtle);
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-icon">N</div>
      <div class="brand-title">NEON <span>ENGINE</span></div>
    </div>
    <div class="system-status">
      <div class="pulse-dot"></div>
      <span>TACTICAL RADAR ACTIVE</span>
    </div>
  </header>
  <main>
    <div class="grid-stats">
      <div class="stat-card">
        <div class="stat-label">معدل الاستجابة (Ping)</div>
        <div class="stat-value" id="stat-ping">-- ms</div>
        <div class="stat-extra">زمن استجابة ديسكورد اللحظي</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">مدة التشغيل المستمر (Uptime)</div>
        <div class="stat-value" id="stat-uptime">--</div>
        <div class="stat-extra">منذ الإطلاق الميداني</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">إجمالي الأعضاء المخدومين</div>
        <div class="stat-value" id="stat-users">--</div>
        <div class="stat-extra" id="stat-guilds">-- سيرفر نشط</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">استهلاك الذاكرة (RAM)</div>
        <div class="stat-value" id="stat-ram">-- MB</div>
        <div class="stat-extra" id="stat-cogs">-- Cogs مفعلة</div>
      </div>
    </div>
    <div class="dashboard-body">
      <div class="section-box">
        <div class="section-title">
          <span>🛡️</span>
          <span>السيرفرات والأنظمة الدفاعية المتصلة</span>
        </div>
        <div class="server-list" id="guilds-container">
          <div style="color: var(--text-muted); text-align: center; padding: 2rem;">جاري استخراج بيانات السيرفرات...</div>
        </div>
      </div>
      <div class="section-box">
        <div class="section-title">
          <span>⚡</span>
          <span>سجل القرارات والتدخلات الأمنية الحية</span>
        </div>
        <div class="terminal-window" id="logs-container">
          <div class="log-row">
            <span class="log-time">[--:--]</span>
            <span class="log-cmd">SYSTEM</span>
            <span class="log-outcome">جاري الاتصال بقاعدة بيانات القرارات...</span>
          </div>
        </div>
      </div>
    </div>
  </main>
  <footer>
    Neon Engine v2.0 • وحدة العمليات الاستراتيجية والتحكم المركزي • جميع الحقوق محفوظة
  </footer>
  <script>
    async function fetchStats() {
      try {
        const res = await fetch('/api/stats');
        if (res.ok) {
          const data = await res.json();
          document.getElementById('stat-ping').innerText = `${data.latency_ms} ms`;
          document.getElementById('stat-uptime').innerText = data.uptime;
          document.getElementById('stat-users').innerText = data.total_users.toLocaleString();
          document.getElementById('stat-guilds').innerText = `${data.guilds_count} سيرفرات متصلة`;
          document.getElementById('stat-ram').innerText = `${data.ram_mb} MB`;
          document.getElementById('stat-cogs').innerText = `${data.cogs_count} Cogs تكتيكية جاهزة`;
        }
      } catch (err) {
        console.error("Stats fetch error:", err);
      }
    }
    async function fetchGuilds() {
      try {
        const res = await fetch('/api/guilds');
        if (res.ok) {
          const guilds = await res.json();
          const container = document.getElementById('guilds-container');
          if (guilds.length === 0) {
            container.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 2rem;">لا توجد سيرفرات متصلة حالياً.</div>`;
            return;
          }
          container.innerHTML = guilds.map(g => `
            <div class="server-item">
              <div class="server-info">
                <div class="server-icon">${g.name.charAt(0)}</div>
                <div>
                  <div style="font-weight: 700;">${g.name}</div>
                  <div style="font-size: 0.8rem; color: var(--text-muted);">${g.member_count} عضو • ${g.channels_count} قناة</div>
                </div>
              </div>
              <div class="badge-on">${g.protection ? 'PROTECTION ON' : 'STANDARD'}</div>
            </div>
          `).join('');
        }
      } catch (err) {
        console.error("Guilds fetch error:", err);
      }
    }
    async function fetchLogs() {
      try {
        const res = await fetch('/api/logs');
        if (res.ok) {
          const logs = await res.json();
          const container = document.getElementById('logs-container');
          if (logs.length === 0) {
            container.innerHTML = `<div style="color: var(--text-muted); padding: 1rem;">لا توجد سجلات أمنية بعد.</div>`;
            return;
          }
          container.innerHTML = logs.map(l => `
            <div class="log-row">
              <span class="log-time">${l.time}</span>
              <span class="log-cmd">${l.command}</span>
              <span class="log-outcome">${l.outcome}</span>
            </div>
          `).join('');
        }
      } catch (err) {
        console.error("Logs fetch error:", err);
      }
    }
    function refreshAll() {
      fetchStats();
      fetchGuilds();
      fetchLogs();
    }
    refreshAll();
    setInterval(refreshAll, 5000);
  </script>
</body>
</html>"""


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
            app.router.add_get('/favicon.ico', self.handle_favicon)
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

    async def handle_favicon(self, request):
        return web.Response(status=204)

    async def handle_index(self, request):
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
