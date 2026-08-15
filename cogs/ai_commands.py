import discord
from discord import app_commands
from discord.ext import commands
from ai.fallback_manager import ai_manager
from utils.smart_split import smart_split
from utils.embeds import create_neon_embed, create_success_embed, create_error_embed
from core.strings import Strings


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
        # الإبقاء على آخر 8 رسائل فقط
        if len(self.context_memory[key]) > 8:
            self.context_memory[key] = self.context_memory[key][-8:]

    def _track_usage(self, guild_id: int, response_len: int):
        if guild_id not in self.usage_stats:
            self.usage_stats[guild_id] = {"requests": 0, "chars_total": 0}
        self.usage_stats[guild_id]["requests"] += 1
        self.usage_stats[guild_id]["chars_total"] += response_len

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # تجاهل قنوات التذاكر تماماً لتجنب التضارب مع TicketsCog
        if message.channel.name.startswith("ticket-"):
            return

        # الرد التلقائي عند منشن البوت (خارج التذاكر)
        if (
            self.bot.user in message.mentions
        ):
            clean_content = (
                message.content
                .replace(f"<@{self.bot.user.id}>", "")
                .replace(f"<@!{self.bot.user.id}>", "")
                .strip()
            )
            if not clean_content:
                clean_content = "وحدة العمليات الاستراتيجية Neon جاهزة وتحت أمرك. بانتظار التوجيهات."

            self._add_to_context(message.channel.id, message.author.id, "user", clean_content)

            async with message.channel.typing():
                context = self._get_context(message.channel.id, message.author.id)
                response = await ai_manager.generate(
                    messages=context,
                    system_prompt=Strings.SYSTEM_AI_PROMPT
                )
                self._add_to_context(message.channel.id, message.author.id, "assistant", response)
                self._track_usage(message.guild.id, len(response))

            chunks = smart_split(response, max_length=2000)
            for chunk in chunks:
                await message.channel.send(chunk)

    # ─── /ask ────────────────────────────────────────────────────────────────────
    @app_commands.command(name="ask", description="طرح سؤال مباشر على وحدة Neon AI مع ذاكرة سياقية")
    @app_commands.describe(question="السؤال أو النص المراد إرساله لـ Neon AI")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()

        self._add_to_context(interaction.channel_id, interaction.user.id, "user", question)
        context = self._get_context(interaction.channel_id, interaction.user.id)

        response = await ai_manager.generate(
            messages=context,
            system_prompt=Strings.SYSTEM_AI_PROMPT
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
        description="تحليل كود أو خطأ برمجي وإصلاحه آلياً عبر Neon AI"
    )
    @app_commands.describe(code="الكود أو نص الخطأ المراد تحليله")
    async def explain_code(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer()

        sys_prompt = (
            "أنت مهندس برمجيات خبير ووحدة Neon AI البرمجية. "
            "حلل الكود أو الخطأ بدقة، حدد السبب الجذري (Root Cause)، "
            "وقدم الحل المصحح خطوة بخطوة بلغة واضحة ومباشرة."
        )

        response = await ai_manager.generate(
            messages=[{"role": "user", "content": f"حلل وأصلح هذا:\n```\n{code}\n```"}],
            system_prompt=sys_prompt
        )
        self._track_usage(interaction.guild_id, len(response))

        chunks = smart_split(response, max_length=2000)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    # ─── /clear_memory ────────────────────────────────────────────────────────────
    @app_commands.command(
        name="clear_memory",
        description="مسح الذاكرة السياقية لـ Neon AI في هذه القناة"
    )
    async def clear_memory(self, interaction: discord.Interaction):
        key = self._get_key(interaction.channel_id, interaction.user.id)
        if key in self.context_memory:
            del self.context_memory[key]
            embed = create_success_embed(
                "مسح الذاكرة السياقية | Clear Memory",
                "تم مسح سجل محادثتك مع Neon AI في هذه القناة.\n"
                "المحادثة القادمة ستبدأ من الصفر تماماً."
            )
        else:
            embed = create_neon_embed(
                "مسح الذاكرة | Clear Memory",
                "لا توجد ذاكرة سياقية محفوظة لك في هذه القناة حالياً."
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── /ai_stats ────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="ai_stats",
        description="عرض إحصائيات استخدام Neon AI في هذا السيرفر"
    )
    async def ai_stats(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        stats = self.usage_stats.get(guild_id, {"requests": 0, "chars_total": 0})

        total_req = stats["requests"]
        total_chars = stats["chars_total"]
        active_sessions = sum(
            1 for (ch, _) in self.context_memory.keys()
            if ch == interaction.channel_id
        )

        desc = (
            f"`──────── إحصائيات Neon AI ────────`\n"
            f"**إجمالي الطلبات:** `{total_req}`\n"
            f"**إجمالي الأحرف المولّدة:** `{total_chars:,}`\n"
            f"**جلسات الذاكرة النشطة (القناة الحالية):** `{active_sessions}`\n"
            f"**إجمالي جلسات الذاكرة (الكل):** `{len(self.context_memory)}`\n\n"
            f"*الإحصائيات تُعاد عند إعادة تشغيل البوت.*"
        )

        embed = create_neon_embed("إحصائيات Neon AI | AI Usage Stats", desc, color=0x9D4EDD)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── /summarize ───────────────────────────────────────────────────────────────
    @app_commands.command(
        name="summarize",
        description="تلخيص آخر N رسالة في القناة الحالية بواسطة Neon AI"
    )
    @app_commands.describe(count="عدد الرسائل المراد تلخيصها (5-50)")
    async def summarize(self, interaction: discord.Interaction, count: int = 20):
        if count < 5 or count > 50:
            await interaction.response.send_message("العدد يجب أن يكون بين 5 و 50.", ephemeral=True)
            return

        await interaction.response.defer()

        messages_text = []
        async for msg in interaction.channel.history(limit=count, oldest_first=True):
            if not msg.author.bot and msg.content:
                messages_text.append(f"{msg.author.display_name}: {msg.content}")

        if not messages_text:
            await interaction.followup.send("لا توجد رسائل كافية للتلخيص.", ephemeral=True)
            return

        conversation = "\n".join(messages_text)
        sys_prompt = (
            "أنت وحدة تلخيص محادثات. لخّص المحادثة التالية بشكل موجز وواضح "
            "مع ذكر النقاط الرئيسية والمخرجات المهمة."
        )
        response = await ai_manager.generate(
            messages=[{"role": "user", "content": f"لخص هذه المحادثة:\n\n{conversation}"}],
            system_prompt=sys_prompt
        )

        self._track_usage(interaction.guild_id, len(response))
        chunks = smart_split(response, max_length=2000)
        await interaction.followup.send(f"**📝 ملخص آخر {count} رسالة:**\n\n{chunks[0]}")
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

        from ai.web_search import search_and_synthesize
        res = await search_and_synthesize(query)

        summary = res["summary"]
        sources = res["sources"]

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


async def setup(bot: commands.Bot):
    await bot.add_cog(AICommandsCog(bot))
