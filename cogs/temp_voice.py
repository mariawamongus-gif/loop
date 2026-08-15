import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class TempVoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # تتبع الرومات المؤقتة المنشأة {channel_id: owner_id}
        self.temp_channels = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild

        # 1. إذا انضم العضو لروم "إنشاء روم مؤقت"
        if after.channel:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()

            trigger_id = getattr(config, "temp_voice_channel_id", None) or config.stats_channel_id
            if trigger_id and after.channel.id == trigger_id:
                category = after.channel.category
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(connect=True),
                    member: discord.PermissionOverwrite(connect=True, manage_channels=True, move_members=True)
                }

                try:
                    temp_chan = await guild.create_voice_channel(
                        name=f"🔊 | روم {member.name}",
                        category=category,
                        overwrites=overwrites,
                        reason="Temp Voice Channel Creation"
                    )
                    self.temp_channels[temp_chan.id] = member.id
                    await member.move_to(temp_chan)
                except Exception:
                    pass

        # 2. إذا غادر العضو وكان الروم المؤقت فارغاً -> نحذفه آلياً
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                try:
                    chan_id = before.channel.id
                    await before.channel.delete(reason="Temp Voice Channel Cleanup")
                    self.temp_channels.pop(chan_id, None)
                except Exception:
                    pass

    @app_commands.command(name="set_temp_voice", description="تحديد روم صوتي رئيسي لإنشاء الرومات المؤقتة التلقائية")
    @app_commands.describe(channel="القناة الصوتية التي عند دخولها يتم إنشاء روم مؤقت")
    async def set_temp_voice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر هذا الأمر على أدمنية السيرفر فقط.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = res.scalars().first()
            if not config:
                config = GuildConfig(guild_id=interaction.guild_id)
                session.add(config)

            config.temp_voice_channel_id = channel.id
            await session.commit()

        embed = create_neon_embed(
            "تم ضبط الروم الصوتي المؤقت",
            f"تم اعتماد القناة الصوتية {channel.mention} كقناة رئيسية لإنشاء الرومات المؤقتة التلقائية."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command=f"/set_temp_voice channel={channel.id}",
            check_result="صلاحية الأدمن مفحوصة",
            execution_step="تحديث القناة الرئيسية للرومات المؤقتة",
            outcome="تم حفظ الإعداد بنجاح"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoiceCog(bot))
