import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, ModerationCase, SupportTicket, DecisionLogEntry
from core.permissions import is_admin
from ai.fallback_manager import ai_manager
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision


class DailyIntelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_intel_task.start()

    def cog_unload(self):
        self.daily_intel_task.cancel()

    async def _generate_intel_report(self, guild: discord.Guild) -> str:
        since = datetime.utcnow() - timedelta(hours=24)

        async with AsyncSessionLocal() as session:
            # 1. القضايا الإدارية خلال 24 ساعة
            cases_res = await session.execute(
                select(ModerationCase).where(
                    ModerationCase.guild_id == guild.id,
                    ModerationCase.created_at >= since
                )
            )
            cases = cases_res.scalars().all()

            # 2. التذاكر المعالجة والمفتوحة
            tickets_res = await session.execute(
                select(SupportTicket).where(
                    SupportTicket.guild_id == guild.id,
                    SupportTicket.created_at >= since
                )
            )
            tickets = tickets_res.scalars().all()

            # 3. القرارات والتدخلات الأمنية
            logs_res = await session.execute(
                select(DecisionLogEntry).where(
                    DecisionLogEntry.guild_id == guild.id,
                    DecisionLogEntry.timestamp >= since
                )
            )
            security_logs = logs_res.scalars().all()

        online_count = sum(1 for m in guild.members if m.status != discord.Status.offline)
        bots_count = sum(1 for m in guild.members if m.bot)

        summary_data = (
            f"اسم السيرفر: {guild.name}\n"
            f"إجمالي الأعضاء: {guild.member_count} (متصلين: {online_count}, روبوتات: {bots_count})\n"
            f"إجمالي العقوبات والقرارات الإشرافية خلال 24 ساعة: {len(cases)}\n"
            f"تفاصيل العقوبات: {', '.join([f'{c.action} ({c.reason[:30]})' for c in cases[:5]]) if cases else 'لا توجد عقوبات'}\n"
            f"التذاكر المسجلة خلال 24 ساعة: {len(tickets)}\n"
            f"العمليات والتدخلات الأمنية المحبطة: {len(security_logs)}"
        )

        sys_prompt = (
            "أنت 'Neon' المساعد الاستراتيجي والرئاسي للعمليات (Chief of Staff). "
            "قم بصياغة 'التقرير الاستخباراتي اليومي الشامل (Daily Strategic Intel Briefing)' "
            "بناءً على البيانات المرفقة لآخر 24 ساعة. "
            "صِغ التقرير بلهجة عسكرية تكتيكية منضبطة، موجزة، حازمة، وواضحة جداً. "
            "قسّم التقرير إلى: 1. الموقف الميداني العام 2. العمليات الإشرافية والتذاكر 3. التقييم والتوصيات الأمنية للقيادة. "
            "ممنوع استخدام الإيموجيات التعبيرية أو المجاملات."
        )

        briefing = await ai_manager.generate(
            messages=[{"role": "user", "content": f"بيانات الـ 24 ساعة الماضية:\n{summary_data}"}],
            system_prompt=sys_prompt
        )

        return briefing

    @tasks.loop(hours=24)
    async def daily_intel_task(self):
        for guild in self.bot.guilds:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
                config = res.scalars().first()
                if not config or not config.logging_enabled:
                    continue

                target_channel_id = config.log_channel_id or config.report_channel_id
                if not target_channel_id:
                    continue

                channel = guild.get_channel(target_channel_id)
                if channel:
                    try:
                        report_text = await self._generate_intel_report(guild)
                        embed = create_neon_embed(
                            "التقرير الاستخباراتي اليومي | Daily Intel Briefing",
                            report_text,
                            color=0x00F5FF
                        )
                        embed.set_footer(text=f"تاريخ التقرير: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | وحدة العمليات Neon")
                        await channel.send(embed=embed)
                    except Exception:
                        pass

    @daily_intel_task.before_loop
    async def before_daily_intel(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="daily_intel", description="استخراج وتوليد التقرير الاستخباراتي اليومي الفوري للسيرفر عبر Neon AI")
    async def daily_intel(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر استدعاء التقرير الاستخباراتي على القيادة العليا.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)

        report_text = await self._generate_intel_report(interaction.guild)
        embed = create_neon_embed(
            "التقرير الاستخباراتي اليومي الميداني | Daily Intel Briefing",
            report_text,
            color=0x00F5FF
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"صادر للقيادة بواسطة: {interaction.user.name} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        await interaction.followup.send(embed=embed)

        await log_decision(
            interaction.guild,
            command="/daily_intel",
            check_result="صلاحيات القيادة مؤكدة",
            execution_step="توليد التقرير الاستخباراتي عبر Neon AI",
            outcome="تم نشر الإيجاز الاستراتيجي بنجاح"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyIntelCog(bot))
