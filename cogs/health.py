import discord
from discord import app_commands
from discord.ext import commands
import sys
import os
import psutil
import time
from datetime import datetime
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.redis_client import redis_manager
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(name="health", description="فحص تشخيصي شامل وصحة الخادم والمعالج والخدمات")
    async def health(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: لا تمتلك الصلاحية لاستخدام هذا الأمر التشخيصي.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # 1. قياس استهلاك الموارد
        cpu_usage = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        mem_used_mb = round(memory.used / (1024 * 1024), 1)
        mem_total_mb = round(memory.total / (1024 * 1024), 1)
        mem_pct = memory.percent

        # 2. قياس زمن استجابة قاعدة البيانات (SQLite DB Ping)
        db_start = time.perf_counter()
        db_status = "سليمة 🟢"
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(select(1))
            db_latency = round((time.perf_counter() - db_start) * 1000, 2)
        except Exception as e:
            db_status = f"خطأ: {e} 🔴"
            db_latency = -1

        # 3. قياس زمن استجابة Redis
        redis_start = time.perf_counter()
        redis_status = "سليم (أو ذاكرة مؤقتة) 🟢"
        try:
            await redis_manager.set("ping_test", "ok", expire=5)
            redis_latency = round((time.perf_counter() - redis_start) * 1000, 2)
        except Exception:
            redis_status = "Fallback Memory 🟠"
            redis_latency = 0

        # 4. حساب زمن التشغيل (Uptime)
        uptime_seconds = int(time.time() - self.start_time)
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        gateway_ping = round(self.bot.latency * 1000)

        # أشرطة التقديم والمرئيات
        def make_bar(pct):
            filled = int(pct / 10)
            return "█" * filled + "░" * (10 - filled)

        desc = (
            f"`──────── صحة النظام والعتاد ────────`\n"
            f"**استهلاك المعالج (CPU):** `{make_bar(cpu_usage)}` `{cpu_usage}%`\n"
            f"**الذاكرة (RAM):** `{make_bar(mem_pct)}` `{mem_used_mb}MB / {mem_total_mb}MB` ({mem_pct}%)\n"
            f"**زمن التشغيل المتواصل (Uptime):** `{uptime_str}`\n\n"
            f"`──────── استجابة الخدمات ────────`\n"
            f"**Discord Gateway Ping:** `{gateway_ping}ms`\n"
            f"**قاعدة البيانات (Database):** `{db_status}` ({db_latency}ms)\n"
            f"**الذاكرة السريعة (Redis):** `{redis_status}` ({redis_latency}ms)\n\n"
            f"`──────── معلومات البيئة ────────`\n"
            f"**إصدار Python:** `{sys.version.split()[0]}`\n"
            f"**المكتبة:** `discord.py {discord.__version__}`\n"
            f"**السيرفرات الخادمة:** `{len(self.bot.guilds)}` سيرفر"
        )

        embed = create_neon_embed("التشخيص الفني الشامل | System Diagnostics & Health", desc, color=0x00F5FF)
        await interaction.followup.send(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command="/health",
            check_result="صلاحيات الأدمن مفحوصة",
            execution_step="قياس أداء CPU وRAM وقاعدة البيانات وRedis",
            outcome="توليد تقرير الصحة بنجاح"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(HealthCog(bot))
