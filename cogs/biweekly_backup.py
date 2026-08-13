import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio
from datetime import datetime
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.html_server_clone import generate_server_html_clone
from utils.decision_log import log_decision

class BiWeeklyBackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.biweekly_task.start()

    def cog_unload(self):
        self.biweekly_task.cancel()

    # المجدول الدوري كل أسبوعين (336 ساعة)
    @tasks.loop(hours=336)
    async def biweekly_task(self):
        for guild in self.bot.guilds:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()
                if not config or not config.logging_enabled or not config.log_channel_id:
                    continue

                log_chan = guild.get_channel(config.log_channel_id)
                if log_chan:
                    try:
                        # 1. توليد لقطة HTML المصممة كواجهة ديسكورد
                        html_path = await generate_server_html_clone(guild)
                        html_file = discord.File(html_path, filename=f"server_snapshot_{guild.id}.html")

                        # 2. ملف قاعدة البيانات
                        db_file = None
                        if os.path.exists("neon.db"):
                            db_file = discord.File("neon.db", filename=f"backup_neon_{datetime.utcnow().strftime('%Y%m%d')}.db")

                        embed = create_neon_embed(
                            "النسخ الاحتياطي الأسبوعي الشامل | Bi-Weekly Server Snapshot",
                            f"تم أخذ لقطة سحابية شاملة لقنوات وأعضاء وأدمنية السيرفر بنجاح.\n"
                            f"• **إجمالي الأعضاء:** `{guild.member_count}`\n"
                            f"• **عدد القنوات:** `{len(guild.channels)}`\n"
                            f"• **النسخة المرفقة:** واجهة Discord HTML التفاعلية + ملف قاعدة البيانات."
                        )

                        files = [html_file]
                        if db_file:
                            files.append(db_file)

                        await log_chan.send(embed=embed, files=files)
                    except Exception:
                        pass

    @biweekly_task.before_loop
    async def before_biweekly(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="server_snapshot", description="إنشاء أرشفة واجهة ديسكورد HTML فورية لهيكل السيرفر والأدمنية والقنوات")
    async def server_snapshot(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر الأمر على الأدمنية فقط.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            html_path = await generate_server_html_clone(interaction.guild)
            file = discord.File(html_path, filename=f"snapshot_{interaction.guild_id}.html")

            embed = create_neon_embed(
                "أرشفة السيرفر التفاعلية | Server HTML Clone",
                f"تم أخذ نسخة تفاعلية كاملة بتصميم Discord UI للسيرفر.\n"
                f"تتضمن القنوات، الفئات، الرولات، وأسماء وصور جميع الأدمنية بالتفصيل."
            )
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)

            await log_decision(
                interaction.guild,
                command="/server_snapshot",
                check_result="صلاحيات الأدمن مفحوصة بالكامل",
                execution_step="توليد ملف HTML Clone وإرفاقه",
                outcome="تم إنشاء اللقطة الأرشيفية بنجاح"
            )
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ أثناء أرشفة السيرفر: {e}", ephemeral=True)

    @app_commands.command(name="db_export", description="تصدير وتحميل نسخة فورية من ملف قاعدة البيانات neon.db")
    async def db_export(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: أمر تصدير قاعدة البيانات مقتصر على الأدمنية فقط.", ephemeral=True)
            return

        if not os.path.exists("neon.db"):
            await interaction.response.send_message("ملف قاعدة البيانات غير موجود حالياً.", ephemeral=True)
            return

        file = discord.File("neon.db", filename=f"neon_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db")
        embed = create_neon_embed("تصدير قاعدة البيانات | Database Backup Export", "تم استخراج نسخة محمية من ملف قاعدة البيانات SQLite.")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(BiWeeklyBackupCog(bot))
