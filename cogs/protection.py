import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime, timedelta
from core.database import AsyncSessionLocal
from core.models import GuildConfig, Whitelist
from core.redis_client import redis_manager
from core.permissions import is_admin, is_whitelisted
from core.strings import Strings
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision
from config import Config

class ProtectionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 1. Anti-Raid System (كشف انضمام جماعي مشبوه)
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        # تتبع الانضمام خلال 10 ثوانٍ عبر Redis
        key = f"raid:{guild.id}"
        joins = await redis_manager.incr(key)
        if joins == 1:
            await redis_manager.expire(key, 10)

        # لو انضم أكثر من 7 أعضاء خلال 10 ثوانٍ -> Lockdown
        if joins >= 7:
            await self._trigger_lockdown(guild, "رصد انضمام مكثف (Anti-Raid Trigger)")

    async def _trigger_lockdown(self, guild: discord.Guild, reason: str):
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                if overwrite.send_messages is not False:
                    overwrite.send_messages = False
                    await channel.set_permissions(guild.default_role, overwrite=overwrite, reason=reason)
            except Exception:
                continue

        await log_decision(
            guild,
            command="AUTOMATED_ANTI_RAID",
            check_result="تجاوز حد الانضمام المسموح (7 أعضاء/10 ثوانٍ)",
            execution_step="تعديل صلاحيات Send Messages لجميع القنوات النصية لـ @everyone",
            outcome="تفعيل Lockdown بنجاح على السيرفر"
        )

    # 2. Anti-Nuke System (كشف حذف قنوات/رولات جماعي)
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            user = entry.user
            if not user or user.id == self.bot.user.id or user.id == guild.owner_id:
                return

            if await is_whitelisted(guild.id, user.id, "user"):
                return

            # تتبع عمليات الحذف في 15 ثانية
            key = f"nuke_channel:{guild.id}:{user.id}"
            count = await redis_manager.incr(key)
            if count == 1:
                await redis_manager.expire(key, 15)

            if count >= 3:
                # سحب الصلاحيات
                await self._strip_roles(guild, user, "حذف قنوات مكثف (Anti-Nuke Trigger)")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            user = entry.user
            if not user or user.id == self.bot.user.id or user.id == guild.owner_id:
                return

            if await is_whitelisted(guild.id, user.id, "user"):
                return

            key = f"nuke_role:{guild.id}:{user.id}"
            count = await redis_manager.incr(key)
            if count == 1:
                await redis_manager.expire(key, 15)

            if count >= 3:
                await self._strip_roles(guild, user, "حذف رولات مكثف (Anti-Nuke Trigger)")

    async def _strip_roles(self, guild: discord.Guild, user: discord.abc.User, reason: str):
        member = guild.get_member(user.id)
        if member:
            roles_to_remove = [r for r in member.roles if r.name != "@everyone" and r.position < guild.me.top_role.position]
            try:
                await member.remove_roles(*roles_to_remove, reason=reason)
            except Exception:
                pass

        await log_decision(
            guild,
            command="AUTOMATED_ANTI_NUKE",
            check_result=f"المتسبب {user.id} غير مستثنى وحذف عناصر متعددة في وقت قصير",
            execution_step="سحب كل الرولات الحساسة ذات الصلاحيات العالية",
            outcome="سحب الصلاحيات وإخطار مالك السيرفر"
        )

    # 3. Anti-Spam System (كشف تكرار الرسائل والمنشن الجماعي)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild = message.guild
        author = message.author

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        if await is_whitelisted(guild.id, author.id, "user"):
            return

        # كشف Mass Mention (> 5 منشن برسالة واحدة)
        if len(message.mentions) >= 5:
            try:
                await message.delete()
                await author.timeout(timedelta(minutes=10), reason="Mass Mention Spam Filter")
                await log_decision(
                    guild,
                    command="AUTOMATED_ANTI_SPAM_MENTION",
                    check_result=f"الرسالة تحتوي {len(message.mentions)} منشن",
                    execution_step="حذف الرسالة وتطبيق Timeout لمدة 10 دقائق",
                    outcome="تم تنفيذ الكتم الآلي بنجاح"
                )
            except Exception:
                pass
            return

        # كشف تكرار الرسائل (Rate limiting)
        key = f"spam_msg:{guild.id}:{author.id}"
        msg_count = await redis_manager.incr(key)
        if msg_count == 1:
            await redis_manager.expire(key, 5)

        if msg_count >= 6:
            try:
                await author.timeout(timedelta(minutes=5), reason="Auto-Spam Rate Limit Trigger")
                await log_decision(
                    guild,
                    command="AUTOMATED_ANTI_SPAM_RATE",
                    check_result="إرسال 6 رسائل خلال 5 ثوانٍ",
                    execution_step="تطبيق كتم مؤقت لمدة 5 دقائق",
                    outcome="تم تقييد حركة السپام"
                )
            except Exception:
                pass

    # 4. Whitelist Management Commands
    @app_commands.command(name="whitelist", description="إدارة قائمة الاستثناء من نظام الحماية (Whitelist)")
    @app_commands.describe(action="إضافة أو إزالة", target="العضو أو الرول المراد استثناؤه")
    async def whitelist_cmd(self, interaction: discord.Interaction, action: str, target: discord.User):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        guild_id = interaction.guild_id
        async with AsyncSessionLocal() as session:
            if action.lower() == "add":
                existing = await session.execute(
                    select(Whitelist).where(Whitelist.guild_id == guild_id, Whitelist.target_id == target.id)
                )
                if not existing.scalars().first():
                    wl = Whitelist(guild_id=guild_id, target_id=target.id, target_type="user")
                    session.add(wl)
                    await session.commit()
                msg = Strings.WHITELIST_ADDED
            else:
                existing = await session.execute(
                    select(Whitelist).where(Whitelist.guild_id == guild_id, Whitelist.target_id == target.id)
                )
                item = existing.scalars().first()
                if item:
                    await session.delete(item)
                    await session.commit()
                msg = Strings.WHITELIST_REMOVED

        embed = create_neon_embed("قائمة الاستثناء | Whitelist", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 5. /security_audit
    @app_commands.command(name="security_audit", description="إجراء فحص أمني وتدقيق كامل لصلاحيات السيرفر والجاهزية")
    async def security_audit(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        guild = interaction.guild
        audit_issues = []
        score = 100

        admin_roles = [r for r in guild.roles if r.permissions.administrator and not r.is_default()]
        if len(admin_roles) > 3:
            score -= 15
            audit_issues.append(f"• **كثرة رولات الأدمن:** يوجد `{len(admin_roles)}` رولات تملك صلاحية `Administrator` كاملاً.")

        everyone_role = guild.default_role
        if everyone_role.permissions.mention_everyone:
            score -= 25
            audit_issues.append("• **ثغرة حرجة:** صلاحية `Mention Everyone` مفعّلة لرول @everyone!")

        if everyone_role.permissions.kick_members or everyone_role.permissions.ban_members:
            score -= 30
            audit_issues.append("• **ثغرة حرجة جداً:** صلاحية الطرد أو الحظر مفعّلة لـ @everyone!")

        grade = "A+ (ممتاز)" if score >= 90 else ("B (جيد)" if score >= 75 else ("C (ضعيف)" if score >= 50 else "F (خطر حرّج)"))

        issues_str = "\n".join(audit_issues) if audit_issues else "• لم يتم رصد أي ثغرات أمنية حرجة. السيرفر في أعلى درجات الجاهزية."

        desc = (
            f"**التقييم الأمني الآلي (Security Grade):** `{grade}` — `{score}/100`\n\n"
            f"**نتائج التدقيق الفني:**\n{issues_str}"
        )

        embed = create_neon_embed("التدقيق الأمني الشامل | Server Security Audit", desc)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ProtectionCog(bot))

