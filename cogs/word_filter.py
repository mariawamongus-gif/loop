import discord
from discord.ext import commands
import re
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_whitelisted
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class WordFilterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _normalize_text(self, text: str) -> str:
        """
        تزيل الفواصل والمسافات المخفية للتصدّي لمحاولات التلاعب بالكلمات (مثل: s.p.a.m / s_p_a_m)
        """
        # إزالة الرموز والفواصل الخاصة
        cleaned = re.sub(r'[\.\-_\*\s\W]+', '', text)
        return cleaned.lower()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or len(message.content.strip()) < 3:
            return

        # تجاهل قنوات التذاكر تماماً لتجنب التضارب
        if message.channel.name.startswith("ticket-"):
            return

        guild = message.guild
        author = message.author

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.moderation_enabled:
                return

        if await is_whitelisted(guild.id, author.id, "user"):
            return

        # الكلمات المحظورة النموذجية
        banned_patterns = ["spam", "nuke", "raid", "hack", "virus", "token"]
        normalized = self._normalize_text(message.content)

        for pattern in banned_patterns:
            if pattern in normalized:
                try:
                    await message.delete()
                    embed = create_neon_embed(
                        "تصفية الكلمات | Smart Word Filter",
                        f"تم حذف رسالة العضو {author.mention} آلياً لاحتوائها على كلمة محظورة بعد كشف محاولة التلاعب بالفواصل.",
                        color=0xFF5555
                    )
                    await message.channel.send(embed=embed, delete_after=10)

                    await log_decision(
                        guild,
                        command="AUTOMATED_WORD_FILTER_BYPASS",
                        check_result=f"كشف كلمة محظورة ({pattern}) بالنص المعالج: {normalized[:30]}",
                        execution_step="حذف الرسالة الفوري",
                        outcome="تم منع التجاوز بنجاح"
                    )
                    break
                except Exception:
                    pass

async def setup(bot: commands.Bot):
    await bot.add_cog(WordFilterCog(bot))
