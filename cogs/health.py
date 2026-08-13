import discord
from discord import app_commands
from discord.ext import commands
import sys
import os
import psutil
import platform
import time
from datetime import datetime, timedelta
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.redis_client import redis_manager
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision


def _make_bar(pct: float, length: int = 12) -> str:
    filled = int(min(max(pct, 0.0), 100.0) / 100.0 * length)
    return "█" * filled + "░" * (length - filled)


def _status_icon(pct: float) -> str:
    if pct < 60:
        return "🟢"
    elif pct < 85:
        return "🟡"
    return "🔴"


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @app_commands.command(
        name="health",
        description="تشخيص شامل وعميق لصحة السيرفر والمعالج والخدمات والشبكة"
    )
    async def health(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(
                "خطأ: لا تمتلك الصلاحية لاستخدام هذا الأمر التشخيصي.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # 1. CPU
        cpu_usage = psutil.cpu_percent(interval=0.5)
        cpu_count_phys = psutil.cpu_count(logical=False) or 1
        cpu_count_log = psutil.cpu_count(logical=True) or 1
        cpu_freq = psutil.cpu_freq()
        freq_str = f"{round(cpu_freq.current, 1)} MHz" if cpu_freq else "N/A"

        # 2. RAM
        memory = psutil.virtual_memory()
        mem_used_gb = round(memory.used / (1024**3), 2)
        mem_total_gb = round(memory.total / (1024**3), 2)
        mem_pct = memory.percent

        # 3. Disk
        disk_lines = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_lines.append(
                    f"  `{part.device}` ({part.fstype}): "
                    f"`{usage.percent}%` ({round(usage.used / (1024**3), 1)}/"
                    f"{round(usage.total / (1024**3), 1)} GB)"
                )
            except Exception:
                continue
        disk_str = "\n".join(disk_lines) if disk_lines else "  لا توجد بيانات"

        # 4. Network
        net_io = psutil.net_io_counters()
        bytes_sent_mb = round(net_io.bytes_sent / (1024**2), 1)
        bytes_recv_mb = round(net_io.bytes_recv / (1024**2), 1)

        # 5. Process info (this Python process)
        proc = psutil.Process(os.getpid())
        proc_mem_mb = round(proc.memory_info().rss / (1024**2), 1)
        proc_threads = proc.num_threads()

        # 6. Total processes
        total_procs = len(list(psutil.process_iter()))

        # 7. Uptime
        uptime_seconds = int(time.time() - self.start_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        # 8. Discord Gateway Ping
        gateway_ping = round(self.bot.latency * 1000)

        # 9. DB Ping
        db_start = time.perf_counter()
        db_status = "سليمة"
        db_icon = "🟢"
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(select(1))
            db_latency = round((time.perf_counter() - db_start) * 1000, 2)
        except Exception as e:
            db_status = f"خطأ: {str(e)[:30]}"
            db_icon = "🔴"
            db_latency = -1

        # 10. Redis Ping
        redis_start = time.perf_counter()
        try:
            await redis_manager.set("health_ping", "ok", expire=5)
            redis_latency = round((time.perf_counter() - redis_start) * 1000, 2)
            redis_icon = "🟢"
            redis_status = "سليم"
        except Exception:
            redis_latency = 0
            redis_icon = "🟠"
            redis_status = "Fallback Memory"

        # Build Embed
        desc = (
            f"`──────── المعالج (CPU) ────────`\n"
            f"**الاستهلاك:** {_status_icon(cpu_usage)} `{_make_bar(cpu_usage)}` `{cpu_usage}%`\n"
            f"**الأنوية:** `{cpu_count_phys} فيزيائية` / `{cpu_count_log} منطقية` | **التردد:** `{freq_str}`\n\n"

            f"`──────── الذاكرة (RAM) ────────`\n"
            f"**الاستهلاك:** {_status_icon(mem_pct)} `{_make_bar(mem_pct)}` `{mem_pct}%`\n"
            f"**الحجم:** `{mem_used_gb} GB` مستخدم من `{mem_total_gb} GB`\n\n"

            f"`──────── التخزين (Disk) ────────`\n"
            f"{disk_str}\n\n"

            f"`──────── الشبكة (Network I/O) ────────`\n"
            f"**مُرسَل:** `{bytes_sent_mb} MB` | **مُستَقبَل:** `{bytes_recv_mb} MB`\n\n"

            f"`──────── عملية البوت (Process) ────────`\n"
            f"**ذاكرة البوت:** `{proc_mem_mb} MB` | **Threads:** `{proc_threads}`\n"
            f"**إجمالي عمليات النظام:** `{total_procs}`\n\n"

            f"`──────── استجابة الخدمات ────────`\n"
            f"{db_icon} **Database:** `{db_status}` (`{db_latency}ms`)\n"
            f"{redis_icon} **Redis:** `{redis_status}` (`{redis_latency}ms`)\n"
            f"🟢 **Discord Gateway:** `{gateway_ping}ms`\n\n"

            f"`──────── معلومات البيئة ────────`\n"
            f"**زمن التشغيل (Uptime):** `{uptime_str}`\n"
            f"**Python:** `{sys.version.split()[0]}` | **discord.py:** `{discord.__version__}`\n"
            f"**السيرفرات الخادمة:** `{len(self.bot.guilds)}`"
        )

        embed = create_neon_embed(
            "التشخيص الفني الشامل | System Health & Diagnostics",
            desc,
            color=0x00F5FF
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command="/health",
            check_result="صلاحيات الأدمن مفحوصة",
            execution_step="قياس CPU/RAM/Disk/Network/DB/Redis/Process",
            outcome="توليد تقرير الصحة الشامل"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HealthCog(bot))
