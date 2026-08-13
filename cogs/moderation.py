import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime, timedelta
from typing import Optional
from core.database import AsyncSessionLocal
from core.models import ModerationCase, GuildConfig
from core.permissions import is_mod, is_admin
from core.strings import Strings
from utils.embeds import create_neon_embed, create_success_embed, create_error_embed, create_warning_embed
from utils.decision_log import log_decision


# ─── Helper: DM notification ───────────────────────────────────────────────────
async def _dm_notify(user: discord.Member, action: str, reason: str, case_id: int):
    """إرسال إشعار DM للمستخدم عند الإجراء الإداري."""
    try:
        action_labels = {
            "BAN": "🔨 حظر",
            "KICK": "👢 طرد",
            "WARN": "⚠️ تحذير رسمي",
            "TIMEOUT": "🔇 كتم مؤقت",
            "UNBAN": "✅ إلغاء حظر",
            "UNMUTE": "🔊 رفع الكتم",
        }
        label = action_labels.get(action, action)
        embed = discord.Embed(
            title=f"❖  إشعار إداري | {label}",
            description=(
                f"تم تطبيق إجراء إداري على حسابك في أحد السيرفرات.\n\n"
                f"**الإجراء:** `{label}`\n"
                f"**السبب:** {reason}\n"
                f"**رقم الحالة:** `#{case_id}`\n\n"
                f"للاعتراض، تواصل مع إدارة السيرفر."
            ),
            color=0xFF5555,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Neon Engine • Administrative Action")
        await user.send(embed=embed)
    except Exception:
        pass


# ─── Pagination View for /history ──────────────────────────────────────────────
class HistoryPaginator(discord.ui.View):
    def __init__(self, cases: list, target: discord.User, author_id: int):
        super().__init__(timeout=120)
        self.cases = cases
        self.target = target
        self.author_id = author_id
        self.page = 0
        self.per_page = 8
        self.total_pages = max(1, (len(cases) + self.per_page - 1) // self.per_page)

    def _build_embed(self) -> discord.Embed:
        start = self.page * self.per_page
        end = start + self.per_page
        page_cases = self.cases[start:end]

        action_icons = {
            "BAN": "🔨", "KICK": "👢", "WARN": "⚠️",
            "TIMEOUT": "🔇", "UNBAN": "✅", "UNMUTE": "🔊", "MUTE": "🔇",
        }
        desc = ""
        for c in page_cases:
            icon = action_icons.get(c.action, "📋")
            dur = f" | `{c.duration}`" if c.duration else ""
            desc += (
                f"{icon} **Case #{c.case_id}** | `{c.action}`{dur}\n"
                f"  📝 {c.reason}\n"
                f"  🕐 `{c.created_at.strftime('%Y-%m-%d %H:%M')} UTC`\n\n"
            )

        embed = create_neon_embed(
            f"سجل العقوبات | {self.target.name}",
            desc or "لا توجد سوابق في هذه الصفحة.",
            color=0xFF5555
        )
        embed.set_thumbnail(url=self.target.display_avatar.url if self.target.display_avatar else "")
        embed.set_footer(
            text=f"Neon Engine  •  صفحة {self.page + 1} / {self.total_pages}  •  {len(self.cases)} حالة مجموع"
        )
        return embed

    async def _update(self, interaction: discord.Interaction):
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page >= self.total_pages - 1)
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("هذه القائمة ليست لك.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ السابق", style=discord.ButtonStyle.secondary, custom_id="hist_prev", disabled=True)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self._update(interaction)

    @discord.ui.button(label="التالي ▶", style=discord.ButtonStyle.secondary, custom_id="hist_next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        await self._update(interaction)


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _create_case(
        self,
        guild_id: int,
        user_id: int,
        mod_id: int,
        action: str,
        reason: str,
        duration: Optional[str] = None
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

    # ─── /ban ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="حظر عضو من السيرفر وتسجيل الحالة")
    @app_commands.describe(user="العضو المراد حظره", reason="سبب الحظر", dm_notify="إرسال إشعار للعضو قبل الحظر")
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "لم يتم تحديد سبب",
        dm_notify: bool = True
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        case_id = await self._create_case(
            interaction.guild_id, user.id, interaction.user.id, "BAN", reason
        )

        if dm_notify:
            await _dm_notify(user, "BAN", reason, case_id)

        try:
            await user.ban(reason=f"[Case #{case_id}] {reason}")
            embed = create_error_embed(
                f"حظر عضو | Ban — Case #{case_id}",
                f"**العضو:** {user.mention} (`{user.id}`)\n"
                f"**بواسطة:** {interaction.user.mention}\n"
                f"**السبب:** {reason}"
            )
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

    # ─── /kick ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="طرد عضو من السيرفر وتسجيل الحالة")
    @app_commands.describe(user="العضو المراد طرده", reason="سبب الطرد", dm_notify="إرسال إشعار للعضو")
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "لم يتم تحديد سبب",
        dm_notify: bool = True
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        case_id = await self._create_case(
            interaction.guild_id, user.id, interaction.user.id, "KICK", reason
        )

        if dm_notify:
            await _dm_notify(user, "KICK", reason, case_id)

        try:
            await user.kick(reason=f"[Case #{case_id}] {reason}")
            embed = create_warning_embed(
                f"طرد عضو | Kick — Case #{case_id}",
                f"**العضو:** {user.mention} (`{user.id}`)\n"
                f"**بواسطة:** {interaction.user.mention}\n"
                f"**السبب:** {reason}"
            )
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

    # ─── /warn ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="تسجيل تحذير إداري رسمي بحق عضو")
    @app_commands.describe(user="العضو المراد تحذيره", reason="سبب التحذير", dm_notify="إرسال إشعار للعضو")
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        dm_notify: bool = True
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        case_id = await self._create_case(
            interaction.guild_id, user.id, interaction.user.id, "WARN", reason
        )

        if dm_notify:
            await _dm_notify(user, "WARN", reason, case_id)

        embed = create_warning_embed(
            f"تحذير إداري | Warn — Case #{case_id}",
            f"**العضو:** {user.mention} (`{user.id}`)\n"
            f"**بواسطة:** {interaction.user.mention}\n"
            f"**السبب:** {reason}"
        )
        await interaction.response.send_message(embed=embed)
        await log_decision(
            interaction.guild,
            command=f"/warn {user.id}",
            check_result="صلاحية الإشراف مؤكدة",
            execution_step=f"إصدار تحذير وإنشاء Case #{case_id}",
            outcome="تم حفظ التحذير في قاعدة البيانات"
        )

    # ─── /timeout ───────────────────────────────────────────────────────────────
    @app_commands.command(name="timeout", description="تطبيق كتم مؤقت (Timeout) على عضو")
    @app_commands.describe(
        user="العضو المستهدف",
        minutes="مدة الكتم بالدقائق",
        reason="السبب",
        dm_notify="إرسال إشعار للعضو"
    )
    async def timeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        minutes: int,
        reason: str = "لم يتم تحديد سبب",
        dm_notify: bool = True
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        if minutes < 1 or minutes > 40320:
            await interaction.response.send_message(
                "مدة الكتم يجب أن تكون بين 1 دقيقة و 40320 دقيقة (28 يوم).", ephemeral=True
            )
            return

        duration_str = f"{minutes}m"
        case_id = await self._create_case(
            interaction.guild_id, user.id, interaction.user.id, "TIMEOUT", reason, duration_str
        )

        if dm_notify:
            await _dm_notify(user, "TIMEOUT", reason, case_id)

        try:
            await user.timeout(timedelta(minutes=minutes), reason=f"[Case #{case_id}] {reason}")
            embed = create_warning_embed(
                f"كتم مؤقت | Timeout — Case #{case_id}",
                f"**العضو:** {user.mention} (`{user.id}`)\n"
                f"**المدة:** `{minutes} دقيقة`\n"
                f"**بواسطة:** {interaction.user.mention}\n"
                f"**السبب:** {reason}"
            )
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

    # ─── /unban ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="إلغاء حظر عضو بواسطة المعرّف (User ID)")
    @app_commands.describe(user_id="معرّف العضو المحظور", reason="سبب إلغاء الحظر")
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "إلغاء حظر إداري"
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        try:
            target_id = int(user_id)
            user = await self.bot.fetch_user(target_id)
            await interaction.guild.unban(user, reason=reason)
            case_id = await self._create_case(
                interaction.guild_id, target_id, interaction.user.id, "UNBAN", reason
            )
            embed = create_success_embed(
                f"إلغاء حظر | Unban — Case #{case_id}",
                f"**العضو:** {user.mention} (`{user.id}`)\n"
                f"**بواسطة:** {interaction.user.mention}\n"
                f"**السبب:** {reason}"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"تعذر إلغاء الحظر: {e}", ephemeral=True)

    # ─── /history (paginated) ────────────────────────────────────────────────────
    @app_commands.command(name="history", description="عرض سجل السوابق والعقوبات الإدارية للعضو")
    @app_commands.describe(user="العضو المراد فحص سجله")
    async def history(self, interaction: discord.Interaction, user: discord.User):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ModerationCase)
                .where(
                    ModerationCase.guild_id == interaction.guild_id,
                    ModerationCase.user_id == user.id
                )
                .order_by(ModerationCase.created_at.desc())
            )
            cases = result.scalars().all()

        if not cases:
            embed = create_neon_embed(
                f"سجل العقوبات | {user.name}",
                "لا توجد سوابق إدارية مسجلة لهذا العضو."
            )
            await interaction.response.send_message(embed=embed)
            return

        paginator = HistoryPaginator(cases, user, interaction.user.id)
        paginator.prev_btn.disabled = True
        paginator.next_btn.disabled = (len(cases) <= paginator.per_page)
        await interaction.response.send_message(
            embed=paginator._build_embed(),
            view=paginator
        )

    # ─── /case ────────────────────────────────────────────────────────────────────
    @app_commands.command(name="case", description="عرض تفاصيل حالة إدارية (رقم خاص أو أحدث حالة إدارية)")
    @app_commands.describe(case_id="رقم الحالة الإدارية (اختياري - اتركه فارغاً لعرض أحدث حالة)")
    async def case_detail(self, interaction: discord.Interaction, case_id: Optional[int] = None):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            if case_id is not None:
                result = await session.execute(
                    select(ModerationCase).where(
                        ModerationCase.case_id == case_id,
                        ModerationCase.guild_id == interaction.guild_id
                    )
                )
                case = result.scalars().first()
            else:
                # جلب أحدث حالة إدارية في السيرفر
                result = await session.execute(
                    select(ModerationCase)
                    .where(ModerationCase.guild_id == interaction.guild_id)
                    .order_by(ModerationCase.created_at.desc())
                )
                case = result.scalars().first()

        if not case:
            msg = f"لم يتم العثور على Case #{case_id}." if case_id else "لا توجد حالات إدارية مسجلة في السيرفر بعد."
            await interaction.response.send_message(msg, ephemeral=True)
            return

        try:
            target = await self.bot.fetch_user(case.user_id)
            target_str = f"{target.mention} ({target.name})"
            target_avatar = target.display_avatar.url
        except Exception:
            target_str = f"`{case.user_id}`"
            target_avatar = ""

        try:
            moderator = await self.bot.fetch_user(case.mod_id)
            mod_str = f"{moderator.mention} ({moderator.name})"
        except Exception:
            mod_str = f"`{case.mod_id}`"

        action_icons = {
            "BAN": "🔨", "KICK": "👢", "WARN": "⚠️",
            "TIMEOUT": "🔇", "UNBAN": "✅", "UNMUTE": "🔊",
        }
        icon = action_icons.get(case.action, "📋")

        desc = (
            f"**رقم الحالة:** `#{case.case_id}`\n"
            f"**الإجراء:** {icon} `{case.action}`\n"
            f"**المستهدف:** {target_str}\n"
            f"**المشرف المسؤول:** {mod_str}\n"
            f"**السبب:** {case.reason}\n"
            f"**المدة:** `{case.duration or 'دائم / غير محدد'}`\n"
            f"**التاريخ:** `{case.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC`"
        )

        embed = create_neon_embed(f"تفاصيل الحالة | Case #{case_id}", desc)
        if target_avatar:
            embed.set_thumbnail(url=target_avatar)
        await interaction.response.send_message(embed=embed)

    # ─── /clear ───────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="clear",
        description="مسح الرسائل مع فلاتر اختيارية للعضو والتاريخ"
    )
    @app_commands.describe(
        amount="عدد الرسائل المفحوصة (الافتراضي 100)",
        user="تحديد عضو معين (اختياري)",
        from_date="بداية التاريخ YYYY-MM-DD (اختياري)",
        to_date="نهاية التاريخ YYYY-MM-DD (اختياري)"
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

        start_dt = end_dt = None
        if from_date:
            try:
                start_dt = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send("صيغة from_date غير صحيحة (YYYY-MM-DD).", ephemeral=True)
                return
        if to_date:
            try:
                end_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            except ValueError:
                await interaction.followup.send("صيغة to_date غير صحيحة (YYYY-MM-DD).", ephemeral=True)
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
            user_info = f" للعضو {user.mention}" if user else ""
            date_info = f" ({from_date or '...'} → {to_date or '...'})" if (from_date or to_date) else ""
            embed = create_success_embed(
                "حذف الرسائل | Clear",
                f"تم مسح `{count}` رسالة{user_info}{date_info} بنجاح."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            await log_decision(
                interaction.guild,
                command=f"/clear amount={amount}",
                check_result="صلاحية الإشراف مفحوصة",
                execution_step=f"purge على القناة {interaction.channel.name}",
                outcome=f"حذف {count} رسالة"
            )
        except Exception as e:
            await interaction.followup.send(f"حدث خطأ: {e}", ephemeral=True)

    # ─── /scan_user ───────────────────────────────────────────────────────────────
    @app_commands.command(name="scan_user", description="فحص أمني شامل لحساب عضو مع تقييم مستوى الخطورة")
    @app_commands.describe(user="العضو المراد فحصه")
    async def scan_user(self, interaction: discord.Interaction, user: discord.Member):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        await interaction.response.defer()

        now = datetime.utcnow()
        account_age_days = (now - user.created_at.replace(tzinfo=None)).days
        joined_age_days = (now - user.joined_at.replace(tzinfo=None)).days if user.joined_at else 0

        async with AsyncSessionLocal() as session:
            res_cases = await session.execute(
                select(ModerationCase).where(
                    ModerationCase.guild_id == interaction.guild_id,
                    ModerationCase.user_id == user.id
                )
            )
            all_cases = res_cases.scalars().all()
            cases_count = len(all_cases)

        risk_score = 0
        risk_reasons = []

        if account_age_days < 7:
            risk_score += 40
            risk_reasons.append("🔴 الحساب أقل من أسبوع")
        elif account_age_days < 30:
            risk_score += 20
            risk_reasons.append("🟡 الحساب أقل من شهر")

        case_score = min(cases_count * 15, 50)
        risk_score += case_score
        if cases_count > 0:
            risk_reasons.append(f"🔴 يوجد {cases_count} سابقة إدارية")

        if user.guild_permissions.administrator:
            risk_score += 10
            risk_reasons.append("🟡 يملك صلاحيات Administrator")

        if not user.avatar:
            risk_score += 10
            risk_reasons.append("🟡 لا يوجد صورة ملف شخصي")

        risk_score = min(risk_score, 100)

        if risk_score < 30:
            risk_level = "🟢 منخفض (Low Risk)"
            risk_color = 0x50FA7B
        elif risk_score < 60:
            risk_level = "🟡 متوسط (Moderate Risk)"
            risk_color = 0xFFB86C
        else:
            risk_level = "🔴 مرتفع (High Risk)"
            risk_color = 0xFF5555

        risk_reasons_str = "\n".join(risk_reasons) if risk_reasons else "لا توجد مؤشرات خطر"

        badges = []
        if user.public_flags.hypesquad_brilliance:
            badges.append("HypeSquad Brilliance")
        if user.public_flags.early_supporter:
            badges.append("Early Supporter")
        if user.public_flags.verified_bot_developer:
            badges.append("Bot Developer")
        badges_str = ", ".join(badges) if badges else "لا شيء"

        desc = (
            f"**المستهدف:** {user.mention} (`{user.id}`)\n"
            f"**مؤشر الخطورة:** `{risk_score}%` — {risk_level}\n\n"
            f"`──────── التفاصيل ────────`\n"
            f"• **تاريخ إنشاء الحساب:** `{user.created_at.strftime('%Y-%m-%d')}` (`{account_age_days}` يوم)\n"
            f"• **تاريخ الانضمام:** `{user.joined_at.strftime('%Y-%m-%d') if user.joined_at else 'غير معروف'}` (`{joined_age_days}` يوم)\n"
            f"• **السوابق الإدارية:** `{cases_count}` حالة\n"
            f"• **أعلى رول:** {user.top_role.mention}\n"
            f"• **Badges:** `{badges_str}`\n\n"
            f"`──────── مؤشرات الخطر ────────`\n"
            f"{risk_reasons_str}"
        )

        embed = create_neon_embed(
            f"الفحص الأمني | User Security Scan",
            desc,
            color=risk_color
        )
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else "")
        await interaction.followup.send(embed=embed)

    # ─── /remove_timeout ─────────────────────────────────────────────────────────
    @app_commands.command(name="remove_timeout", description="إزالة الكتم المؤقت عن عضو")
    @app_commands.describe(user="العضو المراد رفع الكتم عنه", reason="السبب")
    async def remove_timeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "رفع كتم إداري"
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        try:
            await user.timeout(None, reason=reason)
            case_id = await self._create_case(
                interaction.guild_id, user.id, interaction.user.id, "UNMUTE", reason
            )
            embed = create_success_embed(
                f"رفع الكتم | Remove Timeout — Case #{case_id}",
                f"**العضو:** {user.mention}\n**بواسطة:** {interaction.user.mention}\n**السبب:** {reason}"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"فشل رفع الكتم: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
