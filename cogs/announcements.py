import discord
from discord import app_commands
from discord.ext import commands
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class AnnouncementsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="announce", description="نشر إعلان رسمي منسق برمجياً بقناة معينة مع خيارات المنشن")
    @app_commands.describe(
        channel="القناة المراد نشر الإعلان فيها",
        title="عنوان الإعلان الرسمي",
        content="محتوى الإعلان",
        mention="تنبيه الجميع (@everyone/@here/بدون)"
    )
    @app_commands.choices(mention=[
        app_commands.Choice(name="بدون منشن", value="none"),
        app_commands.Choice(name="منشن @everyone", value="everyone"),
        app_commands.Choice(name="منشن @here", value="here")
    ])
    async def announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        content: str,
        mention: str = "none"
    ):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر نشر الإعلانات الرسمية على الأدمنية فقط.", ephemeral=True)
            return

        embed = create_neon_embed(f"إعلان رسمي | {title}", content, color=0x00F5FF)
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"صادر عن إدارة السيرفر | بواسطة {interaction.user.name}")

        mention_str = ""
        if mention == "everyone":
            mention_str = "@everyone"
        elif mention == "here":
            mention_str = "@here"

        try:
            await channel.send(content=mention_str if mention_str else None, embed=embed)
            await interaction.response.send_message(f"تم نشر الإعلان بنجاح بقناة: {channel.mention}", ephemeral=True)

            await log_decision(
                interaction.guild,
                command=f"/announce title={title[:30]} channel={channel.id}",
                check_result="صلاحيات الأدمن مفحوصة",
                execution_step=f"نشر إعلان رسمي بالـ Embed بقناة {channel.name}",
                outcome="تم الإعلان بنجاح"
            )
        except Exception as e:
            await interaction.response.send_message(f"فشل نشر الإعلان: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AnnouncementsCog(bot))
