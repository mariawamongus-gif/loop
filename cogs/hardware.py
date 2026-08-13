import discord
from discord import app_commands
from discord.ext import commands
import psutil
import platform
import subprocess
import os
import sys
from datetime import datetime
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class HardwareCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_motherboard_info(self) -> dict:
        """
        يجلب تفاصيل اللوحة الأم (Motherboard) و BIOS بناءً على بيئة النظام.
        """
        mb_info = {"manufacturer": "غير معروف", "model": "غير معروف", "bios": "غير معروف"}
        try:
            if platform.system() == "Windows":
                # استعلام WMIC على نظام ويندوز
                cmd_mb = "wmic baseboard get Manufacturer,Product,SerialNumber /format:csv"
                out_mb = subprocess.check_output(cmd_mb, shell=True, text=True, stderr=subprocess.DEVNULL)
                lines = [l.strip() for l in out_mb.splitlines() if l.strip()]
                if len(lines) > 1:
                    parts = lines[1].split(",")
                    if len(parts) >= 3:
                        mb_info["manufacturer"] = parts[1] or "N/A"
                        mb_info["model"] = parts[2] or "N/A"

                cmd_bios = "wmic bios get SMBIOSBIOSVersion,Manufacturer /format:csv"
                out_bios = subprocess.check_output(cmd_bios, shell=True, text=True, stderr=subprocess.DEVNULL)
                lines_bios = [l.strip() for l in out_bios.splitlines() if l.strip()]
                if len(lines_bios) > 1:
                    p_bios = lines_bios[1].split(",")
                    if len(p_bios) >= 3:
                        mb_info["bios"] = f"{p_bios[1]} {p_bios[2]}"
            elif platform.system() == "Linux":
                # استعلام Linux sys/class/dmi
                try:
                    with open("/sys/class/dmi/id/board_vendor", "r") as f:
                        mb_info["manufacturer"] = f.read().strip()
                    with open("/sys/class/dmi/id/board_name", "r") as f:
                        mb_info["model"] = f.read().strip()
                    with open("/sys/class/dmi/id/bios_version", "r") as f:
                        mb_info["bios"] = f.read().strip()
                except Exception:
                    pass
        except Exception:
            pass
        return mb_info

    @app_commands.command(name="hardware_scan", description="فحص هاردوير ومكونات السيرفر واللوحة الأم بالكامل (Motherboard / CPU / RAM / Disks)")
    async def hardware_scan(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر الفحص الشامل للهاردوير على أدمنية السيرفر فقط.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # 1. اللوحة الأم (Motherboard) والـ BIOS
        mb = self._get_motherboard_info()

        # 2. المعالج (CPU Topology)
        cpu_model = platform.processor() or "محدد آلياً"
        cpu_cores_phys = psutil.cpu_count(logical=False) or 1
        cpu_cores_log = psutil.cpu_count(logical=True) or 1
        cpu_freq = psutil.cpu_freq()
        freq_str = f"{round(cpu_freq.current, 1)} MHz" if cpu_freq else "N/A"
        cpu_load = psutil.cpu_percent(interval=0.5)

        # 3. الذاكرة العشوائية (RAM Topology)
        ram = psutil.virtual_memory()
        ram_total_gb = round(ram.total / (1024**3), 2)
        ram_used_gb = round(ram.used / (1024**3), 2)
        ram_free_gb = round(ram.available / (1024**3), 2)

        # 4. أقراص التخزين (Storage & Disks)
        disks_str = ""
        for p in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(p.mountpoint)
                total_gb = round(usage.total / (1024**3), 1)
                free_gb = round(usage.free / (1024**3), 1)
                disks_str += f"• **قرص `{p.device}` ({p.fstype}):** `{usage.percent}%` مستخدم (`{free_gb} GB` فارغ من `{total_gb} GB`)\n"
            except Exception:
                continue

        if not disks_str:
            disks_str = "• تعذر قراءة تفاصيل الأقراص المباشرة.\n"

        # 5. شبكة السيرفر (Network Cards)
        net_io = psutil.net_io_counters()
        bytes_sent_mb = round(net_io.bytes_sent / (1024**2), 1)
        bytes_recv_mb = round(net_io.bytes_recv / (1024**2), 1)

        # 6. نظام التشغيل والنواة
        os_info = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"
        host_name = platform.node()

        def make_bar(pct):
            filled = int(pct / 10)
            return "█" * filled + "░" * (10 - filled)

        desc = (
            f"`──────── اللوحة الأم والنظام (Motherboard & OS) ────────`\n"
            f"**الشركة المصنعة للوحة:** `{mb['manufacturer']}`\n"
            f"**موديل اللوحة الأم:** `{mb['model']}`\n"
            f"**نسخة الـ BIOS:** `{mb['bios']}`\n"
            f"**اسم المستضيف (Hostname):** `{host_name}`\n"
            f"**نظام التشغيل:** `{os_info}`\n\n"
            f"`──────── المعالج (CPU Topology) ────────`\n"
            f"**اسم المعالج:** `{cpu_model}`\n"
            f"**الأنوية الفزيائية:** `{cpu_cores_phys}` | **الأنوية المنطقية:** `{cpu_cores_log}`\n"
            f"**التردد الحالي:** `{freq_str}`\n"
            f"**مؤشر الضغط:** `{make_bar(cpu_load)}` `{cpu_load}%`\n\n"
            f"`──────── الذاكرة العشوائية (RAM) ────────`\n"
            f"**إجمالي الذاكرة:** `{ram_total_gb} GB`\n"
            f"**المستخدم:** `{ram_used_gb} GB` | **الفارغ:** `{ram_free_gb} GB`\n"
            f"**مؤشر الاستهلاك:** `{make_bar(ram.percent)}` `{ram.percent}%`\n\n"
            f"`──────── وحدات التخزين (Storage & Disks) ────────`\n"
            f"{disks_str}\n"
            f"`──────── حركة الشبكة (Network I/O) ────────`\n"
            f"**مرسل (TX):** `{bytes_sent_mb} MB` | **مستقبل (RX):** `{bytes_recv_mb} MB`"
        )

        embed = create_neon_embed("فحص الهاردوير واللوحة الأم الشامل | Hardware & Motherboard Scan", desc, color=0x00F5FF)
        await interaction.followup.send(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command="/hardware_scan",
            check_result="صلاحيات الأدمن مفحوصة بالكامل",
            execution_step="استعلام مكونات اللوحة الأم والمعالج والذاكرة والأقراص",
            outcome="توليد تقرير الهاردوير الشامل بنجاح"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(HardwareCog(bot))
