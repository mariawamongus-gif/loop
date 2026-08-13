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
        """جلب تفاصيل اللوحة الأم والـ BIOS."""
        mb_info = {"manufacturer": "N/A", "model": "N/A", "bios": "N/A", "serial": "N/A"}
        try:
            if platform.system() == "Windows":
                cmd_mb = "wmic baseboard get Manufacturer,Product,SerialNumber /format:csv"
                out_mb = subprocess.check_output(cmd_mb, shell=True, text=True, stderr=subprocess.DEVNULL)
                lines = [l.strip() for l in out_mb.splitlines() if l.strip()]
                if len(lines) > 1:
                    parts = lines[1].split(",")
                    if len(parts) >= 4:
                        mb_info["manufacturer"] = parts[1] or "N/A"
                        mb_info["model"] = parts[2] or "N/A"
                        mb_info["serial"] = parts[3] or "N/A"

                cmd_bios = "wmic bios get SMBIOSBIOSVersion,Manufacturer /format:csv"
                out_bios = subprocess.check_output(cmd_bios, shell=True, text=True, stderr=subprocess.DEVNULL)
                lines_bios = [l.strip() for l in out_bios.splitlines() if l.strip()]
                if len(lines_bios) > 1:
                    p_bios = lines_bios[1].split(",")
                    if len(p_bios) >= 3:
                        mb_info["bios"] = f"{p_bios[1]} {p_bios[2]}"
            elif platform.system() == "Linux":
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

    def _get_gpu_info(self) -> str:
        """استعلام كارت الشاشة GPU."""
        try:
            if platform.system() == "Windows":
                cmd = "wmic path win32_videocard get name /format:csv"
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                gpus = []
                for line in lines[1:]:
                    parts = line.split(",")
                    if len(parts) >= 2 and parts[1]:
                        gpus.append(parts[1])
                return ", ".join(gpus) if gpus else "كارت مدمج / Virtual Display"
            elif platform.system() == "Linux":
                cmd = "lspci | grep -i vga"
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
                return out.strip()[:100] if out.strip() else "Virtual GPU"
        except Exception:
            pass
        return "غير معروف / Virtualized"

    @app_commands.command(
        name="hardware_scan",
        description="فحص أجزاء اللوحة الأم والمعالج والذاكرة وكارت الشاشة والأقراص بالكامل"
    )
    async def hardware_scan(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(
                "خطأ: يقتصر هذا الأمر التشخيصي على الأدمنية فقط.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # 1. Motherboard & BIOS
        mb = self._get_motherboard_info()

        # 2. CPU
        cpu_model = platform.processor() or "محدد آلياً"
        cpu_cores_phys = psutil.cpu_count(logical=False) or 1
        cpu_cores_log = psutil.cpu_count(logical=True) or 1
        cpu_freq = psutil.cpu_freq()
        freq_str = f"{round(cpu_freq.current, 1)} MHz" if cpu_freq else "N/A"
        cpu_load = psutil.cpu_percent(interval=0.5)

        # 3. RAM
        ram = psutil.virtual_memory()
        ram_total_gb = round(ram.total / (1024**3), 2)
        ram_used_gb = round(ram.used / (1024**3), 2)
        ram_free_gb = round(ram.available / (1024**3), 2)

        # 4. GPU
        gpu_str = self._get_gpu_info()

        # 5. Storage / Disks
        disks_str = ""
        for p in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(p.mountpoint)
                total_gb = round(usage.total / (1024**3), 1)
                free_gb = round(usage.free / (1024**3), 1)
                disks_str += (
                    f"  • **قرص `{p.device}` ({p.fstype}):** `{usage.percent}%` مستخدم "
                    f"(`{free_gb} GB` فارغ من `{total_gb} GB`)\n"
                )
            except Exception:
                continue

        if not disks_str:
            disks_str = "  • تعذر قراءة تفاصيل الأقراص المباشرة.\n"

        # 6. Network
        net_io = psutil.net_io_counters()
        bytes_sent_mb = round(net_io.bytes_sent / (1024**2), 1)
        bytes_recv_mb = round(net_io.bytes_recv / (1024**2), 1)

        # 7. OS & Host
        os_info = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"
        host_name = platform.node()

        def make_bar(pct):
            filled = int(pct / 10)
            return "█" * filled + "░" * (10 - filled)

        desc = (
            f"`──────── اللوحة الأم والنظام (Motherboard & BIOS) ────────`\n"
            f"**المصنّع:** `{mb['manufacturer']}`\n"
            f"**موديل اللوحة:** `{mb['model']}`\n"
            f"**نسخة الـ BIOS:** `{mb['bios']}`\n"
            f"**الرقم التسلسلي:** `{mb['serial']}`\n"
            f"**المستضيف (Hostname):** `{host_name}`\n"
            f"**نظام التشغيل:** `{os_info}`\n\n"

            f"`──────── المعالج (CPU Topology) ────────`\n"
            f"**المعالج:** `{cpu_model}`\n"
            f"**الأنوية:** `{cpu_cores_phys} فيزيائية` | `{cpu_cores_log} منطقية`\n"
            f"**التردد:** `{freq_str}`\n"
            f"**مؤشر الضغط:** `{make_bar(cpu_load)}` `{cpu_load}%`\n\n"

            f"`──────── الذاكرة وكارت الشاشة (RAM & GPU) ────────`\n"
            f"**الذاكرة (RAM):** `{ram_total_gb} GB` إجمالي (`{ram_used_gb} GB` مستخدم | `{ram_free_gb} GB` فارغ)\n"
            f"**استهلاك RAM:** `{make_bar(ram.percent)}` `{ram.percent}%`\n"
            f"**كارت الشاشة (GPU):** `{gpu_str}`\n\n"

            f"`──────── وحدات التخزين (Storage & Disks) ────────`\n"
            f"{disks_str}\n"

            f"`──────── حركة الشبكة (Network I/O) ────────`\n"
            f"**مُرسَل (TX):** `{bytes_sent_mb} MB` | **مُستَقبَل (RX):** `{bytes_recv_mb} MB`"
        )

        embed = create_neon_embed(
            "فحص عتاد السيرفر الشامل | Motherboard & Hardware Audit",
            desc,
            color=0x00F5FF
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command="/hardware_scan",
            check_result="صلاحيات الأدمن مفحوصة",
            execution_step="فحص اللوحة الأم والـ BIOS والمعالج والـ GPU والـ RAM والأقراص",
            outcome="توليد تقرير عتاد السيرفر بنجاح"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HardwareCog(bot))
