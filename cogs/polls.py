import discord
from discord import app_commands
from discord.ext import commands
from core.permissions import is_mod
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class PollVoteButton(discord.ui.Button):
    def __init__(self, label: str, option_index: int):
        super().__init__(style=discord.ButtonStyle.primary, label=label, custom_id=f"neon_poll_opt_{option_index}")
        self.option_index = option_index

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view
        user_id = interaction.user.id

        # تسجيل أو تعديل تصويت العضو
        view.votes[user_id] = self.option_index
        await view.update_poll_embed(interaction)


class PollView(discord.ui.View):
    def __init__(self, question: str, options: list[str], author: discord.Member):
        super().__init__(timeout=None)
        self.question = question
        self.options = options
        self.author = author
        self.votes = {}  # {user_id: option_index}

        for idx, opt in enumerate(options):
            self.add_item(PollVoteButton(label=f"الخيار {idx + 1}: {opt[:20]}", option_index=idx))

    async def update_poll_embed(self, interaction: discord.Interaction):
        total_votes = len(self.votes)
        counts = [0] * len(self.options)
        for opt_idx in self.votes.values():
            counts[opt_idx] += 1

        results_str = ""
        for idx, opt in enumerate(self.options):
            c = counts[idx]
            pct = (c / total_votes * 100) if total_votes > 0 else 0
            filled = int(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
            results_str += f"**{idx + 1}. {opt}**\n`{bar}` `{c}` تصويت ({int(pct)}%)\n\n"

        desc = (
            f"**الاستبيان:** {self.question}\n\n"
            f"`──────── النتائج المباشرة ────────`\n"
            f"{results_str}"
            f"**إجمالي الأصوات:** `{total_votes}` | **بواسطة:** {self.author.mention}"
        )

        embed = create_neon_embed("استبيان وتصويت مشاركة | Neon Poll", desc, color=0x00F5FF)
        await interaction.response.edit_message(embed=embed, view=self)


class PollsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="poll", description="إنشاء استبيان تفاعلي مع تصويت حي وتحديثات شريطية")
    @app_commands.describe(
        question="موضوع أو سؤال الاستبيان",
        option1="الخيار الأول",
        option2="الخيار الثاني",
        option3="الخيار الثالث (اختياري)",
        option4="الخيار الرابع (اختياري)"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None
    ):
        if not await is_mod(interaction):
            await interaction.response.send_message("خطأ: يقتصر هذا الأمر على المشرفين والأدمنية.", ephemeral=True)
            return

        options = [o for o in [option1, option2, option3, option4] if o is not None]

        results_str = ""
        for idx, opt in enumerate(options):
            results_str += f"**{idx + 1}. {opt}**\n`░░░░░░░░░░` `0` تصويت (0%)\n\n"

        desc = (
            f"**الاستبيان:** {question}\n\n"
            f"`──────── النتائج المباشرة ────────`\n"
            f"{results_str}"
            f"**إجمالي الأصوات:** `0` | **بواسطة:** {interaction.user.mention}"
        )

        embed = create_neon_embed("استبيان وتصويت مشاركة | Neon Poll", desc, color=0x00F5FF)
        view = PollView(question, options, interaction.user)

        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("تم إنشاء الاستبيان بنجاح.", ephemeral=True)

        await log_decision(
            interaction.guild,
            command=f"/poll question={question[:30]}",
            check_result="صلاحيات الإشراف مفحوصة",
            execution_step=f"إنشاء استبيان تفاعلي بـ {len(options)} خيارات",
            outcome="تم نشر الاستبيان بنجاح"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(PollsCog(bot))
