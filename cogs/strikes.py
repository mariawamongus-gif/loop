import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime, timedelta
from typing import Optional
from core.database import AsyncSessionLocal
from core.models import UserStrike, GuildConfig
from core.permissions import is_mod
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class StrikesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="strike", description="إضافة إنذار إداري آلي بحق عضو مع تطبيق التصعيد")
    @app_commands.describe(user="العضو المستهدف", reason="سبب الإنذار")
    async def add_strike(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await is_mod(interaction):
            await interaction.response.send_message("خطأ: لا تمتلك صلاحيات الإشراف لاستخدام هذا الأمر.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            strike = UserStrike(
                guild_id=interaction.guild_id,
                user_id=user.id,
                mod_id=interaction.user.id,
                reason=reason
            )
            session.add(strike)
            await session.commit()

            # حساب إجمالي الإنذارات النشطة
            res = await session.execute(
                select(UserStrike).where(
                    UserStrike.guild_id == interaction.guild_id,
                    UserStrike.user_id == user.id
                )
            )
            strikes = res.scalars().all()
            strike_count = len(strikes)

        # تطبيق التصعيد الآلي حسب عدد الإنذارات
        action_msg = ""
        if strike_count == 2:
            try:
                await user.timeout(timedelta(hours=1), reason="تجاوز 2 إنذارات (تصعيد آلي)")
                action_msg = "\n**التصعيد الآلي:** تم تطبيق كتم مؤقت لمدة ساعة لتجاوز 2 إنذارات."
            except Exception:
                pass
        elif strike_count == 4:
            try:
                await user.timeout(timedelta(hours=24), reason="تجاوز 4 إنذارات (تصعيد آلي)")
                action_msg = "\n**التصعيد الآلي:** تم تطبيق كتم مؤقت لمدة 24 ساعة لتجاوز 4 إنذارات."
            except Exception:
                pass
        elif strike_count >= 6:
            try:
                await user.kick(reason="تجاوز 6 إنذارات (تصعيد آلي)")
                action_msg = "\n**التصعيد الآلي:** تم طرد العضو من السيرفر لتجاوز 6 إنذارات."
            except Exception:
                pass

        embed = create_neon_embed(
            "تسجيل إنذار إداري | Strike System",
            f"تم تسجيل إنذار جديد بحق {user.mention}.\n"
            f"**السبب:** {reason}\n"
            f"**إجمالي الإنذارات:** `{strike_count}`{action_msg}"
        )
        await interaction.response.send_message(embed=embed)

        await log_decision(
            interaction.guild,
            command=f"/strike add user={user.id}",
            check_result=f"العدد الإجمالي الحالي للإنذارات: {strike_count}",
            execution_step="تسجيل الإنذار في قاعدة البيانات وتنفيذ قاعدة التصعيد",
            outcome=f"تم التوثيق {action_msg.replace('**', '')}"
        )

    @app_commands.command(name="strikes_list", description="عرض الإنذارات المسجلة بحق عضو")
    @app_commands.describe(user="العضو المستهدف")
    async def list_strikes(self, interaction: discord.Interaction, user: discord.Member):
        if not await is_mod(interaction):
            await interaction.response.send_message("خطأ: لا تمتلك الصلاحيات المطلوبة.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserStrike).where(
                    UserStrike.guild_id == interaction.guild_id,
                    UserStrike.user_id == user.id
                ).order_by(UserStrike.created_at.desc())
            )
            strikes = res.scalars().all()

        if not strikes:
            embed = create_neon_embed(f"سجل إنذارات {user.name}", "لا توجد إنذارات مسجلة لهذا العضو.")
            await interaction.response.send_message(embed=embed)
            return

        desc = f"**إجمالي الإنذارات:** `{len(strikes)}`\n\n"
        for s in strikes[:10]:
            desc += f"• **#Strike-{s.strike_id}** | السبب: {s.reason} | التاريخ: `{s.created_at.strftime('%Y-%m-%d')}`\n"

        embed = create_neon_embed(f"سجل إنذارات {user.name}", desc)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(StrikesCog(bot))
