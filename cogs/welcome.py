import discord
from discord.ext import commands
from discord import app_commands
from sqlalchemy.future import select
from datetime import datetime
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.strings import Strings
from utils.embeds import create_neon_embed, create_success_embed


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _format_message(self, template: str, member: discord.Member, guild: discord.Guild) -> str:
        """تنسيق رسالة الترحيب مع placeholders."""
        return (
            template
            .replace("{user}", member.mention)
            .replace("{username}", member.name)
            .replace("{server}", guild.name)
            .replace("{count}", str(guild.member_count))
            .replace("{id}", str(member.id))
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild.id)
            )
            config = res.scalars().first()
            if not config or not config.welcome_enabled:
                return

            # إسناد Auto-Role
            if config.auto_role_id:
                role = guild.get_role(config.auto_role_id)
                if role:
                    try:
                        await member.add_roles(role, reason="Auto-Role assignment on join")
                    except Exception:
                        pass

            if config.silent_protocol:
                return

            if config.welcome_channel_id:
                channel = guild.get_channel(config.welcome_channel_id)
                if channel:
                    count = guild.member_count
                    account_age = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days

                    # شريط التقدم نحو أقرب هدف
                    milestones = [50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000]
                    next_milestone = milestones[-1]
                    for m in milestones:
                        if count < m:
                            next_milestone = m
                            break
                    prev_milestone = 0
                    for m in milestones:
                        if m < next_milestone and count >= m:
                            prev_milestone = m

                    progress_pct = min(
                        (count - prev_milestone) / max(next_milestone - prev_milestone, 1), 1.0
                    )
                    filled = int(progress_pct * 12)
                    bar = "█" * filled + "░" * (12 - filled)

                    # رسالة مخصصة أو افتراضية
                    custom_msg = getattr(config, "welcome_message", None) if hasattr(config, "welcome_message") else None

                    desc = (
                        f"**المعرّف:** {member.mention} (`{member.id}`)\n"
                        f"**عمر الحساب:** `{account_age}` يوم\n"
                        f"**العضو رقم:** `#{count}`\n\n"
                        f"`──────── التقدم نحو الهدف التالي ────────`\n"
                        f"`{bar}` `{count}/{next_milestone}`"
                    )

                    if custom_msg:
                        formatted = self._format_message(custom_msg, member, guild)
                        desc = f"💬 **{formatted}**\n\n" + desc

                    embed = create_neon_embed(
                        "🎉 عضو جديد انضم! | Member Join",
                        desc,
                        color=0x00F5FF
                    )
                    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else "")
                    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                    embed.add_field(
                        name="📅 تاريخ إنشاء الحساب",
                        value=f"`{member.created_at.strftime('%Y-%m-%d')}`",
                        inline=True
                    )
                    embed.add_field(
                        name="🏷️ أعلى رول",
                        value=member.top_role.mention,
                        inline=True
                    )

                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild.id)
            )
            config = res.scalars().first()
            if not config or not config.welcome_enabled or config.silent_protocol:
                return

            if config.leave_channel_id:
                channel = guild.get_channel(config.leave_channel_id)
                if channel:
                    stayed_days = 0
                    if member.joined_at:
                        stayed_days = (
                            datetime.utcnow() - member.joined_at.replace(tzinfo=None)
                        ).days

                    top_role = (
                        member.top_role.name
                        if member.top_role and member.top_role.name != "@everyone"
                        else "بدون رول"
                    )

                    desc = (
                        f"**العضو:** `{member.name}` (`{member.id}`)\n"
                        f"**مدة التواجد:** `{stayed_days}` يوم\n"
                        f"**أعلى رول كان:** `{top_role}`\n"
                        f"**الأعضاء المتبقون:** `{guild.member_count}`"
                    )

                    embed = create_neon_embed(
                        "👋 مغادرة | Member Leave",
                        desc,
                        color=0xFF5555
                    )
                    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else "")

                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
