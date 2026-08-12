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
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision
from utils.smart_split import smart_split

# 1. لوحة تحكم التذكرة التفاعلية المستمرة
class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="تحويل لمشرف بشري (Switch)", style=discord.ButtonStyle.primary, custom_id="neon_ticket_switch_btn")
    async def switch_to_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(SupportTicket).where(SupportTicket.ticket_id == self.ticket_id))
            ticket = result.scalars().first()
            if ticket:
                ticket.status = "ESCALATED"
                ticket.severity = "SERIOUS"
                await session.commit()

        embed = create_neon_embed("تحويل التذكرة", Strings.TICKET_SWITCH_TRIGGERED)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.secondary, custom_id="neon_ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("جاري إغلاق التذكرة وتوليد سجل HTML التفاعلي خلال 5 ثوانٍ...")
        
        ticket_id_fmt = f"{self.ticket_id:04d}"
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(SupportTicket).where(SupportTicket.ticket_id == self.ticket_id))
            ticket = result.scalars().first()
            if ticket:
                ticket.status = "CLOSED"
                ticket.closed_at = datetime.utcnow()

            res_config = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
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
                    embed_log = create_neon_embed(
                        f"أرشيف تذكرة مغلقة | Transcript #{ticket_id_fmt}",
                        f"تم إغلاق التذكرة بواسطة {interaction.user.mention}.\nتم إرفاق سجل المحادثة التفاعلي بصيغة HTML."
                    )
                    await log_chan.send(embed=embed_log, file=file)
        except Exception as e:
            pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="تم إغلاق التذكرة وتوليد سجل HTML")
        except Exception:
            pass


    @discord.ui.button(label="إجراء إداري طارئ (Admin Only)", style=discord.ButtonStyle.danger, custom_id="neon_ticket_mod_btn")
    async def emergency_mod(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("هذا الزر مخصص لتفويض المشرفين والأدمنية فقط.", ephemeral=True)
            return

        embed = create_neon_embed(
            "تفويض إجراء إداري",
            "تم تأكيد تفويض الأدمن. النظام الآن مصرح له بتطبيق العقوبات الإدارية بحق المشتبه به في هذه التذكرة."
        )
        await interaction.response.send_message(embed=embed)


# 2. زر فتح تذكرة جديد
class OpenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="فتح تذكرة استقبال مشاكل", style=discord.ButtonStyle.danger, custom_id="neon_open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        async with AsyncSessionLocal() as session:
            # توليد رقم تسلسلي جديد للتذكرة
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

            result_config = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild.id))
            config = result_config.scalars().first()

        category = None
        if config and config.ticket_category_id:
            category = guild.get_channel(config.ticket_category_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # تسمية القناة باسم التذكرة ورقمها السلسلي
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{ticket_id_formatted}",
            category=category,
            overwrites=overwrites
        )

        async with AsyncSessionLocal() as session:
            t = await session.get(SupportTicket, ticket_id)
            if t:
                t.channel_id = ticket_channel.id
                await session.commit()

        # إرسال العنوان بالشكل المطلوب والإرشادات الشاملة
        embed = create_neon_embed(
            title=Strings.TICKET_CREATED_TITLE.format(ticket_id=ticket_id_formatted),
            description=f"مرحباً بك {user.mention}.\n\n{Strings.TICKET_OPENING_GUIDELINES}"
        )
        
        control_view = TicketControlView(ticket_id)
        await ticket_channel.send(content=user.mention, embed=embed, view=control_view)
        await interaction.response.send_message(f"تم فتح التذكرة بالقناة: {ticket_channel.mention}", ephemeral=True)


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

        # 1. فحص أمر switch النصي المباشر
        if message.content.strip().lower() == "switch":
            async with AsyncSessionLocal() as session:
                t = await session.get(SupportTicket, ticket.ticket_id)
                if t:
                    t.status = "ESCALATED"
                    t.severity = "SERIOUS"
                    await session.commit()

            embed = create_neon_embed("تحويل التذكرة النصي", Strings.TICKET_SWITCH_TRIGGERED)
            await message.channel.send(embed=embed)

            await log_decision(
                message.guild,
                command=f"TEXT_SWITCH ticket_id={ticket.ticket_id}",
                check_result="تم استلام أمر switch النصي في التذكرة",
                execution_step="تغيير حالة التذكرة إلى ESCALATED والإخطار",
                outcome="تم التحويل للبشر بنجاح"
            )
            return

        # 2. محاورة AI مستفيضة ومستمرة على كل رسالة يبعثها العضو
        async with message.channel.typing():
            # تجميع سجل آخر 10 رسائل في القناة لبناء ذاكرة سياقية كاملة للمحاورة
            history_messages = []
            async for msg in message.channel.history(limit=10, oldest_first=True):
                role = "assistant" if msg.author.bot else "user"
                # تجنب تضمين التعليمات البرمجية أو الـ Embeds الجاهزة
                if msg.content and not msg.content.startswith("http"):
                    history_messages.append({"role": role, "content": msg.content})

            if not history_messages:
                history_messages = [{"role": "user", "content": message.content}]

            # توليد رد مستفيض ومحاور من الـ AI
            ai_reply = await ai_manager.generate(
                messages=history_messages,
                system_prompt=Strings.SYSTEM_TICKET_AI_PROMPT
            )

            # تقسيم وتنسيق الرد بأمان
            splits = smart_split(ai_reply, max_length=2000)
            for s in splits:
                await message.channel.send(s)

            # إرسال أزرار التحكم بعد كل رد لتسهيل الاختيار في كل الحالات
            control_view = TicketControlView(ticket.ticket_id)
            embed_status = create_neon_embed(
                "خيارات التذكرة المتاحة",
                "يمكنك مواصلة المحادثة مع Neon AI أو الضغط أدناه للتحويل لمشرف بشري أو إغلاق التذكرة."
            )
            await message.channel.send(embed=embed_status, view=control_view)

    @app_commands.command(name="ticket_panel", description="إنشاء لوحة زر فتح التذاكر بالروم الحالي")
    async def ticket_panel(self, interaction: discord.Interaction):
        desc = (
            "نظام الدعم الفني الآلي مدعوم بالذكاء الاصطناعي.\n\n"
            "`──────── كيف يعمل النظام ────────`\n"
            "**1.** اضغط الزر أدناه لفتح تذكرة خاصة.\n"
            "**2.** اشرح مشكلتك بالتفصيل.\n"
            "**3.** سيقوم Neon AI بتحليل ومحاورتك آلياً.\n"
            "**4.** اكتب `switch` للتحويل لمشرف بشري.\n\n"
            "`──────── تنبيهات مهمة ────────`\n"
            "سوء استخدام التذاكر يؤدي لعقوبات فورية.\n"
            "النظام يسجل كامل المحادثة كأرشيف HTML."
        )

        embed = create_neon_embed("نظام التذاكر والدعم الفني | Neon Support", desc, color=0x5865F2)
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        view = OpenTicketView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("تم إنشاء لوحة التذاكر بنجاح.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))

