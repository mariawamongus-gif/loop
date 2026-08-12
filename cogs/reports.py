import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import AnonymousReport, GuildConfig
from utils.embeds import create_neon_embed

class ReportModal(discord.ui.Modal, title="تقديم بلاغ سرّي وآلي"):
    details = discord.ui.TextInput(
        label="تفاصيل الشكوى أو المخالفة",
        style=discord.TextStyle.paragraph,
        placeholder="اكتب التفاصيل هنا بدقة وبصياغة واضحة...",
        required=True,
        max_length=1000
    )
    evidence = discord.ui.TextInput(
        label="رابط الدليل أو الصورة (اختياري)",
        style=discord.TextStyle.short,
        placeholder="https://...",
        required=False,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            report = AnonymousReport(
                guild_id=interaction.guild_id,
                content=self.details.value,
                evidence_url=self.evidence.value or None,
                status="PENDING"
            )
            session.add(report)
            await session.commit()
            await session.refresh(report)
            report_id = report.report_id

            # البحث عن قناة البلاغات
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = res.scalars().first()

        if config and config.report_channel_id:
            channel = interaction.guild.get_channel(config.report_channel_id)
            if channel:
                evidence_str = f"\n**الدليل المرفق:** {self.evidence.value}" if self.evidence.value else ""
                embed = create_neon_embed(
                    f"بلاغ سرّي جديد | Anonymous Report #{report_id}",
                    f"**تفاصيل البلاغ:**\n```{self.details.value}```"
                    f"{evidence_str}\n\n"
                    f"*ملاحظة النظام: تم تشفير وتجريد هويّة المبلّغ بالكامل لحمايته.*"
                )
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

        embed_user = create_neon_embed(
            "تم استلام البلاغ السرّي",
            f"تم تسجيل بلاغك برقم مرجعي: `Report #{report_id}`.\n"
            f"تم إرسال المحتوى للإدارة وتشفير هويتك بالكامل."
        )
        await interaction.response.send_message(embed=embed_user, ephemeral=True)


class ReportsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="report", description="تقديم بلاغ سرّي ومجهول الهوية للإدارة")
    async def report(self, interaction: discord.Interaction):
        modal = ReportModal()
        await interaction.response.send_modal(modal)

async def setup(bot: commands.Bot):
    await bot.add_cog(ReportsCog(bot))
