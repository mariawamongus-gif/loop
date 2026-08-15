import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_mod, is_admin
from utils.embeds import create_critical_embed, create_warning_embed, create_success_embed, create_neon_embed
from utils.decision_log import log_decision


class QuarantineCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_name_impersonation(self, member_name: str, admin_names: list[str]) -> bool:
        """فحص تطابق أو تشابه الاسم مع أسماء الأدمنية والمشرفين"""
        clean_member = member_name.lower().strip()
        for adm in admin_names:
            clean_adm = adm.lower().strip()
            if len(clean_adm) >= 3:
                if clean_adm == clean_member or clean_adm in clean_member:
                    return True
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        account_age_days = (datetime.utcnow() - member.created_at.replace(tzinfo=None)).days

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = res.scalars().first()
            if not config or not config.protection_enabled:
                return

        # جمع أسماء المالك والأدمنية للفحص
        admin_names = [guild.owner.name] if guild.owner else []
        for m in guild.members:
            if m.guild_permissions.administrator and not m.bot:
                admin_names.append(m.name)
                if m.display_name:
                    admin_names.append(m.display_name)

        admin_names = list(set(admin_names))

        is_impersonator = self._is_name_impersonation(member.name, admin_names) or (
            member.display_name and self._is_name_impersonation(member.display_name, admin_names)
        )
        is_suspicious_age = account_age_days < 3

        if is_impersonator or is_suspicious_age:
            flags = []
            if is_impersonator:
                flags.append("انتحال هوية شخصية قيادية في السيرفر (Impersonation Attack)")
            if is_suspicious_age:
                flags.append(f"حساب حديث الإنشاء جداً ({account_age_days} يوم فقط)")

            flags_str = "\n• ".join(flags)

            # إشعار أمني عالي الأولوية في قناة السجلات
            if config.log_channel_id:
                log_chan = guild.get_channel(config.log_channel_id)
                if log_chan:
                    embed = create_critical_embed(
                        "رادار الحجر الصحي | Quarantine Threat Detected",
                        f"**العضو المشتبه به:** {member.mention} (`{member.id}`)\n"
                        f"**تاريخ إنشاء الحساب:** `{member.created_at.strftime('%Y-%m-%d')}` (`{account_age_days}` يوم)\n\n"
                        f"**المؤشرات المرصودة:**\n• {flags_str}\n\n"
                        f"*التوصية التكتيكية: فحص الحساب يدوياً أو استخدام `/quarantine` لعزله.*"
                    )
                    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else "")
                    try:
                        await log_chan.send(embed=embed)
                    except Exception:
                        pass

            await log_decision(
                guild,
                command="AUTOMATED_QUARANTINE_SCAN",
                check_result=f"مؤشرات الخطر: {', '.join(flags)}",
                execution_step="رصد العضو وإرسال التنبيه الأمني للإدارة",
                outcome="تم تسجيل التهديد بنجاح"
            )

    @app_commands.command(
        name="quarantine",
        description="عزل عضو مشبوه في الحجر الصحي وتقييد صلاحياته فورياً لحين التحقق منه"
    )
    @app_commands.describe(user="العضو المراد عزله", reason="سبب الإحالة للحجر الصحي")
    async def quarantine(self, interaction: discord.Interaction, user: discord.Member, reason: str = "عزل أمني للتحقق من الهوية"):
        if not await is_mod(interaction):
            await interaction.response.send_message("خطأ: يقتصر العزل على المشرفين والقيادة.", ephemeral=True)
            return

        guild = interaction.guild
        # البحث عن رول الحجر الصحي أو إنشاؤه
        quarantine_role = discord.utils.get(guild.roles, name="Quarantined")
        if not quarantine_role:
            try:
                quarantine_role = await guild.create_role(
                    name="Quarantined",
                    color=discord.Color.dark_gray(),
                    permissions=discord.Permissions(send_messages=False, read_messages=True, connect=False),
                    reason="Auto-created Quarantine Role"
                )
            except Exception:
                pass

        if quarantine_role:
            try:
                await user.add_roles(quarantine_role, reason=f"Quarantined by {interaction.user.name}: {reason}")
            except Exception:
                pass

        embed = create_warning_embed(
            "إحالة للحجر الصحي | Member Quarantined",
            f"تم إحالة العضو {user.mention} للحجر الصحي التكتيكي بنجاح.\n"
            f"**السبب:** {reason}\n"
            f"**المشرف المنفّذ:** {interaction.user.mention}"
        )
        await interaction.response.send_message(embed=embed)

        await log_decision(
            guild,
            command=f"/quarantine user={user.id}",
            check_result="صلاحيات الإشراف مؤكدة",
            execution_step="إسناد رول الحجر الصحي وتقييد الأذونات",
            outcome="تم عزل العضو بنجاح"
        )

    @app_commands.command(
        name="unquarantine",
        description="رفع الحجر الصحي عن عضو واستعادة صلاحياته الطبيعية"
    )
    @app_commands.describe(user="العضو المراد رفع العزل عنه")
    async def unquarantine(self, interaction: discord.Interaction, user: discord.Member):
        if not await is_mod(interaction):
            await interaction.response.send_message("خطأ: لا تملك الصلاحيات المطلوبة.", ephemeral=True)
            return

        guild = interaction.guild
        quarantine_role = discord.utils.get(guild.roles, name="Quarantined")
        if quarantine_role and quarantine_role in user.roles:
            try:
                await user.remove_roles(quarantine_role, reason=f"Unquarantined by {interaction.user.name}")
            except Exception:
                pass

        embed = create_success_embed(
            "رفع الحجر الصحي | Quarantine Lifted",
            f"تم رفع الحجر الصحي عن العضو {user.mention} واستعادة وضعه الطبيعي."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuarantineCog(bot))
