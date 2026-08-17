import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy.future import select
from sqlalchemy import update
import json
import asyncio
import re
import aiohttp
from datetime import datetime
from typing import Optional, List
from core.database import AsyncSessionLocal, engine
from core.models import SupportTicket, TicketWitness, GuildConfig, ModerationCase
from ai.fallback_manager import ai_manager
from ai.multimodal_analyzer import analyze_evidence_multimodal
from core.strings import Strings
from utils.embeds import create_neon_embed, create_success_embed, create_error_embed, create_warning_embed
from utils.decision_log import log_decision
from utils.smart_split import smart_split

# ─── 1. لوحة تصويت الشهود التفاعلية ──────────────────────────────────────────
class WitnessVoteView(discord.ui.View):
    def __init__(self, ticket_id: int, target_user_id: int, creator_id: int):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.target_user_id = target_user_id
        self.creator_id = creator_id

    @discord.ui.button(label="أشهد على صحة الواقعة (شهادة معتمدة)", style=discord.ButtonStyle.success, emoji="✋")
    async def add_witness(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id == self.creator_id:
            await interaction.response.send_message("❌ لا يمكنك الشهادة على تذكرتك الخاصة كشاهد محايد.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            # التحقق هل شهد العضو مسبقاً
            res_witness = await session.execute(
                select(TicketWitness).where(
                    TicketWitness.ticket_id == self.ticket_id,
                    TicketWitness.witness_id == user.id
                )
            )
            if res_witness.scalars().first():
                await interaction.response.send_message("⚠️ لقد قمت بتسجيل شهادتك مسبقاً على هذه التذكرة.", ephemeral=True)
                return

            new_witness = TicketWitness(
                ticket_id=self.ticket_id,
                witness_id=user.id,
                approved=True,
                voted_at=datetime.utcnow()
            )
            session.add(new_witness)
            await session.commit()

            # حساب عدد الشهود الحالي
            res_all = await session.execute(
                select(TicketWitness).where(
                    TicketWitness.ticket_id == self.ticket_id,
                    TicketWitness.approved == True
                )
            )
            witness_count = len(res_all.scalars().all())

            # إذا اكتمل شاهدان، يتم اعتماد الدليل
            if witness_count >= 2:
                t = await session.get(SupportTicket, self.ticket_id)
                if t:
                    t.evidence_type = "WITNESS"
                    t.evidence_status = "VERIFIED"
                    t.evidence_score = 100
                    t.evidence_analysis = f"تم توثيق الواقعة واعتمادها رسميًا بشهادة {witness_count} شهود محايدين."
                    await session.commit()

                for item in self.children:
                    item.disabled = True

                embed_verified = create_success_embed(
                    "تم اعتماد شهادة الشهود بنجاح | Evidence Verified",
                    f"✅ **اكتمل النصاب المطلوب للشهود ({witness_count}/2)!**\n"
                    f"• تم توثيق الواقعة رسمياً، وأصبحت صلاحية الإجراءات الإدارية الطارئة مفعلة ومتاحة للإدارة."
                )
                await interaction.response.edit_message(embed=embed_verified, view=self)
                return

            await interaction.response.send_message(
                f"✅ تم توثيق شهادتك بنجاح بواسطة {user.mention}. (عدد الشهود الحالي: **{witness_count}/2**)",
                ephemeral=False
            )


# ─── 2. لوحة الإجراءات الإدارية الطارئة داخل التذكرة ─────────────────────────
class EmergencyTicketActionView(discord.ui.View):
    def __init__(self, ticket_id: int, target_user_id: int, evidence_url: str):
        super().__init__(timeout=120)
        self.ticket_id = ticket_id
        self.target_user_id = target_user_id
        self.evidence_url = evidence_url

    async def _execute_mod(self, interaction: discord.Interaction, action: str, reason: str):
        guild = interaction.guild
        for item in self.children:
            item.disabled = True

        try:
            case_id = 0
            if action == "BAN":
                await guild.ban(discord.Object(id=self.target_user_id), reason=reason)
            elif action == "KICK":
                member = guild.get_member(self.target_user_id)
                if member:
                    await member.kick(reason=reason)
                else:
                    await interaction.response.edit_message(content="❌ تعذر العثور على العضو في السيرفر لطرده.", view=self)
                    return
            elif action == "TIMEOUT":
                member = guild.get_member(self.target_user_id)
                if member:
                    from datetime import timedelta
                    await member.timeout(timedelta(minutes=60), reason=reason)
                else:
                    await interaction.response.edit_message(content="❌ تعذر العثور على العضو لكتمه.", view=self)
                    return

            async with AsyncSessionLocal() as session:
                case = ModerationCase(
                    guild_id=guild.id,
                    user_id=self.target_user_id,
                    mod_id=interaction.user.id,
                    action=action,
                    reason=f"{reason} (دليل معتمد في تذكرة #{self.ticket_id})",
                    created_at=datetime.utcnow()
                )
                session.add(case)
                await session.commit()
                await session.refresh(case)
                case_id = case.case_id

            action_names = {"BAN": "حظر نهائي", "KICK": "طرد", "TIMEOUT": "كتم 60 دقيقة"}
            embed = create_success_embed(
                f"تم تنفيذ الإجراء التأديبي | Case #{case_id}",
                f"✅ تم تنفيذ **{action_names.get(action, action)}** بحق <@{self.target_user_id}> بنجاح.\n"
                f"• **المشرف المنفذ:** {interaction.user.mention}\n"
                f"• **رابط الدليل المعتمد:** [عرض الدليل]({self.evidence_url if self.evidence_url else 'https://discord.com'})\n"
                f"• **رقم القضية الإدارية:** `Case #{case_id}`"
            )
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            await interaction.response.edit_message(content=f"❌ تعذر تنفيذ الإجراء بسبب قيود الصلاحيات أو الرتب: `{e}`", view=self)

    @discord.ui.button(label="حظر نهائي (Ban)", style=discord.ButtonStyle.danger, emoji="🔨")
    async def ban_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._execute_mod(interaction, "BAN", "مخالفة سلوكية وشتائم مثبتة بالدليل التلقائي")

    @discord.ui.button(label="طرد العضو (Kick)", style=discord.ButtonStyle.danger, emoji="👢")
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._execute_mod(interaction, "KICK", "مخالفة قوانين السيرفر مثبتة بالدليل")

    @discord.ui.button(label="كتم 60 دقيقة (Timeout)", style=discord.ButtonStyle.primary, emoji="🔇")
    async def mute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._execute_mod(interaction, "TIMEOUT", "كتم مؤقت لمخالفة الآداب العامة")


# ─── 3. لوحة تحكم التذكرة التفاعلية المستمرة ──────────────────────────────────
class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="تحويل لمشرف بشري",
        emoji="👤",
        style=discord.ButtonStyle.primary,
        custom_id="neon_ticket_switch_btn",
        row=0
    )
    async def switch_to_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SupportTicket).where(SupportTicket.ticket_id == self.ticket_id)
            )
            ticket = result.scalars().first()
            if ticket:
                ticket.status = "ESCALATED"
                ticket.severity = "SERIOUS"
                await session.commit()

            cfg = await session.get(GuildConfig, interaction.guild_id)
            staff_mention = "@here"
            if cfg and cfg.mod_role_id:
                mr = interaction.guild.get_role(cfg.mod_role_id)
                if mr:
                    staff_mention = mr.mention
            elif cfg and cfg.admin_role_id:
                ar = interaction.guild.get_role(cfg.admin_role_id)
                if ar:
                    staff_mention = ar.mention

        embed = create_warning_embed(
            "تحويل التذكرة للدعم البشري واستدعاء المشرفين",
            f"🔔 {interaction.user.mention} **تم استدعاء طاقم الإشراف بنجاح:** {staff_mention}\n\n"
            f"> تم إيقاف ردود الذكاء الاصطناعي الآلية، وسيتدخل أحد المشرفين لمساعدتك مباشرة."
        )
        await interaction.response.send_message(
            content=staff_mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True)
        )

    @discord.ui.button(
        label="طلب توثيق شهود",
        emoji="👥",
        style=discord.ButtonStyle.secondary,
        custom_id="neon_ticket_witness_btn",
        row=0
    )
    async def request_witness(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with AsyncSessionLocal() as session:
            ticket = await session.get(SupportTicket, self.ticket_id)
            creator_id = ticket.user_id if ticket else interaction.user.id

        embed = create_neon_embed(
            "طلب توثيق شهود على الواقعة | Witness System",
            f"📌 **مطلوب شهادة شاهدين اثنين (2) لتأكيد الواقعة:**\n\n"
            f"• **مُنشئ التذكرة:** <@{creator_id}>\n"
            f"• يُرجى من أي عضوين محايدين شهدا الواقعة الضغط على الزر أدناه لتوثيق الشهادة رسمياً.",
            color=0xF1C40F
        )
        view = WitnessVoteView(self.ticket_id, creator_id, creator_id)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.ui.button(
        label="إجراء إداري طارئ",
        emoji="🚨",
        style=discord.ButtonStyle.danger,
        custom_id="neon_ticket_mod_btn",
        row=0
    )
    async def emergency_mod(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.ban_members or interaction.user.guild_permissions.kick_members):
            await interaction.response.send_message(
                "❌ يقتصر استخدام هذا الزر على طاقم الإدارة والإشراف فقط.", ephemeral=True
            )
            return

        async with AsyncSessionLocal() as session:
            ticket = await session.get(SupportTicket, self.ticket_id)
            if not ticket:
                await interaction.response.send_message("❌ تعذر جلب بيانات التذكرة.", ephemeral=True)
                return

            # بروتوكول فحص الأدلة الإلزامي (Evidence Gate)
            is_evidence_valid = (ticket.evidence_status == "VERIFIED")
            if not is_evidence_valid:
                embed_gate = create_warning_embed(
                    "بروتوكول الأدلة الإلزامي | Evidence Required",
                    "⚠️ **لا يمكن تنفيذ أي إجراء إداري تأديبي داخل التذكرة قبل توفر دليل معتمد واحد على الأقل:**\n\n"
                    "1. 📸 **صورة/شات:** أرسل صورة الشات أو لقطة الشاشة ليقوم **Gemini 1.5 Flash Vision** بفحصها آلياً.\n"
                    "2. 🎙️ **مقطع صوتي:** أرسل التسجيل الصوتي (`.mp3`, `.ogg`, `.wav`, `.m4a`) ليحلل الذكاء الاصطناعي الشتائم والتعديات الصوتية.\n"
                    "3. 👥 **نظام الشهود:** اضغط زر `طلب توثيق شهود` لتوثيق شهادة شاهدين محايدين."
                )
                await interaction.response.send_message(embed=embed_gate, ephemeral=True)
                return

            # الدليل معتمد: فتح قائمة التنفيذ الإداري
            embed_ready = create_neon_embed(
                "لوحة العقوبات التأديبية المعتمدة | Verified Mod Actions",
                f"✅ **الدليل معتمد رسمياً ({ticket.evidence_type}) بنسبة ثقة {ticket.evidence_score}%!**\n\n"
                f"• **المستخدم صاحب التذكرة:** <@{ticket.user_id}>\n"
                f"• **تفاصيل الدليل:** {ticket.evidence_analysis or 'تم الفحص والتأكيد بنجاح.'}\n\n"
                f"اختر الإجراء التأديبي المطلوب تطبيقه فوراً:",
                color=0xE74C3C
            )
            view = EmergencyTicketActionView(self.ticket_id, ticket.user_id, ticket.evidence_url or "")
            await interaction.response.send_message(embed=embed_ready, view=view, ephemeral=True)

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="neon_ticket_close_btn",
        row=1
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_closing = create_neon_embed(
            "جاري إغلاق التذكرة",
            f"سيتم إغلاق التذكرة **#{self.ticket_id:04d}** وأرشفة المحادثة خلال **5 ثوانٍ**...",
            color=0xFF5555
        )
        await interaction.response.send_message(embed=embed_closing)

        ticket_id_fmt = f"{self.ticket_id:04d}"
        async with AsyncSessionLocal() as session:
            ticket = await session.get(SupportTicket, self.ticket_id)
            if ticket:
                ticket.status = "CLOSED"
                ticket.closed_at = datetime.utcnow()

            res_config = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            config = res_config.scalars().first()
            await session.commit()

        # توليد أرشيف المحادثة HTML
        try:
            from utils.transcript_exporter import generate_html_transcript
            filepath = await generate_html_transcript(interaction.channel, ticket_id_fmt)

            if config and config.logging_enabled and config.log_channel_id:
                log_chan = interaction.guild.get_channel(config.log_channel_id)
                if log_chan:
                    file = discord.File(filepath, filename=f"transcript_ticket_{ticket_id_fmt}.html")
                    embed_log = create_success_embed(
                        f"أرشيف تذكرة مغلقة | Ticket #{ticket_id_fmt}",
                        f"أُغلقت التذكرة بواسطة {interaction.user.mention}.\n"
                        f"📎 سجل المحادثة HTML مرفق أدناه."
                    )
                    await log_chan.send(embed=embed_log, file=file)
        except Exception:
            pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"تم إغلاق التذكرة #{ticket_id_fmt}")
        except Exception:
            pass


