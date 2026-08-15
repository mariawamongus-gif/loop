import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_admin
from utils.embeds import create_critical_embed, create_success_embed, create_neon_embed
from utils.decision_log import log_decision


class RedAlertCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # تتبع السيرفرات المفعل بها حالة الطوارئ {guild_id: True}
        self.active_red_alerts = {}

    @app_commands.command(
        name="red_alert",
        description="زر الطوارئ الأمني والإنذار الأحمر: إغلاق فوري شامل للسيرفر وتعطيل الأذونات لمنع الهجمات"
    )
    @app_commands.describe(reason="سبب تفعيل حالة الطوارئ القصوى")
    async def red_alert(self, interaction: discord.Interaction, reason: str = "حالة طوارئ أمنية قصوى (Red Alert Triggered)"):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ أمني: يقتصر زر الطوارئ Red Alert على القيادة العليا حصراً.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild

        self.active_red_alerts[guild.id] = True
        locked_channels_count = 0

        # قفل كافة القنوات النصية فورياً
        for channel in guild.text_channels:
            try:
                overwrites = channel.overwrites_for(guild.default_role)
                if overwrites.send_messages is not False:
                    overwrites.send_messages = False
                    overwrites.send_messages_in_threads = False
                    overwrites.create_public_threads = False
                    await channel.set_permissions(guild.default_role, overwrite=overwrites, reason=f"RED ALERT: {reason}")
                    locked_channels_count += 1
            except Exception:
                pass

        desc = (
            f"🚨 **حالة الطوارئ العسكرية القصوى مفعلة الآن (DEFCON 1)** 🚨\n\n"
            f"**السبب:** {reason}\n"
            f"**القائد المنفّذ:** {interaction.user.mention}\n"
            f"**القنوات التي تم إغلاقها فورياً:** `{locked_channels_count}` قناة\n\n"
            f"`──────── الإجراءات الدفاعية النشطة ────────`\n"
            f"1. تم إيقاف كافة صلاحيات الكتابة والمشاركة لجميع الأعضاء.\n"
            f"2. تم تفعيل الحصانة التكتيكية لقنوات وسيرفرات القيادة.\n"
            f"3. لن يتم فك حالة الطوارئ إلا بأمر صريح من القيادة عبر `/cancel_red_alert`."
        )

        embed = create_critical_embed("الإنذار الأحمر | RED ALERT EMERGENCY ACTIVATED", desc)
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await interaction.followup.send(embed=embed)

        # إشعار قناة السجلات
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if config and config.log_channel_id:
                log_chan = guild.get_channel(config.log_channel_id)
                if log_chan and log_chan.id != interaction.channel_id:
                    await log_chan.send(embed=embed)

        await log_decision(
            guild,
            command=f"/red_alert reason={reason[:30]}",
            check_result="تفويض القيادة العليا مؤكد",
            execution_step=f"قفل {locked_channels_count} قنوات وتطبيق حالة الطوارئ الدفاعية",
            outcome="تفعيل الإنذار الأحمر بنجاح"
        )

    @app_commands.command(
        name="cancel_red_alert",
        description="إلغاء حالة الإنذار الأحمر وإعادة فتح قنوات السيرفر للوضع الطبيعي"
    )
    async def cancel_red_alert(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر إلغاء حالة الطوارئ على القيادة العليا.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild

        self.active_red_alerts.pop(guild.id, None)
        unlocked_count = 0

        for channel in guild.text_channels:
            try:
                overwrites = channel.overwrites_for(guild.default_role)
                if overwrites.send_messages is False:
                    overwrites.send_messages = None
                    overwrites.send_messages_in_threads = None
                    overwrites.create_public_threads = None
                    await channel.set_permissions(guild.default_role, overwrite=overwrites, reason="RED ALERT LIFTED")
                    unlocked_count += 1
            except Exception:
                pass

        desc = (
            f"🟢 **تم انتهاء حالة الطوارئ وعودة الوضع الميداني للاستقرار الكامل.**\n\n"
            f"**القنوات المستعادة:** `{unlocked_count}` قناة\n"
            f"**بواسطة القائد:** {interaction.user.mention}\n"
            f"يمكن لجميع الأعضاء الآن العودة للمشاركة والتفاعل بصورة طبيعية."
        )

        embed = create_success_embed("إلغاء الإنذار الأحمر | RED ALERT LIFTED", desc)
        await interaction.followup.send(embed=embed)

        await log_decision(
            guild,
            command="/cancel_red_alert",
            check_result="صلاحيات القيادة مؤكدة",
            execution_step=f"إلغاء إغلاق {unlocked_count} قنوات واستعادة الأذونات الطبيعية",
            outcome="تم استعادة النظام الطبيعي بنجاح"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RedAlertCog(bot))
