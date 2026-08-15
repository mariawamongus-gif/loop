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
from utils.embeds import (
    create_neon_embed, create_success_embed,
    create_error_embed, create_warning_embed, create_critical_embed
)
from utils.decision_log import log_decision
from config import Config


class ProtectionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_raid_threshold(self, guild_id: int) -> int:
        """يجلب حد الـ Anti-Raid من الـ DB أو يستخدم الافتراضي 7."""
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == guild_id)
                )
                config = res.scalars().first()
                if config and hasattr(config, "raid_threshold") and config.raid_threshold:
                    return config.raid_threshold
        except Exception:
            pass
        return 7

    # ─── 1. Anti-Raid ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild.id)
            )
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        key = f"raid:{guild.id}"
        joins = await redis_manager.incr(key)
        if joins == 1:
            await redis_manager.expire(key, 10)

        threshold = await self._get_raid_threshold(guild.id)
        if joins >= threshold:
            await self._trigger_lockdown(guild, f"رصد انضمام مكثف ({joins} عضو/10ث) — Anti-Raid Trigger")

    async def _trigger_lockdown(self, guild: discord.Guild, reason: str):
        locked = 0
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                if overwrite.send_messages is not False:
                    overwrite.send_messages = False
                    await channel.set_permissions(
                        guild.default_role, overwrite=overwrite, reason=reason
                    )
                    locked += 1
            except Exception:
                continue

        await log_decision(
            guild,
            command="AUTOMATED_ANTI_RAID",
            check_result=f"تجاوز حد الانضمام المسموح",
            execution_step=f"قفل {locked} قناة نصية — @everyone: send_messages = False",
            outcome="تفعيل Lockdown بنجاح"
        )

        # إشعار في قناة اللوج
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == guild.id)
                )
                config = res.scalars().first()
                if config and config.log_channel_id:
                    log_chan = guild.get_channel(config.log_channel_id)
                    if log_chan:
                        embed = create_critical_embed(
                            "🚨 تفعيل Lockdown — Anti-Raid",
                            f"**تم قفل `{locked}` قناة نصية** بسبب:\n`{reason}`\n\n"
                            f"استخدم `/unlock_server` لفك القفل بعد تأمين الوضع."
                        )
                        await log_chan.send("@here", embed=embed)
        except Exception:
            pass

    # ─── 2. Anti-Nuke (Channel Delete) ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild.id)
            )
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            user = entry.user
            if not user or user.id == self.bot.user.id or user.id == guild.owner_id:
                return
            if await is_whitelisted(guild.id, user.id, "user"):
                return

            key = f"nuke_channel:{guild.id}:{user.id}"
            count = await redis_manager.incr(key)
            if count == 1:
                await redis_manager.expire(key, 15)

            if count >= 3:
                await self._strip_roles(
                    guild, user, f"حذف {count} قنوات في 15ث — Anti-Nuke Trigger"
                )

    # ─── 3. Anti-Nuke (Role Delete) ───────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild.id)
            )
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
                await self._strip_roles(
                    guild, user, f"حذف {count} رولات في 15ث — Anti-Nuke Trigger"
                )

    async def _strip_roles(self, guild: discord.Guild, user: discord.abc.User, reason: str):
        member = guild.get_member(user.id)
        stripped = []
        if member:
            roles_to_remove = [
                r for r in member.roles
                if r.name != "@everyone" and r.position < guild.me.top_role.position
            ]
            try:
                await member.remove_roles(*roles_to_remove, reason=reason)
                stripped = roles_to_remove
            except Exception:
                pass

        await log_decision(
            guild,
            command="AUTOMATED_ANTI_NUKE",
            check_result=f"المتسبب {user.id} حذف عناصر متعددة",
            execution_step=f"سحب {len(stripped)} رول",
            outcome="سحب الصلاحيات بنجاح"
        )

        # إشعار في قناة اللوج
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == guild.id)
                )
                config = res.scalars().first()
                if config and config.log_channel_id:
                    log_chan = guild.get_channel(config.log_channel_id)
                    if log_chan:
                        embed = create_critical_embed(
                            "🚨 تدخل Anti-Nuke — سحب صلاحيات",
                            f"**المتسبب:** {member.mention if member else user.id}\n"
                            f"**السبب:** `{reason}`\n"
                            f"**الرولات المسحوبة:** `{len(stripped)}`"
                        )
                        await log_chan.send(embed=embed)
        except Exception:
            pass

    # ─── 4. Anti-Spam ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # تجاهل قنوات التذاكر تماماً لتجنب التضارب مع TicketsCog
        if message.channel.name.startswith("ticket-"):
            return

        guild = message.guild
        author = message.author

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild.id)
            )
            config = result.scalars().first()
            if not config or not config.protection_enabled:
                return

        if await is_whitelisted(guild.id, author.id, "user"):
            return

        # Mass Mention (>= 5 منشن)
        if len(message.mentions) >= 5:
            try:
                await message.delete()
                await author.timeout(timedelta(minutes=10), reason="Mass Mention Spam Filter")
                await log_decision(
                    guild,
                    command="AUTOMATED_ANTI_SPAM_MENTION",
                    check_result=f"{len(message.mentions)} منشن برسالة واحدة",
                    execution_step="حذف الرسالة + Timeout 10 دقائق",
                    outcome="تم الكتم الآلي"
                )
                # إشعار في اللوج
                async with AsyncSessionLocal() as session:
                    res = await session.execute(
                        select(GuildConfig).where(GuildConfig.guild_id == guild.id)
                    )
                    config = res.scalars().first()
                    if config and config.log_channel_id:
                        log_chan = guild.get_channel(config.log_channel_id)
                        if log_chan:
                            embed = create_warning_embed(
                                "Anti-Spam — Mass Mention",
                                f"**العضو:** {author.mention}\n"
                                f"**المنشنات:** `{len(message.mentions)}`\n"
                                f"**الإجراء:** Timeout 10 دقائق"
                            )
                            await log_chan.send(embed=embed)
            except Exception:
                pass
            return

        # Rate Limiting (6 رسائل في 5 ثوانٍ)
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
                    check_result=f"إرسال {msg_count} رسائل خلال 5 ثوانٍ",
                    execution_step="Timeout 5 دقائق",
                    outcome="تقييد السبام"
                )
            except Exception:
                pass

    # ─── 5. /whitelist ────────────────────────────────────────────────────────────
    @app_commands.command(name="whitelist", description="إدارة قائمة الاستثناء من نظام الحماية")
    @app_commands.describe(action="add أو remove", target="العضو المراد استثناؤه")
    async def whitelist_cmd(
        self, interaction: discord.Interaction, action: str, target: discord.User
    ):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        guild_id = interaction.guild_id
        async with AsyncSessionLocal() as session:
            if action.lower() == "add":
                existing = await session.execute(
                    select(Whitelist).where(
                        Whitelist.guild_id == guild_id,
                        Whitelist.target_id == target.id
                    )
                )
                if not existing.scalars().first():
                    wl = Whitelist(guild_id=guild_id, target_id=target.id, target_type="user")
                    session.add(wl)
                    await session.commit()
                msg = f"تم إضافة {target.mention} لقائمة الاستثناء."
                embed = create_success_embed("Whitelist — إضافة", msg)
            else:
                existing = await session.execute(
                    select(Whitelist).where(
                        Whitelist.guild_id == guild_id,
                        Whitelist.target_id == target.id
                    )
                )
                item = existing.scalars().first()
                if item:
                    await session.delete(item)
                    await session.commit()
                msg = f"تم إزالة {target.mention} من قائمة الاستثناء."
                embed = create_warning_embed("Whitelist — إزالة", msg)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── 6. /security_audit ───────────────────────────────────────────────────────
    @app_commands.command(name="security_audit", description="تدقيق أمني شامل لصلاحيات السيرفر")
    async def security_audit(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        guild = interaction.guild
        audit_issues = []
        warnings = []
        score = 100

        # فحص رولات الأدمن
        admin_roles = [r for r in guild.roles if r.permissions.administrator and not r.is_default()]
        if len(admin_roles) > 3:
            score -= 15
            audit_issues.append(f"🔴 **كثرة رولات الأدمن:** `{len(admin_roles)}` رولات تملك Administrator.")

        # فحص @everyone
        everyone = guild.default_role
        if everyone.permissions.mention_everyone:
            score -= 25
            audit_issues.append("🔴 **ثغرة حرجة:** `Mention Everyone` مفعّل لـ @everyone!")
        if everyone.permissions.kick_members:
            score -= 30
            audit_issues.append("🔴 **ثغرة خطيرة جداً:** `Kick Members` مفعّل لـ @everyone!")
        if everyone.permissions.ban_members:
            score -= 35
            audit_issues.append("🔴 **ثغرة قاتلة:** `Ban Members` مفعّل لـ @everyone!")
        if everyone.permissions.manage_channels:
            score -= 20
            audit_issues.append("🟡 `Manage Channels` مفعّل لـ @everyone.")
        if everyone.permissions.manage_messages:
            score -= 10
            warnings.append("🟡 `Manage Messages` مفعّل لـ @everyone.")

        # فحص Bots بصلاحيات عالية
        suspicious_bots = []
        for member in guild.members:
            if member.bot and member.guild_permissions.administrator:
                suspicious_bots.append(member.name)
        if suspicious_bots:
            score -= 10
            warnings.append(f"🟡 بوتات تملك Administrator: `{', '.join(suspicious_bots[:5])}`")

        score = max(0, score)
        if score >= 90:
            grade, grade_color = "A+ (ممتاز)", 0x50FA7B
        elif score >= 75:
            grade, grade_color = "B (جيد)", 0x00F5FF
        elif score >= 50:
            grade, grade_color = "C (ضعيف)", 0xFFB86C
        else:
            grade, grade_color = "F (خطر حرّج)", 0xFF0000

        all_issues = audit_issues + warnings
        issues_str = "\n".join(all_issues) if all_issues else "✅ لم يتم رصد أي ثغرات حرجة."

        desc = (
            f"**التقييم الأمني:** `{grade}` — `{score}/100`\n\n"
            f"**عدد الأعضاء:** `{guild.member_count}` | **الرولات:** `{len(guild.roles)}`\n"
            f"**رولات الأدمن:** `{len(admin_roles)}` | **البوتات:** `{sum(1 for m in guild.members if m.bot)}`\n\n"
            f"`──────── نتائج التدقيق ────────`\n"
            f"{issues_str}"
        )

        embed = create_neon_embed("التدقيق الأمني الشامل | Security Audit", desc, color=grade_color)
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
        await interaction.response.send_message(embed=embed)

    # ─── 7. /unlock_server ────────────────────────────────────────────────────────
    @app_commands.command(name="unlock_server", description="فك قفل السيرفر بعد Anti-Raid Lockdown (أدمن فقط)")
    async def unlock_server(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        unlocked = 0

        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                if overwrite.send_messages is False:
                    overwrite.send_messages = None  # إعادة للافتراضي
                    await channel.set_permissions(
                        guild.default_role, overwrite=overwrite,
                        reason=f"فك قفل بواسطة {interaction.user.name}"
                    )
                    unlocked += 1
            except Exception:
                continue

        embed = create_success_embed(
            "فك قفل السيرفر | Server Unlock",
            f"تم فك قفل `{unlocked}` قناة نصية بنجاح.\n"
            f"**بواسطة:** {interaction.user.mention}"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        await log_decision(
            guild,
            command="/unlock_server",
            check_result="صلاحيات الأدمن مؤكدة",
            execution_step=f"إعادة صلاحية send_messages لـ {unlocked} قناة",
            outcome="تم فك الـ Lockdown بنجاح"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ProtectionCog(bot))
