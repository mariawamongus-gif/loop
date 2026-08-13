import discord
from discord import app_commands
from discord.ext import commands
from core.permissions import is_mod
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class FAQSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="قوانين السيرفر العامة", value="rules", emoji="📜", description="شروط وقواعد التواجد بالسيرفر"),
            discord.SelectOption(label="كيفية فتح وتذاكر الدعم الفني", value="tickets", emoji="🎫", description="خطوات المحاورة مع Neon AI والإدارة"),
            discord.SelectOption(label="أوامر البوت المتاحة للأعضاء", value="commands", emoji="⚙️", description="استعراض أحدث الأوامر والخصائص"),
            discord.SelectOption(label="روابط السيرفر الرسمية", value="links", emoji="🔗", description="الروابط والمعلومات الموثوقة")
        ]
        super().__init__(placeholder="اختر الموضوع الذي تريد قراءته...", options=options, custom_id="neon_faq_select")

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]

        if val == "rules":
            title = "📜 قوانين السيرفر العامة"
            desc = (
                "1. يمنع الإساءة أو الشتم بجميع أشكاله.\n"
                "2. يمنع نشر الروابط الإعلانية أو الاحتيالية.\n"
                "3. يمنع منعا باتا استخدام التذاكر لغايات إزعاج الإدارة.\n"
                "4. الاحترام المتبادل بين جميع الأعضاء واجب أساسي."
            )
        elif val == "tickets":
            title = "🎫 دليل التذاكر والدعم الفني"
            desc = (
                "• اضغط على زر فتح تذكرة بالروم المخصص.\n"
                "• سيقوم وحدة Neon AI بمحاورتك آلياً وتقديم الحلول الفنية.\n"
                "• يمكنك كتابة `switch` في أي وقت للتحويل لمشرف بشري."
            )
        elif val == "commands":
            title = "⚙️ الأوامر المتاحة للأعضاء"
            desc = (
                "• `/rank`: عرض بطاقة المستوى والخبرة PNG.\n"
                "• `/leaderboard`: عرض قائمة متصدري الخبرة بالسيرفر.\n"
                "• `/ask`: طرح سؤال مباشر على Neon AI.\n"
                "• `/explain_code`: تحليل وإصلاح الأكواد والبرمجة آلياً."
            )
        elif val == "links":
            title = "🔗 روابط وتفاصيل السيرفر"
            desc = (
                f"**اسم السيرفر:** {interaction.guild.name}\n"
                f"**إجمالي الأعضاء:** `{interaction.guild.member_count}`\n"
                f"جميع الحقوق محفوظة لنظام Neon Engine."
            )

        embed = create_neon_embed(title, desc, color=0x00F5FF)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class FAQView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FAQSelectMenu())


class FAQCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="faq", description="إنشاء لوحة الأسئلة الشائعة والقوانين التفاعلية بالروم")
    async def faq(self, interaction: discord.Interaction):
        if not await is_mod(interaction):
            await interaction.response.send_message("خطأ: يقتصر إنشاء لوحة الأسئلة على المشرفين.", ephemeral=True)
            return

        desc = (
            "مرحباً بك في مركز المعرفة والأسئلة الشائعة.\n\n"
            "استخدم القائمة المنسدلة أدناه لقراءة القوانين، دليل التذاكر، أو استعراض الأوامر والروابط الرسمية."
        )

        embed = create_neon_embed("دليل المعرفة والأسئلة الشائعة | Neon FAQ", desc, color=0x5865F2)
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        view = FAQView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("تم إنشاء لوحة الأسئلة الشائعة بنجاح.", ephemeral=True)

        await log_decision(
            interaction.guild,
            command="/faq",
            check_result="صلاحيات الإشراف مفحوصة",
            execution_step="إرسال لوحة FAQ التفاعلية بالروم",
            outcome="تم نشر اللوحة بنجاح"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(FAQCog(bot))
