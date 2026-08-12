import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy.future import select
from datetime import datetime
from core.database import AsyncSessionLocal
from core.models import GuildConfig, ModerationCase, SupportTicket
from utils.embeds import create_neon_embed
from core.strings import Strings

class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cold_report_scheduler.start()

    def cog_unload(self):
        self.cold_report_scheduler.cancel()

    # التقرير الدوري الآلي الجاف (Cold Report Task)
    @tasks.loop(hours=168)  # أسبوعياً (168 ساعة)
    async def cold_report_scheduler(self):
        for guild in self.bot.guilds:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()
                if not config or not config.stats_enabled or not config.report_channel_id:
                    continue

                # تجميع البيانات الإحصائية
                cases_count = len((await session.execute(select(ModerationCase).where(ModerationCase.guild_id == guild.id))).scalars().all())
                tickets_count = len((await session.execute(select(SupportTicket).where(SupportTicket.guild_id == guild.id))).scalars().all())

                channel = guild.get_channel(config.report_channel_id)
                if channel:
                    desc = (
                        f"**بيانات الفترة المرجعية (أسبوعية):**\n\n"
                        f"- إجمالي عدد الأعضاء: `{guild.member_count}`\n"
                        f"- عدد العقوبات المسجلة: `{cases_count}`\n"
                        f"- إجمالي التذاكر المعالجة: `{tickets_count}`\n"
                        f"- حالة بروتوكول الصمت: `{'مفعّل' if config.silent_protocol else 'معطّل'}`"
                    )
                    embed = create_neon_embed(Strings.COLD_REPORT_TITLE, desc)
                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass

    @cold_report_scheduler.before_loop
    async def before_cold_report(self):
        await self.bot.wait_until_ready()

    # 1. /serverinfo
    @app_commands.command(name="serverinfo", description="عرض بيانات وإحصائيات السيرفر التقنية")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild

        online = sum(1 for m in g.members if m.status != discord.Status.offline)
        bots = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots
        text_ch = len(g.text_channels)
        voice_ch = len(g.voice_channels)
        categories = len(g.categories)
        boost_lvl = g.premium_tier
        boost_count = g.premium_subscription_count or 0
        age_days = (datetime.utcnow() - g.created_at.replace(tzinfo=None)).days

        desc = (
            f"**المعرّف:** `{g.id}`\n"
            f"**المالك:** {g.owner.mention}\n"
            f"**تاريخ الإنشاء:** `{g.created_at.strftime('%Y-%m-%d')}` (`{age_days}` يوم)\n\n"
            f"`──────── الأعضاء ────────`\n"
            f"**الإجمالي:** `{g.member_count}` | **بشر:** `{humans}` | **بوتات:** `{bots}`\n"
            f"**متصلين الآن:** `{online}`\n\n"
            f"`──────── القنوات ────────`\n"
            f"**فئات:** `{categories}` | **نصية:** `{text_ch}` | **صوتية:** `{voice_ch}`\n"
            f"**الرولات:** `{len(g.roles)}`\n\n"
            f"`──────── البوست ────────`\n"
            f"**مستوى البوست:** `{boost_lvl}` | **عدد البوستات:** `{boost_count}`"
        )

        embed = create_neon_embed("معلومات السيرفر | Server Info", desc, color=0x00F5FF)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        if g.banner:
            embed.set_image(url=g.banner.url)
        embed.set_author(name=g.name, icon_url=g.icon.url if g.icon else None)
        await interaction.response.send_message(embed=embed)

    # 2. /userinfo
    @app_commands.command(name="userinfo", description="عرض بيانات تفصيلية عن عضو معين")
    @app_commands.describe(user="العضو المراد فحص بياناته")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        account_age = (datetime.utcnow() - target.created_at.replace(tzinfo=None)).days
        server_age = (datetime.utcnow() - target.joined_at.replace(tzinfo=None)).days if target.joined_at else 0

        roles_list = [r.mention for r in target.roles if r.name != "@everyone"][:8]
        roles_str = " ".join(roles_list) if roles_list else "`بدون رولات`"

        perms = []
        if target.guild_permissions.administrator:
            perms.append("`Administrator`")
        if target.guild_permissions.manage_guild:
            perms.append("`Manage Server`")
        if target.guild_permissions.ban_members:
            perms.append("`Ban Members`")
        if target.guild_permissions.kick_members:
            perms.append("`Kick Members`")
        perms_str = " ".join(perms) if perms else "`عادي`"

        desc = (
            f"**المعرّف:** `{target.id}`\n"
            f"**الحالة:** `{str(target.status).upper()}`\n\n"
            f"`──────── التواريخ ────────`\n"
            f"**إنشاء الحساب:** `{target.created_at.strftime('%Y-%m-%d')}` (`{account_age}` يوم)\n"
            f"**دخول السيرفر:** `{target.joined_at.strftime('%Y-%m-%d') if target.joined_at else 'N/A'}` (`{server_age}` يوم)\n\n"
            f"`──────── الرولات ────────`\n"
            f"**أعلى رول:** {target.top_role.mention}\n"
            f"**الرولات ({len(roles_list)}):** {roles_str}\n\n"
            f"`──────── الصلاحيات ────────`\n"
            f"**صلاحيات رئيسية:** {perms_str}"
        )

        color = 0x00F5FF if target.status == discord.Status.online else (0xFFB86C if target.status == discord.Status.idle else 0xFF5555)
        embed = create_neon_embed(f"معلومات العضو | {target.name}", desc, color=color)
        embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else "")
        await interaction.response.send_message(embed=embed)

    # 3. /stats
    @app_commands.command(name="stats", description="عرض حالة ومؤشرات نظام Neon التشغيلية")
    async def stats(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)

        if latency < 100:
            latency_bar = "████████░░"
            latency_status = "ممتاز"
        elif latency < 250:
            latency_bar = "██████░░░░"
            latency_status = "جيد"
        else:
            latency_bar = "███░░░░░░░"
            latency_status = "بطيء"

        total_users = sum(g.member_count for g in self.bot.guilds)

        desc = (
            f"`──────── الحالة العامة ────────`\n"
            f"**النظام:** `OPERATIONAL`\n"
            f"**الاتصال:** `{latency_bar}` `{latency}ms` ({latency_status})\n\n"
            f"`──────── الأرقام ────────`\n"
            f"**السيرفرات:** `{len(self.bot.guilds)}`\n"
            f"**المستخدمين:** `{total_users}`\n"
            f"**الأوامر المسجلة:** `{len(self.bot.tree.get_commands())}`\n\n"
            f"`──────── المحرك ────────`\n"
            f"**النسخة:** `Neon Engine v2.0`\n"
            f"**المكتبة:** `discord.py {discord.__version__}`"
        )

        embed = create_neon_embed("مؤشرات النظام التشغيلية | System Stats", desc, color=0x50FA7B)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