# ─── 4. زر فتح تذكرة جديد ──────────────────────────────────────────────────────
_opening_tickets_lock = asyncio.Lock()
_recently_opened = set()


class OpenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="فتح تذكرة دعم",
        emoji="🎫",
        style=discord.ButtonStyle.danger,
        custom_id="neon_open_ticket_btn"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        lock_key = (guild.id, user.id)
        if lock_key in _recently_opened:
            await interaction.response.send_message("جاري إنشاء تذكرتك بالفعل، الرجاء الانتظار...", ephemeral=True)
            return

        async with _opening_tickets_lock:
            if lock_key in _recently_opened:
                await interaction.response.send_message("جاري إنشاء تذكرتك بالفعل، الرجاء الانتظار...", ephemeral=True)
                return
            _recently_opened.add(lock_key)

        try:
            async with AsyncSessionLocal() as session:
                existing = await session.execute(
                    select(SupportTicket).where(
                        SupportTicket.guild_id == guild.id,
                        SupportTicket.user_id == user.id,
                        SupportTicket.status.in_(["OPEN", "ESCALATED"])
                    )
                )
                existing_ticket = existing.scalars().first()

                if existing_ticket:
                    chan = guild.get_channel(existing_ticket.channel_id)
                    if chan is not None:
                        await interaction.response.send_message(
                            f"⚠️ لديك تذكرة مفتوحة بالفعل في الروم: {chan.mention}. أغلق التذكرة الحالية قبل فتح واحدة جديدة.",
                            ephemeral=True
                        )
                        return
                    else:
                        existing_ticket.status = "CLOSED"
                        existing_ticket.closed_at = datetime.utcnow()
                        await session.commit()

                ticket = SupportTicket(
                    guild_id=guild.id,
                    channel_id=0,
                    user_id=user.id,
                    status="OPEN",
                    evidence_status="NONE",
                    evidence_type="NONE"
                )
                session.add(ticket)
                await session.commit()
                await session.refresh(ticket)

                ticket_id = ticket.ticket_id
                ticket_id_formatted = f"{ticket_id:04d}"

                result_config = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == guild.id)
                )
                config = result_config.scalars().first()

            category = None
            if config and config.ticket_category_id:
                category = guild.get_channel(config.ticket_category_id)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
            }

            if config and config.admin_role_id:
                admin_role = guild.get_role(config.admin_role_id)
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if config and config.mod_role_id:
                mod_role = guild.get_role(config.mod_role_id)
                if mod_role:
                    overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{ticket_id_formatted}",
                category=category,
                overwrites=overwrites,
                topic=f"تذكرة #{ticket_id_formatted} | {user.name} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
            )

            async with AsyncSessionLocal() as session:
                t = await session.get(SupportTicket, ticket_id)
                if t:
                    t.channel_id = ticket_channel.id
                    await session.commit()

            embed = create_neon_embed(
                title=f"🎫 تذكرة دعم #{ticket_id_formatted}",
                description=(
                    f"مرحباً {user.mention} 👋\n\n"
                    f"`──────── بروتوكول الأدلة والدعم ────────`\n"
                    f"**1.** اشرح استفسارك أو مشكلتك بالتفصيل.\n"
                    f"**2.** 📸 **الصور والاسكرينات:** ارفع صورة المخالفة ليحللها **Gemini 1.5 Flash Vision** فوراً.\n"
                    f"**3.** 🎙️ **التسجيلات الصوتية:** ارفع المقطع الصوتي لكشف الشتائم والتعديات اللفظية.\n"
                    f"**4.** 👥 **الشهود:** يمكنك طلب توثيق شاهدين اثنين كإثبات معتمد.\n"
                    f"**5.** اضغط **تحويل لمشرف** لطلب تدخل الإدارة فوراً.\n\n"
                    f"`──────── معلومات التذكرة ────────`\n"
                    f"• **الرقم:** `#{ticket_id_formatted}` | **الحالة:** 🟢 مفتوحة\n"
                    f"• **حالة الدليل:** ⏳ بانتظار إرفاق صورة/صوت أو شهود"
                ),
                color=0x5865F2
            )
            embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else "")
            embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)

            control_view = TicketControlView(ticket_id)
            await ticket_channel.send(content=user.mention, embed=embed, view=control_view)
            await interaction.response.send_message(
                f"✅ تم فتح تذكرتك: {ticket_channel.mention}", ephemeral=True
            )
        finally:
            _recently_opened.discard(lock_key)


