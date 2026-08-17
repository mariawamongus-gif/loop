import re
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional
from ai.fallback_manager import ai_manager
from utils.smart_split import smart_split
from utils.embeds import create_neon_embed, create_success_embed, create_error_embed
from core.strings import Strings
from core.database import AsyncSessionLocal
from core.models import GuildConfig, ModerationCase


def is_requesting_staff(text: str) -> bool:
    """فحص ذكي للتحقق مما إذا كان العضو يطلب التحدث مع مشرف أو إدارة."""
    patterns = [
        r"مشرف", r"مسؤول", r"مسئول", r"ادمن", r"أدمن", r"إدارة", r"اداره",
        r"طاقم", r"شخص حقيقي", r"بشري", r"support", r"admin", r"mod", r"staff",
        r"نادي لي", r"نادي المشرف", r"ابغى اكلم", r"بدي اكلم", r"ممكن اكلم"
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def parse_action_intent(text: str) -> Optional[tuple[str, int]]:
    """استخراج نية الإجراء الإداري ومعرف المستخدم من الرسالة."""
    user_ids = re.findall(r"\d{17,20}", text)
    if not user_ids:
        return None

    target_id = int(user_ids[0])
    text_lower = text.lower()

    if any(k in text_lower for k in ["فك حظر", "شيل الحظر", "الغاء حظر", "unban"]):
        return ("UNBAN", target_id)
    elif any(k in text_lower for k in ["حظر", "احظر", "تبنيد", "بند", "ban", "block"]):
        return ("BAN", target_id)
    elif any(k in text_lower for k in ["طرد", "اطرد", "kick"]):
        return ("KICK", target_id)
    elif any(k in text_lower for k in ["كتم", "اكتم", "ميوت", "timeout", "mute"]):
        return ("TIMEOUT", target_id)

    return None


def can_execute_action(author: discord.Member, action: str) -> bool:
    """التحقق من امتلاك العضو لصلاحية تنفيذ الإجراء الإداري المطلوب."""
    if author.guild_permissions.administrator:
        return True
    if action in ("BAN", "UNBAN") and author.guild_permissions.ban_members:
        return True
    if action == "KICK" and author.guild_permissions.kick_members:
        return True
    if action == "TIMEOUT" and author.guild_permissions.moderate_members:
        return True
    return False


def check_hierarchy_for_id(guild: discord.Guild, mod: discord.Member, target_id: int) -> tuple[bool, str]:
    """فحص تدرج الرتب وحماية الإدارة عند تنفيذ الأوامر بالآيدي المباشر."""
    if target_id == guild.owner_id:
        return False, "لا يمكن تطبيق إجراء إداري على مالك السيرفر."
    if target_id == mod.id:
        return False, "لا يمكنك تطبيق إجراء إداري على نفسك."
    target_member = guild.get_member(target_id)
    if target_member:
        if mod.id != guild.owner_id and target_member.top_role >= mod.top_role:
            return False, "لا يمكنك تطبيق إجراء على عضو يملك رتبة مساوية لرتبتك أو أعلى منها."
        if guild.me and target_member.top_role >= guild.me.top_role:
            return False, "رتبة العضو أعلى من رتبة البوت أو مساوية لها."
    return True, ""



async def get_staff_role_mention(guild: discord.Guild) -> str:
    """جلب منشن رتبة المشرفين أو الإدارة من إعدادات السيرفر."""
    try:
        async with AsyncSessionLocal() as session:
            config = await session.get(GuildConfig, guild.id)
            if config:
                if config.mod_role_id:
                    r = guild.get_role(config.mod_role_id)
                    if r:
                        return r.mention
                if config.admin_role_id:
                    r = guild.get_role(config.admin_role_id)
                    if r:
                        return r.mention
    except Exception:
        pass

    for role in guild.roles:
        if role.permissions.manage_guild or role.permissions.manage_messages or role.permissions.administrator:
            if not role.is_default() and not role.managed:
                return role.mention
    return "@here"


class AIActionConfirmView(discord.ui.View):
    """لوحة تفاعلية فورية لتأكيد وتنفيذ الإجراء الإداري بضغطة زر واحدة."""
    def __init__(self, executor: discord.Member, target_id: int, action: str, reason: str):
        super().__init__(timeout=90)
        self.executor = executor
        self.target_id = target_id
        self.action = action
        self.reason = reason

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.executor.id:
            await interaction.response.send_message("هذا الزر مخصص للمسؤول الذي طلب الإجراء فقط.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="تأكيد التنفيذ فوراً", style=discord.ButtonStyle.danger, emoji="🔨")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        for item in self.children:
            item.disabled = True

        try:
            case_id = 0
            if self.action == "BAN":
                await guild.ban(discord.Object(id=self.target_id), reason=self.reason)
                async with AsyncSessionLocal() as session:
                    case = ModerationCase(
                        guild_id=guild.id,
                        user_id=self.target_id,
                        mod_id=self.executor.id,
                        action="BAN",
                        reason=self.reason,
                        created_at=datetime.utcnow()
                    )
                    session.add(case)
                    await session.commit()
                    await session.refresh(case)
                    case_id = case.case_id

                embed = discord.Embed(
                    title="❖ تم تنفيذ الحظر بنجاح | Action Executed",
                    description=(
                        f"✅ **تم حظر المستخدم بنجاح من السيرفر بواسطة Neon AI بتفويض منك.**\n\n"
                        f"• **المستخدم المستهدف:** <@{self.target_id}> (`{self.target_id}`)\n"
                        f"• **المنفذ المسؤول:** {self.executor.mention}\n"
                        f"• **رقم الحالة:** `Case #{case_id}`\n"
                        f"• **السبب:** `{self.reason}`"
                    ),
                    color=0x50FA7B
                )
                await interaction.response.edit_message(embed=embed, view=self)
                return

            elif self.action == "KICK":
                member = guild.get_member(self.target_id)
                if member:
                    await member.kick(reason=self.reason)
                    async with AsyncSessionLocal() as session:
                        case = ModerationCase(
                            guild_id=guild.id,
                            user_id=self.target_id,
                            mod_id=self.executor.id,
                            action="KICK",
                            reason=self.reason,
                            created_at=datetime.utcnow()
                        )
                        session.add(case)
                        await session.commit()
                        await session.refresh(case)
                        case_id = case.case_id

                    embed = discord.Embed(
                        title="❖ تم تنفيذ الطرد بنجاح | Action Executed",
                        description=f"✅ تم طرد العضو <@{self.target_id}> بنجاح من السيرفر بتفويض منك | `Case #{case_id}`.",
                        color=0x50FA7B
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await interaction.response.edit_message(content="❌ تعذر العثور على العضو في السيرفر لطرده.", view=self)
                return

            elif self.action == "UNBAN":
                await guild.unban(discord.Object(id=self.target_id), reason=self.reason)
                async with AsyncSessionLocal() as session:
                    case = ModerationCase(
                        guild_id=guild.id,
                        user_id=self.target_id,
                        mod_id=self.executor.id,
                        action="UNBAN",
                        reason=self.reason,
                        created_at=datetime.utcnow()
                    )
                    session.add(case)
                    await session.commit()
                    await session.refresh(case)
                    case_id = case.case_id

                embed = discord.Embed(
                    title="❖ تم إلغاء الحظر بنجاح | Action Executed",
                    description=f"✅ تم إلغاء حظر المستخدم <@{self.target_id}> بنجاح | `Case #{case_id}`.",
                    color=0x50FA7B
                )
                await interaction.response.edit_message(embed=embed, view=self)
                return

        except Exception as e:
            await interaction.response.edit_message(content=f"❌ تعذر تنفيذ الإجراء بسبب قيود الصلاحيات أو الرتب: `{e}`", view=self)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="تم إلغاء تنفيذ الإجراء بناءً على طلبك.", embed=None, view=self)


class AICommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ذاكرة قصيرة المدى: {(channel_id, user_id): [messages]}
        self.context_memory: dict = {}
        # إحصائيات الاستخدام: {guild_id: {"requests": int, "tokens_est": int}}
        self.usage_stats: dict = {}

    def _get_key(self, channel_id: int, user_id: int) -> tuple:
        return (channel_id, user_id)

    def _get_context(self, channel_id: int, user_id: int) -> list:
        key = self._get_key(channel_id, user_id)
        return self.context_memory.get(key, [])

    def _add_to_context(self, channel_id: int, user_id: int, role: str, content: str):
        key = self._get_key(channel_id, user_id)
        if key not in self.context_memory:
            self.context_memory[key] = []
        self.context_memory[key].append({"role": role, "content": content})
        if len(self.context_memory[key]) > 8:
            self.context_memory[key] = self.context_memory[key][-8:]

    def _track_usage(self, guild_id: int, response_len: int):
        if guild_id not in self.usage_stats:
            self.usage_stats[guild_id] = {"requests": 0, "chars_total": 0}
        self.usage_stats[guild_id]["requests"] += 1
        self.usage_stats[guild_id]["chars_total"] += response_len

    def _build_system_prompt(self, guild: discord.Guild, author: discord.Member, channel: discord.abc.GuildChannel) -> str:
        return (
            f"{Strings.SYSTEM_AI_PROMPT}\n\n"
            f"[معلومات بيئة السيرفر الحالية]:\n"
            f"- اسم السيرفر: {guild.name} (ID: {guild.id})\n"
            f"- العضو الذي يخاطبك: {author.display_name} (ID: {author.id})\n"
            f"- القناة الحالية: #{channel.name}\n"
            f"- إجمالي أعضاء السيرفر: {guild.member_count} عضو\n"
            f"- صلاحياتك: أنت تملك صلاحيات إدارة ودفاع كاملة لمساعدة المشرفين والأعضاء."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # تجاهل قنوات التذاكر تماماً لتجنب التضارب مع TicketsCog
        if message.channel.name.startswith("ticket-"):
            return

        # الرد التلقائي عند منشن البوت (خارج التذاكر)
        if self.bot.user in message.mentions:
            clean_content = (
                message.content
                .replace(f"<@{self.bot.user.id}>", "")
                .replace(f"<@!{self.bot.user.id}>", "")
                .strip()
            )
            if not clean_content:
                clean_content = "اهلا"

            # 1. فحص طلب تنفيذ إجراء إداري حقيقي (مثل حظر عضو برقم الآيدي)
            action_intent = parse_action_intent(clean_content)
            if action_intent:
                action, target_id = action_intent
                if not can_execute_action(message.author, action):
                    await message.channel.send(
                        f"❌ عذراً {message.author.mention}، لا تملك الصلاحيات الإدارية المطلوبة (`{action}`) لتنفيذ هذا الإجراء."
                    )
                    return

                allowed, err_msg = check_hierarchy_for_id(message.guild, message.author, target_id)
                if not allowed:
                    await message.channel.send(f"❌ تعذر تنفيذ الإجراء: {err_msg}")
                    return

                action_names = {"BAN": "حظر نهائي (Ban)", "KICK": "طرد (Kick)", "UNBAN": "فك حظر (Unban)"}
                action_name = action_names.get(action, action)
                reason = f"طلب إداري عبر المساعد الذكي بتفويض من {message.author}"

                embed = discord.Embed(
                    title="🛡️ تأكيد تنفيذ الإجراء الإداري | Assistant Action",
                    description=(
                        f"أهلاً بك {message.author.mention}، بالتأكيد يمكنني مساعدتك في تنفيذ هذا الإجراء فوراً.\n\n"
                        f"• **الإجراء المطلوب:** `{action_name}`\n"
                        f"• **المستخدم المستهدف:** <@{target_id}> (`{target_id}`)\n"
                        f"• **المسؤول المفوض:** {message.author.mention}\n\n"
                        f"👇 **اضغط على الزر أدناه لتأكيد وتنفيذ العملية فوراً في السيرفر:**"
                    ),
                    color=0x2B2D31
                )
                view = AIActionConfirmView(message.author, target_id, action, reason)
                await message.channel.send(embed=embed, view=view)
                return


            # 2. فحص طلب استدعاء المشرفين
            if is_requesting_staff(clean_content):
                staff_mention = await get_staff_role_mention(message.guild)
                msg_txt = (
                    f"🔔 {message.author.mention} **تم استدعاء طاقم الإشراف لمساعدتك:** {staff_mention}\n"
                    f"> تفضل بطرح تفاصيل استفسارك أو مشكلتك هنا وسيتدخل أحد المشرفين في أقرب وقت."
                )
                await message.channel.send(
                    msg_txt,
                    allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True)
                )
                return

            self._add_to_context(message.channel.id, message.author.id, "user", clean_content)

            async with message.channel.typing():
                context = self._get_context(message.channel.id, message.author.id)
                sys_prompt = self._build_system_prompt(message.guild, message.author, message.channel)
                response = await ai_manager.generate(
                    messages=context,
                    system_prompt=sys_prompt
                )
                self._add_to_context(message.channel.id, message.author.id, "assistant", response)
                self._track_usage(message.guild.id, len(response))

            chunks = smart_split(response, max_length=2000)
            for chunk in chunks:
                await message.channel.send(chunk)

    # ─── /ask ────────────────────────────────────────────────────────────────────
    @app_commands.command(name="ask", description="طرح سؤال أو طلب إجراء مباشر على وحدة Neon AI")
    @app_commands.describe(question="السؤال أو طلب الإجراء الموجه لـ Neon AI")
    async def ask(self, interaction: discord.Interaction, question: str):
        # 1. فحص طلب تنفيذ إجراء إداري
        action_intent = parse_action_intent(question)
        if action_intent:
            action, target_id = action_intent
            if not can_execute_action(interaction.user, action):
                await interaction.response.send_message(
                    f"❌ عذراً {interaction.user.mention}، لا تملك الصلاحيات الإدارية المطلوبة (`{action}`) لتنفيذ هذا الإجراء.",
                    ephemeral=True
                )
                return

            allowed, err_msg = check_hierarchy_for_id(interaction.guild, interaction.user, target_id)
            if not allowed:
                await interaction.response.send_message(f"❌ تعذر تنفيذ الإجراء: {err_msg}", ephemeral=True)
                return

            action_names = {"BAN": "حظر نهائي (Ban)", "KICK": "طرد (Kick)", "UNBAN": "فك حظر (Unban)"}

            action_name = action_names.get(action, action)
            reason = f"طلب إداري عبر المساعد الذكي بتفويض من {interaction.user}"

            embed = discord.Embed(
                title="🛡️ تأكيد تنفيذ الإجراء الإداري | Assistant Action",
                description=(
                    f"أهلاً بك {interaction.user.mention}، بالتأكيد يمكنني مساعدتك في تنفيذ هذا الإجراء فوراً.\n\n"
                    f"• **الإجراء المطلوب:** `{action_name}`\n"
                    f"• **المستخدم المستهدف:** <@{target_id}> (`{target_id}`)\n"
                    f"• **المسؤول المفوض:** {interaction.user.mention}\n\n"
                    f"👇 **اضغط على الزر أدناه لتأكيد وتنفيذ العملية فوراً في السيرفر:**"
                ),
                color=0x2B2D31
            )
            view = AIActionConfirmView(interaction.user, target_id, action, reason)
            await interaction.response.send_message(embed=embed, view=view)
            return

        await interaction.response.defer()

        # 2. فحص طلب استدعاء المشرفين
        if is_requesting_staff(question):
            staff_mention = await get_staff_role_mention(interaction.guild)
            msg_txt = (
                f"🔔 {interaction.user.mention} **تم استدعاء طاقم الإشراف لمساعدتك:** {staff_mention}\n"
                f"> تفضل بطرح تفاصيل استفسارك أو مشكلتك هنا وسيتدخل أحد المشرفين في أقرب وقت."
            )
            await interaction.followup.send(
                msg_txt,
                allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=True)
            )
            return

        self._add_to_context(interaction.channel_id, interaction.user.id, "user", question)
        context = self._get_context(interaction.channel_id, interaction.user.id)

        sys_prompt = self._build_system_prompt(interaction.guild, interaction.user, interaction.channel)
        response = await ai_manager.generate(
            messages=context,
            system_prompt=sys_prompt
        )
        self._add_to_context(interaction.channel_id, interaction.user.id, "assistant", response)
        self._track_usage(interaction.guild_id, len(response))

        chunks = smart_split(response, max_length=2000)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    # ─── /explain_code ────────────────────────────────────────────────────────────
    @app_commands.command(
        name="explain_code",
        description="تحليل كود برمجي، شرح منطقه، اكتشاف الثغرات، واقتراح التحسينات"
    )
    @app_commands.describe(code="الكود البرمجي المراد تحليله")
    async def explain_code(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer()

        user_prompt = (
            f"قم بتحليل الكود البرمجي التالي بدقة:\n"
            f"1. شرح وظيفة الكود وما يفعله.\n"
            f"2. اكتشاف الأخطاء المحتملة أو الثغرات الأمنية إن وجدت.\n"
            f"3. تقديم النسخة المصححة والمحسنة من الكود.\n\n"
            f"```\n{code}\n```"
        )

        response = await ai_manager.generate(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt="أنت مبرمج وخبير أمني متقدم. قدم تحليلاً برمجياً دقيقاً ومباشراً بدون حشو."
        )

        chunks = smart_split(response, max_length=2000)
        embed = create_neon_embed("تحليل وشرح الكود البرمجي | Code Review", chunks[0], color=0x9B59B6)
        await interaction.followup.send(embed=embed)
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    # ─── /search ─────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="search",
        description="البحث الحي في شبكة الإنترنت وتلخيص النتائج عبر Neon AI مع إرفاق المصادر"
    )
    @app_commands.describe(query="موضوع أو سؤال البحث بالإنترنت")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        try:
            from ai.web_search import search_and_synthesize
            res = await search_and_synthesize(query)

            summary = res.get("summary", "لم يتم العثور على ملخص.")
            sources = res.get("sources", [])

            sources_str = "\n".join(sources[:4]) if sources else "`المصادر مفتوحة`"
            desc = (
                f"**الاستعلام:** `{query}`\n\n"
                f"`──────── التقرير المستخرج ────────`\n"
                f"{summary}\n\n"
                f"`──────── المصادر والروابط ────────`\n"
                f"{sources_str}"
            )
            embed = create_neon_embed(f"نتائج البحث المباشر | Web Search", desc, color=0x00F5FF)
            await interaction.followup.send(embed=embed)
            self._track_usage(interaction.guild_id, len(summary))
        except Exception as e:
            await interaction.followup.send(f"تعذر إتمام عملية البحث في الإنترنت حالياً: `{e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AICommandsCog(bot))
