import discord
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from utils.embeds import create_neon_embed

class LoggingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_log(self, guild: discord.Guild, title: str, description: str, color: int = 0x1E1E2E):
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.logging_enabled or not config.log_channel_id:
                return

            channel = guild.get_channel(config.log_channel_id)
            if channel:
                embed = create_neon_embed(title, description, color=color)
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    # 1. سجل حذف الرسائل
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        desc = (
            f"**المؤلف:** {message.author.mention} (`{message.author.id}`)\n"
            f"**القناة:** {message.channel.mention}\n"
            f"**المحتوى المحذوف:**\n```{message.content or 'محتوى غير نصي/وسائط'}```"
        )
        await self._send_log(message.guild, "سجل حذف رسالة | Message Delete", desc, color=0xFF5555)

    # 2. سجل تعديل الرسائل
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        desc = (
            f"**المؤلف:** {before.author.mention} (`{before.author.id}`)\n"
            f"**القناة:** {before.channel.mention}\n"
            f"**قبل:**\n```{before.content}```\n"
            f"**بعد:**\n```{after.content}```"
        )
        await self._send_log(before.guild, "سجل تعديل رسالة | Message Edit", desc, color=0xFFB86C)

    # 3. سجل الصوت (Voice State)
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel != after.channel:
            if not before.channel and after.channel:
                desc = f"**العضو:** {member.mention}\n**انضم إلى القناة الصوتية:** {after.channel.mention}"
                await self._send_log(member.guild, "سجل الصوت | Voice Join", desc, color=0x50FA7B)
            elif before.channel and not after.channel:
                desc = f"**العضو:** {member.mention}\n**غادر القناة الصوتية:** {before.channel.mention}"
                await self._send_log(member.guild, "سجل الصوت | Voice Leave", desc, color=0xFF5555)
            elif before.channel and after.channel:
                desc = f"**العضو:** {member.mention}\n**انتقل من:** {before.channel.mention}\n**إلى:** {after.channel.mention}"
                await self._send_log(member.guild, "سجل الصوت | Voice Move", desc, color=0x8BE9FD)

async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingCog(bot))
