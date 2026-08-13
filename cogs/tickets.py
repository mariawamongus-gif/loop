import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
import json
import asyncio
from datetime import datetime
from core.database import AsyncSessionLocal
from core.models import SupportTicket, TicketWitness, GuildConfig
from ai.fallback_manager import ai_manager
from core.strings import Strings
from utils.embeds import create_neon_embed, create_success_embed, create_error_embed, create_warning_embed
from utils.decision_log import log_decision
from utils.smart_split import smart_split


# ─── 1. لوحة تحكم التذكرة التفاعلية المستمرة ──────────────────────────────────
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

        embed = create_warning_embed(
            "تحويل التذكرة للدعم البشري",
            f"تم تحويل التذكرة **#{self.ticket_id:04d}** إلى مشرف بشري.\n"
            "سيتواصل معك أحد المشرفين قريباً، الرجاء الانتظار."
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="neon_ticket_close_btn",
        row=0
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
            result = await session.execute(
                select(SupportTicket).where(SupportTicket.ticket_id == self.ticket_id)
            )
            ticket = result.scalars().first()
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

    @discord.ui.button(
        label="إجراء إداري طارئ",
        emoji="🚨",
        style=discord.ButtonStyle.danger,
        custom_id="neon_ticket_mod_btn",
        row=0
    )
    async def emergency_mod(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "هذا الزر مخصص للأدمنية فقط.", ephemeral=True
            )
            return

        embed = create_warning_embed(
            "تفويض إجراء إداري طارئ",
            f"✅ تم منح التفويض الإداري لـ {interaction.user.mention}.\n"
            "النظام مصرح له الآن بتطبيق العقوبات اللازمة على صاحب التذكرة."
        )
        await interaction.response.send_message(embed=embed)


# ─── 2. زر فتح تذكرة جديد ──────────────────────────────────────────────────────
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

        # فحص إذا للمستخدم تذكرة مفتوحة بالفعل
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(SupportTicket).where(
                    SupportTicket.guild_id == guild.id,
                    SupportTicket.user_id == user.id,
                    SupportTicket.status.in_(["OPEN", "ESCALATED"])
                )
            )
            if existing.scalars().first():
                await interaction.response.send_message(
                    "⚠️ لديك تذكرة مفتوحة بالفعل. أغلق التذكرة الحالية قبل فتح واحدة جديدة.",
                    ephemeral=True
                )
                return

            ticket = SupportTicket(
                guild_id=guild.id,
                channel_id=0,
                user_id=user.id,
                status="OPEN"
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
            user: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
        }

        # إضافة صلاحيات للمشرفين والأدمنية
        if config and config.admin_role_id:
            admin_role = guild.get_role(config.admin_role_id)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )
        if config and config.mod_role_id:
            mod_role = guild.get_role(config.mod_role_id)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )

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

        # الـ Embed الترحيبي في التذكرة
        embed = create_neon_embed(
            title=f"🎫 تذكرة دعم #{ticket_id_formatted}",
            description=(
                f"مرحباً {user.mention} 👋\n\n"
                f"`──────── تعليمات التذكرة ────────`\n"
                f"**1.** اشرح مشكلتك بالتفصيل الكامل.\n"
                f"**2.** أرفق أي صور أو ملفات داعمة.\n"
                f"**3.** سيرد **Neon AI** عليك آلياً خلال ثوانٍ.\n"
                f"**4.** اضغط **تحويل لمشرف** إذا أردت دعماً بشرياً.\n\n"
                f"`──────── معلومات التذكرة ────────`\n"
                f"• **الرقم التسلسلي:** `#{ticket_id_formatted}`\n"
                f"• **المُنشئ:** {user.mention} (`{user.id}`)\n"
                f"• **وقت الفتح:** `{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC`\n"
                f"• **الحالة:** 🟢 مفتوحة"
            ),
            color=0x5865F2
        )
        embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else "")
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)

        # إرسال embed مع أزرار التحكم مرة واحدة فقط
        control_view = TicketControlView(ticket_id)
        await ticket_channel.send(content=user.mention, embed=embed, view=control_view)
        await interaction.response.send_message(
            f"✅ تم فتح تذكرتك: {ticket_channel.mention}", ephemeral=True
        )