# ─── 5. الـ Cog الرئيسي ─────────────────────────────────────────────────────────
class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @tasks.loop(hours=6)
    async def cleanup_task(self):
        await self.bot.wait_until_ready()
        await self._cleanup_deleted_tickets()

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    async def _cleanup_deleted_tickets(self):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SupportTicket).where(SupportTicket.status.in_(["OPEN", "ESCALATED"]))
                )
                tickets = result.scalars().all()
                closed_count = 0
                for ticket in tickets:
                    guild = self.bot.get_guild(ticket.guild_id)
                    if not guild:
                        ticket.status = "CLOSED"
                        ticket.closed_at = datetime.utcnow()
                        closed_count += 1
                        continue

                    channel = guild.get_channel(ticket.channel_id)
                    if channel is None:
                        ticket.status = "CLOSED"
                        ticket.closed_at = datetime.utcnow()
                        closed_count += 1

                if closed_count > 0:
                    await session.commit()
                    print(f"[Tickets Cleanup] تم إغلاق {closed_count} تذكرة محذوفة.")
        except Exception as e:
            print(f"[Tickets Cleanup Error] {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not message.channel.name.startswith("ticket-"):
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SupportTicket).where(
                    SupportTicket.channel_id == message.channel.id,
                    SupportTicket.status.in_(["OPEN", "ESCALATED"])
                )
            )
            ticket = result.scalars().first()
            if not ticket:
                return

        # ─── 1. فحص المرفقات متعددة الوسائط (صور / تسجيلات صوتية عبر Gemini 1.5 Flash) ───
        if message.attachments:
            for att in message.attachments:
                content_type = (att.content_type or "").lower()
                filename = att.filename.lower()
                is_image = any(content_type.startswith(x) for x in ["image/"]) or any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"])
                is_audio = any(content_type.startswith(x) for x in ["audio/", "video/ogg"]) or any(filename.endswith(ext) for ext in [".mp3", ".ogg", ".wav", ".m4a", ".aac"])

                if is_image or is_audio:
                    media_kind = "صورة / لقطة شاشة" if is_image else "تسجيل صوتي / Voice Note"
                    async with message.channel.typing():
                        try:
                            file_bytes = await att.read()
                            analysis = await analyze_evidence_multimodal(
                                file_bytes=file_bytes,
                                mime_type=content_type or ("image/png" if is_image else "audio/mp3"),
                                context_text=message.content
                            )

                            is_violation = analysis.get("is_violation", False)
                            confidence = analysis.get("confidence", 0)
                            severity = analysis.get("severity", "NONE")
                            details = analysis.get("violation_details", "تم فحص الوسائط.")
                            extracted_text = analysis.get("transcription_or_text", "")
                            recom = analysis.get("recommendation", "NONE")

                            # تحديث حالة التذكرة
                            async with AsyncSessionLocal() as session:
                                t = await session.get(SupportTicket, ticket.ticket_id)
                                if t:
                                    t.evidence_type = "IMAGE" if is_image else "AUDIO"
                                    t.evidence_url = att.url
                                    t.evidence_status = "VERIFIED" if (is_violation and confidence >= 60) else "PENDING"
                                    t.evidence_score = confidence
                                    t.evidence_analysis = f"{details} (النص: {extracted_text[:200]})"
                                    await session.commit()

                            status_icon = "✅ معتمد رسمياً" if (is_violation and confidence >= 60) else "⚠️ تم الحفظ وبانتظار المراجعة"
                            embed_ev = create_neon_embed(
                                f"👁️🎙️ تقرير فحص الدليل الآلي | Gemini 1.5 Flash",
                                (
                                    f"• **نوع المرفق:** `{media_kind}`\n"
                                    f"• **حالة الاعتماد:** **{status_icon}**\n"
                                    f"• **نسبة الثقة:** `{confidence}%` | **مستوى الخطورة:** `{severity}`\n"
                                    f"• **النص المستخرج:** ```\n{extracted_text or 'لا يوجد نصوص مفرغة'}\n```\n"
                                    f"• **تفاصيل المخالفة:** {details}\n"
                                    f"• **الإجراء المقترح:** `{recom}`\n\n"
                                    f"*(تم تحديث حالة الدليل وفتح قفل الإجراءات التأديبية للمشرفين)*"
                                ),
                                color=0x2ECC71 if (is_violation and confidence >= 60) else 0xE67E22
                            )
                            embed_ev.set_thumbnail(url=att.url if is_image else None)
                            await message.channel.send(embed=embed_ev)
                        except Exception as e:
                            logger_err = f"خطأ أثناء فحص الدليل: {e}"
                            await message.channel.send(f"⚠️ تم استلام المرفق بنجاح: {att.url}")

        # ─── 2. فحص طلب استدعاء المشرفين ───
        content_lower = message.content.strip().lower()
        is_mod_req = (
            content_lower == "switch" or
            any(re.search(p, message.content, re.IGNORECASE) for p in [
                r"مشرف", r"مسؤول", r"مسئول", r"ادمن", r"أدمن", r"إدارة", r"اداره",
                r"طاقم", r"شخص حقيقي", r"بشري", r"support", r"admin", r"mod", r"staff",
                r"نادي لي", r"نادي المشرف", r"ابغى اكلم", r"بدي اكلم", r"ممكن اكلم"
            ])
        )

        if is_mod_req:
            async with AsyncSessionLocal() as session:
                t = await session.get(SupportTicket, ticket.ticket_id)
                if t:
                    t.status = "ESCALATED"
                    t.severity = "SERIOUS"
                    await session.commit()

            staff_mention = "@here"
            async with AsyncSessionLocal() as session:
                cfg = await session.get(GuildConfig, message.guild.id)
                if cfg and cfg.mod_role_id:
                    mr = message.guild.get_role(cfg.mod_role_id)
                    if mr:
                        staff_mention = mr.mention
                elif cfg and cfg.admin_role_id:
                    ar = message.guild.get_role(cfg.admin_role_id)
                    if ar:
                        staff_mention = ar.mention

            embed = create_warning_embed(
                "تحويل التذكرة للإدارة واستدعاء المشرفين",
                f"🔔 {message.author.mention} **تم استدعاء طاقم الإشراف بنجاح:** {staff_mention}\n\n"
                f"> تم إيقاف الردود الآلية، وتفضل بذكر مشكلتك أو استفسارك بالكامل وسيتدخل أحد المشرفين فوراً."
            )
            await message.channel.send(
                content=staff_mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True)
            )
            return

        # ─── 3. إيقاف ردود الـ AI إذا كانت التذكرة محولة لمشرف ───
        async with AsyncSessionLocal() as session:
            fresh_ticket = await session.get(SupportTicket, ticket.ticket_id)
            if not fresh_ticket or fresh_ticket.status == "ESCALATED":
                return

        # ─── 4. محاورة AI الذكية كالبشر ───
        async with message.channel.typing():
            history_messages = []
            async for msg in message.channel.history(limit=12, oldest_first=True):
                role = "assistant" if msg.author.bot else "user"
                if msg.content and not msg.content.startswith("http") and len(msg.content) > 1:
                    history_messages.append({"role": role, "content": msg.content})

            if not history_messages:
                history_messages = [{"role": "user", "content": message.content}]

            ai_reply = await ai_manager.generate(
                messages=history_messages,
                system_prompt=Strings.SYSTEM_TICKET_AI_PROMPT
            )

            splits = smart_split(ai_reply, max_length=2000)
            for s in splits:
                await message.channel.send(s)

    @app_commands.command(
        name="ticket_panel",
        description="إنشاء لوحة زر فتح التذاكر بالروم الحالي"
    )
    async def ticket_panel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "خطأ: يقتصر هذا الأمر على من يملك صلاحية إدارة السيرفر.", ephemeral=True
            )
            return

        desc = (
            "نظام الدعم الفني الذكي والتذاكر المتطورة **Neon Tickets v2.0**.\n\n"
            "`──────── مميزات وبروتوكول الدعم ────────`\n"
            "**1.** 🎫 اضغط الزر أدناه لفتح تذكرة خاصة فوراً.\n"
            "**2.** 👁️ **فحص الصور:** فحص لقطات الشاشة والشات عبر **Gemini 1.5 Flash Vision**.\n"
            "**3.** 🎙️ **فحص الصوتيات:** فحص المقاطع الصوتية وكشف الشتائم والتجاوزات.\n"
            "**4.** 👥 **نظام الشهود:** توثيق شهادة شاهدين محايدين كدليل معتمد.\n"
            "**5.** 🤖 محاورة ذكية طبيعية مع خيار استدعاء المشرفين بضغطة زر.\n\n"
            "👇 **اضغط على الزر أدناه للبدء:**"
        )
        embed = create_neon_embed("لوحة الدعم الفني والتذاكر | Support System", desc, color=0x00F5FF)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        view = OpenTicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ تم إنشاء لوحة التذاكر بنجاح.", ephemeral=True)

    @app_commands.command(
        name="close_ticket",
        description="إغلاق التذكرة الحالية وأرشفة السجل"
    )
    async def close_ticket_slash(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ هذا الأمر يستخدم فقط داخل قنوات التذاكر.", ephemeral=True)
            return

        embed_closing = create_neon_embed(
            "جاري إغلاق التذكرة",
            f"سيتم إغلاق التذكرة وأرشفة المحادثة خلال **5 ثوانٍ**...",
            color=0xFF5555
        )
        await interaction.response.send_message(embed=embed_closing)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SupportTicket).where(SupportTicket.channel_id == interaction.channel.id)
            )
            ticket = result.scalars().first()
            ticket_id_fmt = f"{ticket.ticket_id:04d}" if ticket else "0000"
            if ticket:
                ticket.status = "CLOSED"
                ticket.closed_at = datetime.utcnow()

            res_config = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            config = res_config.scalars().first()
            await session.commit()

        try:
            from utils.transcript_exporter import generate_html_transcript
            filepath = await generate_html_transcript(interaction.channel, ticket_id_fmt)

            if config and config.logging_enabled and config.log_channel_id:
                log_chan = interaction.guild.get_channel(config.log_channel_id)
                if log_chan:
                    file = discord.File(filepath, filename=f"transcript_ticket_{ticket_id_fmt}.html")
                    embed_log = create_success_embed(
                        f"أرشيف تذكرة مغلقة | Ticket #{ticket_id_fmt}",
                        f"أُغلقت التذكرة بواسطة {interaction.user.mention}.\n📎 سجل المحادثة HTML مرفق."
                    )
                    await log_chan.send(embed=embed_log, file=file)
        except Exception:
            pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"تم إغلاق التذكرة بواسطة {interaction.user}")
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
