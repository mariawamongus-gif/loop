import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_whitelisted, is_mod
from ai.fallback_manager import ai_manager
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class AIModCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or len(message.content.strip()) < 10:
            return

        guild = message.guild
        author = message.author

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.protection_enabled or not config.ai_enabled:
                return

        if await is_whitelisted(guild.id, author.id, "user"):
            return

        # فحص وجود كلمات حادة أو مريبة تستدعي تدقيق AI
        suspicious_words = ["احتيال", "سب", "قذف", "تهديد", "تهكير", "شتم", "scam", "hack", "bypass", "nuke"]
        content_lower = message.content.lower()

        if any(w in content_lower for w in suspicious_words):
            sys_prompt = (
                "أنت وحدة Neon AI السلوكية للحماية والتصنيف. "
                "قم بتقييم درجة الخطورة أو الشتم أو الاحتيال بالرسالة التالية من 0 إلى 100. "
                "أجب برقم فقط يعبر عن النسبة المئوية للسمية (مثال: 85) دون أي كلمات أخرى إطلاقاً."
            )

            try:
                score_str = await ai_manager.generate(
                    messages=[{"role": "user", "content": message.content}],
                    system_prompt=sys_prompt
                )
                score = int(''.join(filter(str.isdigit, score_str)) or "0")

                if score >= 85:
                    try:
                        await message.delete()
                        embed = create_neon_embed(
                            "فلتر الحماية الذكي | AI Auto-Mod",
                            f"تم حذف رسالة العضو {author.mention} آلياً لاحتوائها على مخالفة سلوكية أو لفظية حادة.\n**نسبة التقييم:** `{score}%`",
                            color=0xFF5555
                        )
                        await message.channel.send(embed=embed, delete_after=10)

                        await log_decision(
                            guild,
                            command="AUTOMATED_AI_MOD_TOXICITY",
                            check_result=f"تقييم الذكاء الاصطناعي للرسالة: {score}%",
                            execution_step="حذف الرسالة وإرسال تنبيه مؤقت",
                            outcome="حذف الرسالة المخالفة بنجاح"
                        )
                    except Exception:
                        pass
            except Exception:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(AIModCog(bot))