# ─── 3. الـ Cog الرئيسي ─────────────────────────────────────────────────────────
class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # فحص هل القناة تابعة لتذكرة مفتوحة
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

        # أمر switch النصي
        if message.content.strip().lower() == "switch":
            async with AsyncSessionLocal() as session:
                t = await session.get(SupportTicket, ticket.ticket_id)
                if t:
                    t.status = "ESCALATED"
                    t.severity = "SERIOUS"
                    await session.commit()

            embed = create_warning_embed(
                "تحويل التذكرة للمشرف البشري",
                "تم تسجيل طلبك. سيتواصل معك أحد المشرفين قريباً."
            )
            await message.channel.send(embed=embed)
            return

        # محاورة AI — بدون إعادة إرسال الأزرار في كل مرة
        async with message.channel.typing():
            history_messages = []
            async for msg in message.channel.history(limit=12, oldest_first=True):
                role = "assistant" if msg.author.bot else "user"
                if msg.content and not msg.content.startswith("http") and len(msg.content) > 2:
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
            "نظام الدعم الفني المدعوم بالذكاء الاصطناعي **Neon AI**.\n\n"
            "`──────── كيف يعمل النظام ────────`\n"
            "**1.** اضغط الزر أدناه لفتح تذكرة دعم خاصة.\n"
            "**2.** اشرح مشكلتك بالتفصيل الكامل مع الأدلة.\n"
            "**3.** سيقوم **Neon AI** بتحليلها والرد آلياً.\n"
            "**4.** اضغط **تحويل لمشرف** للحصول على دعم بشري.\n\n"
            "`──────── سياسات الاستخدام ────────`\n"
            "⚠️ سوء استخدام التذاكر = عقوبة فورية.\n"
            "📁 النظام يحفظ كامل المحادثة كأرشيف HTML.\n"
            "🔒 التذكرة خاصة — لا يراها غيرك والإدارة."
        )

        embed = create_neon_embed(
            "نظام التذاكر والدعم الفني | Neon Support System",
            desc,
            color=0x5865F2
        )
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        view = OpenTicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ تم إنشاء لوحة التذاكر بنجاح.", ephemeral=True)

    @app_commands.command(
        name="close_ticket",
        description="إغلاق تذكرة محددة يدوياً بواسطة الأدمن (من أي قناة)"
    )
    @app_commands.describe(ticket_channel="قناة التذكرة المراد إغلاقها")
    async def close_ticket_cmd(
        self,
        interaction: discord.Interaction,
        ticket_channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "خطأ: يقتصر هذا الأمر على من يملك صلاحية إدارة القنوات.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SupportTicket).where(
                    SupportTicket.channel_id == ticket_channel.id,
                    SupportTicket.status.in_(["OPEN", "ESCALATED"])
                )
            )
            ticket = result.scalars().first()

            if not ticket:
                await interaction.followup.send(
                    "لم يتم العثور على تذكرة مفتوحة في القناة المحددة.", ephemeral=True
                )
                return

            ticket.status = "CLOSED"
            ticket.closed_at = datetime.utcnow()
            ticket_id_fmt = f"{ticket.ticket_id:04d}"

            res_config = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            config = res_config.scalars().first()
            await session.commit()

        try:
            from utils.transcript_exporter import generate_html_transcript
            filepath = await generate_html_transcript(ticket_channel, ticket_id_fmt)

            if config and config.log_channel_id:
                log_chan = interaction.guild.get_channel(config.log_channel_id)
                if log_chan:
                    file = discord.File(filepath, filename=f"transcript_{ticket_id_fmt}.html")
                    embed_log = create_success_embed(
                        f"تذكرة مُغلقة يدوياً | Ticket #{ticket_id_fmt}",
                        f"أُغلقت بواسطة {interaction.user.mention} عبر `/close_ticket`."
                    )
                    await log_chan.send(embed=embed_log, file=file)
        except Exception:
            pass

        await interaction.followup.send(
            f"✅ تم إغلاق التذكرة `#{ticket_id_fmt}` وأرشفتها بنجاح. القناة ستُحذف خلال 5 ثوانٍ.",
            ephemeral=True
        )
        await asyncio.sleep(5)
        try:
            await ticket_channel.delete(reason=f"إغلاق يدوي بواسطة {interaction.user.name}")
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
