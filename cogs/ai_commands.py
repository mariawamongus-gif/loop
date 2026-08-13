import discord
from discord import app_commands
from discord.ext import commands
from ai.fallback_manager import ai_manager
from utils.smart_split import smart_split
from core.strings import Strings

class AICommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ذاكرة قصيرة المدى لكل قناة {channel_id: [{"role": "user", "content": ...}, ...]}
        self.context_memory = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # الرد التلقائي عند منشن البوت خارج التذاكر
        if self.bot.user in message.mentions and not message.channel.name.startswith("ticket-"):
            clean_content = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            if not clean_content:
                clean_content = "مرحباً، كيف يمكنني مساعدتك؟"

            channel_id = message.channel.id
            if channel_id not in self.context_memory:
                self.context_memory[channel_id] = []

            self.context_memory[channel_id].append({"role": "user", "content": clean_content})
            if len(self.context_memory[channel_id]) > 5:
                self.context_memory[channel_id] = self.context_memory[channel_id][-5:]

            async with message.channel.typing():
                response = await ai_manager.generate(
                    messages=self.context_memory[channel_id],
                    system_prompt=Strings.SYSTEM_AI_PROMPT
                )
                self.context_memory[channel_id].append({"role": "assistant", "content": response})

                chunks = smart_split(response, max_length=2000)
                for chunk in chunks:
                    await message.channel.send(chunk)

    @app_commands.command(name="ask", description="طرح سؤال مباشر على وحدة Neon AI")
    @app_commands.describe(question="النص أو السؤال المراد إرساله للتحليل")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()

        channel_id = interaction.channel_id
        if channel_id not in self.context_memory:
            self.context_memory[channel_id] = []

        self.context_memory[channel_id].append({"role": "user", "content": question})

        # الإبقاء على آخر 5 رسائل فقط بالذاكرة القصيرة
        if len(self.context_memory[channel_id]) > 5:
            self.context_memory[channel_id] = self.context_memory[channel_id][-5:]

        response = await ai_manager.generate(
            messages=self.context_memory[channel_id],
            system_prompt=Strings.SYSTEM_AI_PROMPT
        )

        self.context_memory[channel_id].append({"role": "assistant", "content": response})

        # تمرير إجباري عبر خوارزمية التقسيم الذكي smart_split()
        chunks = smart_split(response, max_length=2000)

        # إرسال الجزء الأول للاستجابة المفرغة
        await interaction.followup.send(chunks[0])
        # إرسال باقي الأجزاء متتالية
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    @app_commands.command(name="explain_code", description="تحليل كود أو خطأ البرمجة وتفسيره وإصلاحه آلياً عبر Neon AI")
    @app_commands.describe(code="الكود البرمجي أو نص الخطأ Traceback المراد تحليله وإصلاحه")
    async def explain_code(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer()

        sys_prompt = (
            "أنت مهندس برمجيات خبير ووحدة Neon AI البرمجية. "
            "قم بتحليل الكود أو نص الخطأ المرفق بدقة عالية، وتحديد السبب الجذر للخطأ (Root Cause)، "
            "وتقديم الكود المصحح خطوة بخطوة بلغة أملس ومباشرة دون كلام زائد وبدون إيموجيات."
        )

        response = await ai_manager.generate(
            messages=[{"role": "user", "content": f"قم بتحليل وإصلاح هذا الكود أو الخطأ:\n```\n{code}\n```"}],
            system_prompt=sys_prompt
        )

        chunks = smart_split(response, max_length=2000)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

async def setup(bot: commands.Bot):
    await bot.add_cog(AICommandsCog(bot))

