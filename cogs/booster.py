import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class BoosterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild

        # فحص هل قام العضو بعمل بوست جديد للسيرفر (Premium Subscriber)
        if not before.premium_since and after.premium_since:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()
                if not config or config.silent_protocol:
                    return

                channel_id = config.welcome_channel_id or config.log_channel_id
                if channel_id:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        desc = (
                            f"شكر فائق وتقدير خاص للعضو {after.mention} لقيامه بعمل **Server Boost** للسيرفر! 🚀\n\n"
                            f"• **إجمالي البوستات:** `{guild.premium_subscription_count}`\n"
                            f"• **مستوى السيرفر الحالي:** `Tier {guild.premium_tier}`"
                        )
                        embed = create_neon_embed("دعم السيرفر | Server Boost Notification", desc, color=0xF47FFF)
                        embed.set_thumbnail(url=after.display_avatar.url if after.display_avatar else "")

                        try:
                            await channel.send(embed=embed)
                        except Exception:
                            pass

                        await log_decision(
                            guild,
                            command="AUTOMATED_BOOST_EVENT",
                            check_result=f"العضو {after.id} قام بعمل Server Boost",
                            execution_step="نشر بطاقة التقدير التلقائية",
                            outcome="تم توثيق الدعم بنجاح"
                        )

async def setup(bot: commands.Bot):
    await bot.add_cog(BoosterCog(bot))
