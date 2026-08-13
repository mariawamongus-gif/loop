import discord
from discord.ext import commands, tasks
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, SupportTicket

class CounterChannelsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.counter_update_task.start()

    def cog_unload(self):
        self.counter_update_task.cancel()

    # تحديث أسماء القنوات كل 10 دقائق
    @tasks.loop(minutes=10)
    async def counter_update_task(self):
        for guild in self.bot.guilds:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()
                if not config or not config.stats_enabled:
                    continue

                # حساب التذاكر المفتوحة
                res_t = await session.execute(
                    select(SupportTicket).where(SupportTicket.guild_id == guild.id, SupportTicket.status == "OPEN")
                )
                open_tickets_count = len(res_t.scalars().all())

            # تحديث أسماء قنوات الإحصائيات إذا كانت معرفة
            online_count = sum(1 for m in guild.members if m.status != discord.Status.offline)

            for channel in guild.voice_channels:
                name_lower = channel.name.lower()
                if "👥" in channel.name or "أعضاء" in channel.name or "members" in name_lower:
                    try:
                        await channel.edit(name=f"👥 | الأعضاء: {guild.member_count}")
                    except Exception:
                        pass
                elif "🟢" in channel.name or "متصلون" in channel.name or "online" in name_lower:
                    try:
                        await channel.edit(name=f"🟢 | المتصلون: {online_count}")
                    except Exception:
                        pass
                elif "🎫" in channel.name or "تذاكر" in channel.name or "tickets" in name_lower:
                    try:
                        await channel.edit(name=f"🎫 | التذاكر المفتوحة: {open_tickets_count}")
                    except Exception:
                        pass

    @counter_update_task.before_loop
    async def before_counter_update(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(CounterChannelsCog(bot))
