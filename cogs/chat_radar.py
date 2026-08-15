import discord
from discord.ext import commands
import time
from collections import defaultdict
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_whitelisted
from ai.fallback_manager import ai_manager
from utils.embeds import create_warning_embed, create_neon_embed
from utils.decision_log import log_decision


class ChatRadarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # سجل الرسائل الأخيرة لكل قناة: {channel_id: [(author_name, content, timestamp)]}
        self.channel_history = defaultdict(list)
        # مهدئ التنبيهات لكل قناة: {channel_id: last_warning_timestamp}
        self.channel_cooldowns = {}
        # الكلمات الدلالية للاشتباك اللفظي
        self.tension_keywords = [
            "اخرس", "انقلع", "غبي", "حيوان", "كلب", "يا حمار", "تخسي", "يا فاشل", "ورع",
            "shut up", "idiot", "stfu", "loser", "trash", "noob", "fuck", "bitch", "nigger"
        ]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or len(message.content.strip()) < 4:
            return

        # تجاهل قنوات التذاكر
        if message.channel.name.startswith("ticket-"):
            return

        guild = message.guild
        channel = message.channel
        now = time.time()

        # إضافة الرسالة لسجل القناة المتداول
        self.channel_history[channel.id].append((message.author.display_name, message.content, now))
        # الإبقاء على آخر 6 رسائل فقط ضمن آخر دقيقتين
        self.channel_history[channel.id] = [
            m for m in self.channel_history[channel.id] if now - m[2] < 120
        ][-6:]

        history = self.channel_history[channel.id]
        if len(history) < 3:
            return

        # فحص هل يوجد كلمات توتر أو تراشق
        content_combined = " ".join([m[1].lower() for m in history])
        has_triggers = any(k in content_combined for k in self.tension_keywords)

        # التحقق من الكولد داون (5 دقائق بين كل تدخل بالقناة)
        last_warn = self.channel_cooldowns.get(channel.id, 0)
        if now - last_warn < 300:
            return

        if has_triggers or len(history) >= 5:
            # فحص إعدادات السيرفر
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()
                if not config or not config.protection_enabled or not config.ai_enabled:
                    return

            conversation_sample = "\n".join([f"{m[0]}: {m[1]}" for m in history])

            sys_prompt = (
                "أنت رادار Neon لرصد التوتر والمشاحنات السلوكية في المحادثات. "
                "قيّم درجة التوتر أو الاحتقان أو الشجار بين الأعضاء في المحادثة المرفقة من 0 إلى 100. "
                "أجب برقم فقط (مثال: 85) دون أي نصوص أو شروحات إضافية."
            )

            try:
                score_str = await ai_manager.generate(
                    messages=[{"role": "user", "content": conversation_sample}],
                    system_prompt=sys_prompt
                )
                score = int(''.join(filter(str.isdigit, score_str)) or "0")

                if score >= 75:
                    self.channel_cooldowns[channel.id] = now
                    # 1. تدخل تكتيكي لتهدئة المحادثة
                    embed = create_warning_embed(
                        "تنبيه انضباطي | Tactical De-escalation Alert",
                        "رصدت وحدة Neon ارتفاعاً في وتيرة الاحتقان والتراشق داخل هذه القناة.\n\n"
                        "**التوجيه الإلزامي:** يُرجى من جميع الأطراف خفض وتيرة الحديث والالتزام التام بقوانين السيرفر وآداب الحوار فوراً لتفادي تفعيل إجراءات الكتم التلقائي."
                    )
                    await channel.send(embed=embed)

                    # 2. إشعار المشرفين في قناة السجلات
                    if config.log_channel_id:
                        log_chan = guild.get_channel(config.log_channel_id)
                        if log_chan:
                            mod_embed = create_neon_embed(
                                "رادار التوتر الميداني | Tension Radar Triggered",
                                f"**القناة:** {channel.mention}\n"
                                f"**مستوى التوتر المرصود:** `{score}%`\n"
                                f"**عينة من النقاش:**\n```{conversation_sample[:400]}```",
                                color=0xFFB86C
                            )
                            await log_chan.send(embed=mod_embed)

                    await log_decision(
                        guild,
                        command="AUTOMATED_CHAT_TENSION_RADAR",
                        check_result=f"مؤشر الاحتقان في القناة: {score}%",
                        execution_step="إرسال تنبيه خفض التوتر وإخطار الإدارة",
                        outcome="تم احتواء الموقف بنجاح"
                    )
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatRadarCog(bot))
