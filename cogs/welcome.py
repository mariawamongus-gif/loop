import discord
from discord.ext import commands
from discord import app_commands
from sqlalchemy.future import select
from datetime import datetime
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_admin
from core.strings import Strings
from utils.embeds import create_neon_embed, create_success_embed
from utils.welcome_card import generate_welcome_card


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

            # إسناد Auto-Role تلقائياً
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
                    avatar_url = member.display_avatar.url if member.display_avatar else ""
                    
                    # توليد بطاقة الترحيب الرخامية الفاخرة بنمط TS
                    card_buffer = await generate_welcome_card(
                        username=member.name,
                        avatar_url=avatar_url,
                        server_name=guild.name,
                        member_count=guild.member_count
                    )
                    
                    file = discord.File(card_buffer, filename=f"welcome_{member.id}.png")
                    
                    # رسالة الترحيب مع منشن العضو
                    content = f"مرحباً بك في **{guild.name}** يا {member.mention}! ✨"
                    
                    embed = create_neon_embed(
                        f"✦ أهلاً بك في {guild.name} ✦",
                        f"نورت السيرفر يا {member.mention} | أنت العضو رقم **#{guild.member_count}** 🎉",
                        color=0xD4AF37
                    )
                    embed.set_image(url=f"attachment://welcome_{member.id}.png")
                    embed.set_footer(text=f"ID: {member.id} • {guild.name}")

                    try:
                        await channel.send(content=member.mention, embed=embed, file=file)
                    except Exception:
                        pass

    # ─── /test_welcome ──────────────────────────────────────────────────────────
    @app_commands.command(name="test_welcome", description="معاينة واختبار بطاقة الترحيب الرخامية الفاخرة")
    async def test_welcome(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        avatar_url = interaction.user.display_avatar.url if interaction.user.display_avatar else ""
        card_buffer = await generate_welcome_card(
            username=interaction.user.name,
            avatar_url=avatar_url,
            server_name=interaction.guild.name,
            member_count=interaction.guild.member_count
        )

        file = discord.File(card_buffer, filename="welcome_preview.png")
        embed = create_neon_embed(
            f"✦ معاينة بطاقة الترحيب الرخامية | {interaction.guild.name} ✦",
            f"هذا نموذج بطاقة الترحيب الفاخرة المنقوشة بشعار **TS** عند انضمام عضو جديد! 🎉",
            color=0xD4AF37
        )
        embed.set_image(url="attachment://welcome_preview.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
