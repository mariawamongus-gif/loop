import discord
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.strings import Strings
from utils.embeds import create_neon_embed

class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.welcome_enabled:
                return

            # إسناد Auto-Role إذا تم ضبطه
            if config.auto_role_id:
                role = guild.get_role(config.auto_role_id)
                if role:
                    try:
                        await member.add_roles(role, reason="Auto-Role assignment on join")
                    except Exception:
                        pass

            # احترام بروتوكول الصمت (Silent Protocol)
            if config.silent_protocol:
                return

            if config.welcome_channel_id:
                channel = guild.get_channel(config.welcome_channel_id)
                if channel:
                    count = guild.member_count
                    account_age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days

                    # شريط التقدم نحو أقرب هدف
                    milestones = [50, 100, 250, 500, 1000, 2500, 5000, 10000]
                    next_milestone = milestones[-1]
                    for m in milestones:
                        if count < m:
                            next_milestone = m
                            break
                    prev_milestone = 0
                    for m in milestones:
                        if m < next_milestone and count >= m:
                            prev_milestone = m

                    progress_pct = min((count - prev_milestone) / max(next_milestone - prev_milestone, 1), 1.0)
                    filled = int(progress_pct * 10)
                    bar = "█" * filled + "░" * (10 - filled)

                    desc = (
                        f"تسجيل انضمام جديد للسيرفر.\n\n"
                        f"**المعرّف:** {member.mention} (`{member.id}`)\n"
                        f"**عمر الحساب:** `{account_age}` يوم\n"
                        f"**إجمالي الأعضاء:** `{count}`\n\n"
                        f"**التقدم:** `{bar}` `{count}/{next_milestone}`"
                    )

                    embed = create_neon_embed("سجل الانضمام الآلي | Member Join", desc, color=0x00F5FF)
                    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else "")
                    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                    embed.add_field(name="الحساب مُنشأ بتاريخ", value=f"`{member.created_at.strftime('%Y-%m-%d')}`", inline=True)
                    embed.add_field(name="العضو رقم", value=f"`#{count}`", inline=True)

                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.welcome_enabled or config.silent_protocol:
                return

            if config.leave_channel_id:
                channel = guild.get_channel(config.leave_channel_id)
                if channel:
                    stayed_days = 0
                    if member.joined_at:
                        stayed_days = (datetime.utcnow() - member.joined_at.replace(tzinfo=None)).days

                    top_role = member.top_role.name if member.top_role and member.top_role.name != "@everyone" else "بدون رول"

                    desc = (
                        f"تسجيل مغادرة من السيرفر.\n\n"
                        f"**العضو:** `{member.name}` (`{member.id}`)\n"
                        f"**مدة التواجد:** `{stayed_days}` يوم\n"
                        f"**أعلى رول:** `{top_role}`\n"
                        f"**إجمالي الأعضاء المتبقي:** `{guild.member_count}`"
                    )

                    embed = create_neon_embed("سجل المغادرة الآلي | Member Leave", desc, color=0xFF5555)
                    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else "")

                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass

async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
