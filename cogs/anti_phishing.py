import discord
from discord.ext import commands
import re
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_whitelisted
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class AntiPhishingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # النماذج المشتبهة للروابط الاحتيالية والملفات التنفيذية
        self.phishing_regex = re.compile(
            r'(discord-gift|discorcl|dlscord|discord-app|discordnitro|steamcommunituv|steamcornmunity|free-nitro)\.[a-z]{2,}',
            re.IGNORECASE
        )
        self.bad_extensions = ('.exe', '.bat', '.vbs', '.scr', '.cmd', '.ps1')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild = message.guild
        author = message.author

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.protection_enabled:
                return

        if await is_whitelisted(guild.id, author.id, "user"):
            return

        # 1. كشف الروابط والاحتيال
        if self.phishing_regex.search(message.content):
            try:
                await message.delete()
                embed = create_neon_embed(
                    "حماية الروابط | Anti-Phishing Link Guard",
                    f"تم اعتراض وحذف رابط احتيالي مشتبه به من العضو {author.mention} لحماية حسابات الأعضاء.",
                    color=0xFF5555
                )
                await message.channel.send(embed=embed, delete_after=10)

                await log_decision(
                    guild,
                    command="AUTOMATED_ANTI_PHISHING_LINK",
                    check_result=f"الرابط يطابق النمط الاحتيالي: {message.content[:50]}",
                    execution_step="حذف الرسالة الفوري لحظر التهديد",
                    outcome="تم إحباط محاولة الاحتيال بنجاح"
                )
            except Exception:
                pass
            return

        # 2. كشف المرفقات التنفيذية الخبيثة
        if message.attachments:
            for att in message.attachments:
                if any(att.filename.lower().endswith(ext) for ext in self.bad_extensions):
                    try:
                        await message.delete()
                        embed = create_neon_embed(
                            "حماية المرفقات | Executable Guard",
                            f"تم حذف ملف تنفيذي خطير (`{att.filename}`) من {author.mention} لمنع انتشار الفيروسات.",
                            color=0xFF5555
                        )
                        await message.channel.send(embed=embed, delete_after=10)

                        await log_decision(
                            guild,
                            command="AUTOMATED_ANTI_EXECUTABLE",
                            check_result=f"امتداد ملف تنفيذي خطير: {att.filename}",
                            execution_step="حذف الرسالة الفوري",
                            outcome="تم منع رفع الملف التنفيذي"
                        )
                        break
                    except Exception:
                        pass

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiPhishingCog(bot))
