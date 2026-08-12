import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime, timedelta
from typing import Optional
from core.database import AsyncSessionLocal
from core.models import ModerationCase, GuildConfig
from core.permissions import is_mod
from core.strings import Strings
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _create_case(
        self, guild_id: int, user_id: int, mod_id: int, action: str, reason: str, duration: Optional[str] = None
    ) -> int:
        async with AsyncSessionLocal() as session:
            case = ModerationCase(
                guild_id=guild_id,
                user_id=user_id,
                mod_id=mod_id,
                action=action,
                reason=reason,
                duration=duration,
                created_at=datetime.utcnow()
            )
            session.add(case)
            await session.commit()
            await session.refresh(case)
            return case.case_id

    # 1. /ban
    @app_commands.command(name="ban", description="حظر عضو من السيرفر وتسجيل الحالة")
    @app_commands.describe(user="العضو المراد حظره", reason="سبب الحظر")
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "لم يتم تحديد سبب"):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        case_id = await self._create_case(interaction.guild_id, user.id, interaction.user.id, "BAN", reason)
        try:
            await user.ban(reason=f"[Case #{case_id}] {reason}")
            msg = Strings.MOD_BAN_SUCCESS.format(user=user.mention, reason=reason, case_id=case_id)
            embed = create_neon_embed("إجراء إداري | Ban", msg)
            await interaction.response.send_message(embed=embed)
            
            await log_decision(
                interaction.guild,
                command=f"/ban {user.id}",
                check_result="صلاحية الإشراف مؤكدة",
                execution_step=f"حظر العضو وإنشاء Case #{case_id}",
                outcome="تم الحظر وتسجيل الحالة بنجاح"
            )
        except Exception as e:
            await interaction.response.send_message(f"فشل تنفيذ الحظر: {e}", ephemeral=True)

    # 2. /kick
    @app_commands.command(name="kick", description="طرد عضو من السيرفر وتسجيل الحالة")
    @app_commands.describe(user="العضو المرادطرده", reason="سبب الطرد")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "لم يتم تحديد سبب"):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        case_id = await self._create_case(interaction.guild_id, user.id, interaction.user.id, "KICK", reason)
        try:
            await user.kick(reason=f"[Case #{case_id}] {reason}")
            msg = Strings.MOD_KICK_SUCCESS.format(user=user.mention, reason=reason, case_id=case_id)
            embed = create_neon_embed("إجراء إداري | Kick", msg)
            await interaction.response.send_message(embed=embed)

            await log_decision(
                interaction.guild,
                command=f"/kick {user.id}",
                check_result="صلاحية الإشراف مؤكدة",
                execution_step=f"طرد العضو وإنشاء Case #{case_id}",
                outcome="تم الطرد وتسجيل الحالة بنجاح"
            )
        except Exception as e:
            await interaction.response.send_message(f"فشل تنفيذ الطرد: {e}", ephemeral=True)

    # 3. /warn
    @app_commands.command(name="warn", description="تسجيل تحذير إداري رسمي بحق عضو")
    @app_commands.describe(user="العضو المراد تحذيره", reason="سبب التحذير")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        case_id = await self._create_case(interaction.guild_id, user.id, interaction.user.id, "WARN", reason)
        msg = Strings.MOD_WARN_SUCCESS.format(user=user.mention, reason=reason, case_id=case_id)
        embed = create_neon_embed("إجراء إداري | Warn", msg)
        await interaction.response.send_message(embed=embed)

        await log_decision(
            interaction.guild,
            command=f"/warn {user.id}",
            check_result="صلاحية الإشراف مؤكدة",
            execution_step=f"إصدار تحذير وإنشاء Case #{case_id}",
            outcome="تم حفظ التحذير في قاعدة البيانات"
        )

    # 4. /timeout
    @app_commands.command(name="timeout", description="تطبيق مهلة كتم مؤقت (Timeout) على عضو")
    @app_commands.describe(user="العضو المستهدف", minutes="مدة الكتم بالدقائق", reason="السبب")
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "لم يتم تحديد سبب"):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        duration_str = f"{minutes}m"
        case_id = await self._create_case(interaction.guild_id, user.id, interaction.user.id, "TIMEOUT", reason, duration_str)
        try:
            await user.timeout(timedelta(minutes=minutes), reason=f"[Case #{case_id}] {reason}")
            msg = Strings.MOD_TIMEOUT_SUCCESS.format(user=user.mention, duration=duration_str, reason=reason, case_id=case_id)
            embed = create_neon_embed("إجراء إداري | Timeout", msg)
            await interaction.response.send_message(embed=embed)

            await log_decision(
                interaction.guild,
                command=f"/timeout {user.id} {minutes}m",
                check_result="صلاحية الإشراف مؤكدة",
                execution_step=f"تطبيق Timeout وإنشاء Case #{case_id}",
                outcome="تم تنفيذ الكتم المؤقت بنجاح"
            )
        except Exception as e:
            await interaction.response.send_message(f"فشل تنفيذ الـ Timeout: {e}", ephemeral=True)

    # 5. /unban
    @app_commands.command(name="unban", description="إلغاء حظر عضو بواسطة المعرّف (User ID)")
    @app_commands.describe(user_id="معرّف العضو الحظر", reason="سبب إلغاء الحظر")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "إلغاء حظر إداري"):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        try:
            target_id = int(user_id)
            user = await self.bot.fetch_user(target_id)
            await interaction.guild.unban(user, reason=reason)
            case_id = await self._create_case(interaction.guild_id, target_id, interaction.user.id, "UNBAN", reason)
            
            msg = Strings.MOD_UNBAN_SUCCESS.format(user=user.mention, case_id=case_id)
            embed = create_neon_embed("إجراء إداري | Unban", msg)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"تعذر إلغاء الحظر: {e}", ephemeral=True)

    # 6. /history
    @app_commands.command(name="history", description="عرض سجل السوابق والعقوبات الإدارية للعضو")
    @app_commands.describe(user="العضو المراد فحص سجله")
    async def history(self, interaction: discord.Interaction, user: discord.User):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ModerationCase)
                .where(ModerationCase.guild_id == interaction.guild_id, ModerationCase.user_id == user.id)
                .order_by(ModerationCase.created_at.desc())
            )
            cases = result.scalars().all()

        if not cases:
            embed = create_neon_embed(Strings.HISTORY_TITLE.format(user=user.name), Strings.NO_HISTORY)
            await interaction.response.send_message(embed=embed)
            return

        desc = ""
        for c in cases[:10]:  # عرض آخر 10 عقوبات
            desc += f"**Case #{c.case_id}** | `{c.action}` | السبب: {c.reason} | التاريخ: `{c.created_at.strftime('%Y-%m-%d')}`\n"

        embed = create_neon_embed(Strings.HISTORY_TITLE.format(user=user.name), desc)
        await interaction.response.send_message(embed=embed)

    # 7. /clear
    @app_commands.command(name="clear", description="مسح الرسائل مع فلاتر اختيارية للعضو ونطاق التاريخ (من تاريخ إلى تاريخ)")
    @app_commands.describe(
        amount="عدد الرسائل المفحوصة للمسح (الافتراضي 100)",
        user="تحديد عضو معين لحذف رسائله فقط (اختياري)",
        from_date="بداية تاريخ الحذف بصيغة YYYY-MM-DD (مثال: 2026-08-01)",
        to_date="نهاية تاريخ الحذف بصيغة YYYY-MM-DD (مثال: 2026-08-12)"
    )
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int = 100,
        user: Optional[discord.User] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        start_dt = None
        end_dt = None

        if from_date:
            try:
                start_dt = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send("خطأ: صيغة تاريخ البداية (from_date) غير صحيحة. يجب أن تكون YYYY-MM-DD.", ephemeral=True)
                return

        if to_date:
            try:
                end_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            except ValueError:
                await interaction.followup.send("خطأ: صيغة تاريخ النهاية (to_date) غير صحيحة. يجب أن تكون YYYY-MM-DD.", ephemeral=True)
                return

        def check_msg(msg: discord.Message) -> bool:
            if user and msg.author.id != user.id:
                return False
            msg_dt = msg.created_at.replace(tzinfo=None)
            if start_dt and msg_dt < start_dt:
                return False
            if end_dt and msg_dt > end_dt:
                return False
            return True

        try:
            deleted = await interaction.channel.purge(limit=amount, check=check_msg)
            count = len(deleted)
            
            user_info = f" الخاص بالعضو {user.mention}" if user else ""
            date_info = f" في الفترة بين `{from_date or 'البداية'}` و `{to_date or 'الآن'}`" if (from_date or to_date) else ""
            
            msg = f"تم مسح `{count}` رسالة بنجاح{user_info}{date_info}."
            embed = create_neon_embed("حذف الرسائل | Clear", msg)
            await interaction.followup.send(embed=embed, ephemeral=True)

            await log_decision(
                interaction.guild,
                command=f"/clear amount={amount} user={user.id if user else 'All'} from={from_date} to={to_date}",
                check_result="صلاحية الإشراف مفحوصة والتواريخ مصادق عليها",
                execution_step=f"تنفيذ purge على القناة {interaction.channel.name}",
                outcome=f"تم مسح {count} رسالة"
            )
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ أثناء مسح الرسائل: {e}", ephemeral=True)

    # 8. /scan_user
    @app_commands.command(name="scan_user", description="فحص أمني وتدقيق شامل لحساب العضو وحساب تقييم المخاطر")
    @app_commands.describe(user="العضو المراد فحص حسابه تقنياً")
    async def scan_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        now = datetime.utcnow()
        account_age_days = (now - user.created_at.replace(tzinfo=None)).days
        joined_age_days = (now - user.joined_at.replace(tzinfo=None)).days if user.joined_at else 0

        async with AsyncSessionLocal() as session:
            res_cases = await session.execute(
                select(ModerationCase).where(ModerationCase.guild_id == interaction.guild_id, ModerationCase.user_id == user.id)
            )
            cases_count = len(res_cases.scalars().all())

        risk_score = 0
        if account_age_days < 7:
            risk_score += 40
        elif account_age_days < 30:
            risk_score += 20

        risk_score += min(cases_count * 15, 50)
        if user.guild_permissions.administrator:
            risk_score += 10

        risk_score = min(risk_score, 100)
        status_level = "منخفض / Low Risk" if risk_score < 30 else ("متوسط / Moderate Risk" if risk_score < 60 else "مرتفع عالي الخطورة / High Risk")

        desc = (
            f"**المستهدف:** {user.mention} (`{user.id}`)\n"
            f"**مؤشر الخطورة الآلي (Risk Score):** `{risk_score}%` — `{status_level}`\n\n"
            f"• **تاريخ إنشاء الحساب:** `{user.created_at.strftime('%Y-%m-%d')}` (`{account_age_days}` يوم)\n"
            f"• **تاريخ انضمام السيرفر:** `{user.joined_at.strftime('%Y-%m-%d') if user.joined_at else 'غير معروف'}` (`{joined_age_days}` يوم)\n"
            f"• **عدد القضايا الإدارية المسجلة:** `{cases_count}`\n"
            f"• **أعلى رول:** {user.top_role.mention}\n"
            f"• **صلاحيات حساسة:** `{'نعم (Administrator)' if user.guild_permissions.administrator else 'عادي'}`"
        )

        embed = create_neon_embed(f"تقرير الفحص الأمني | User Security Scan", desc)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))


