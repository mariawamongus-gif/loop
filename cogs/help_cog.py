import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from config import Config

# ألوان ثيم الرخام والجرانيت الرمادي الأنيق (Slate / Discord Dark Palette)
SLATE_DARK = 0x2B2D31
SILVER_METALLIC = 0x80848E

HELP_DATABASE = {
    "moderation": {
        "emoji": "⚔️",
        "title": "الإدارة والإشراف",
        "menu_desc": "أمر إداري — تحكم لا حدود له بسيرفرك",
        "desc": "حزمة الأدوات التأديبية والإشرافية الميدانية للتحكم في الأعضاء وتنظيف القنوات:",
        "commands": [
            ("`/ban [user] [reason] [delete_days] [dm_notify]`", "حظر العضو نهائياً من السيرفر مع مسح الرسائل وإشعار بالخاص."),
            ("`/unban [user_id] [reason]`", "إلغاء حظر عضو محظور مسبقاً باستخدام الآيدي."),
            ("`/kick [user] [reason] [dm_notify]`", "طرد العضو من السيرفر مع إرسال سبب الطرد له بالخاص."),
            ("`/timeout [user] [minutes] [reason] [dm_notify]`", "كتم مؤقت للعضو (Timeout) لمنعه من الكتابة والتحدث."),
            ("`/remove_timeout [user] [reason]`", "فك الكتم المؤقت فوراً عن العضو واستعادة الصلاحيات."),
            ("`/warn [user] [reason] [dm_notify]`", "تسجيل تحذير رسمي بحق العضو في سجله التأديبي مع إشعار خاص."),
            ("`/strike [user] [reason]`", "تسجيل إنذار تراكمي (تطبيق عقوبات تصاعدية تلقائياً عند التكرار)."),
            ("`/strikes_list [user]`", "عرض قائمة الإنذارات النشطة بحق العضو وتاريخ كل إنذار."),
            ("`/clear [amount] [user] [from_date] [to_date]`", "مسح جماعي ذكي وفلترة للرسائل حسب العضو أو التاريخ."),
            ("`/history [user]`", "استعراض السجل التأديبي والأمني الكامل للعضو وسوابقه."),
            ("`/case [case_id]`", "الاستعلام عن تفاصيل قضية إدارية محددة ومعرفة المشرف والإجراء."),
            ("`/scan_user [user]`", "فحص أمني وتحليلي لحساب العضو (عمر الحساب، الرتب، ونسبة الخطورة)."),
            ("`/audit [count]`", "مراقبة حية لسجل أحداث السيرفر (Audit Log) ومعرفة من قام بالإجراءات.")
        ]
    },
    "defense": {
        "emoji": "🛡️",
        "title": "الحماية والدفاع",
        "menu_desc": "سيرفرك محمي 24/7 — حتى وأنت دايم",
        "desc": "منظومة الطوارئ القصوى ومكافحة الرايد والتخريب وعزل الحسابات المشبوهة:",
        "commands": [
            ("`/red_alert [reason]`", "إعلان حالة الطوارئ القصوى (DEFCON 1) وقفل كافة قنوات السيرفر فوراً."),
            ("`/cancel_red_alert`", "إلغاء حالة الإنذار الأحمر وفك القفل واستعادة النظام الطبيعي."),
            ("`/quarantine [user] [reason]`", "فرض الحجر الصحي الأمني على عضو مشبوه وعزله عن القنوات."),
            ("`/unquarantine [user]`", "رفع الحجر الصحي الأمني واستعادة الصلاحيات الطبيعية."),
            ("`/lockdown_server`", "إغلاق وقفل قنوات السيرفر لصد هجمات الرايد والدخول الجماعي."),
            ("`/unlock_server`", "فك إغلاق قنوات السيرفر بعد السيطرة على الهجوم وانتهاء الخطر."),
            ("`/security_audit`", "تدقيق أمني شامل لكافة إعدادات السيرفر والصلاحيات الحساسة."),
            ("`/whitelist [action] [target]`", "إدارة قائمة الاستثناء والحصانة من أنظمة الحماية والفلاتر.")
        ]
    },
    "utilities": {
        "emoji": "💎",
        "title": "المعلومات والأدوات",
        "menu_desc": "كل معلومة وكل أداة يومية تحتاجها — جاهزة",
        "desc": "أدوات نشر الإعلانات، الاستطلاعات، الاستعلام عن الأعضاء، والبلاغات السرية:",
        "commands": [
            ("`/announce [channel] [title] [message] [role_mention]`", "نشر إعلان رسمي منسق في قناة محددة مع منشن للرول."),
            ("`/poll [question] [options...] [duration]`", "إنشاء استطلاع رأي رسمي وتفاعلي للأعضاء مع مؤقت زمني للتصويت."),
            ("`/userinfo [user]`", "عرض بطاقة معلومات كاملة عن عضو (تاريخ الإنشاء، الانضمام، الرتب، والآيدي)."),
            ("`/serverinfo`", "استعراض ملف بيانات السيرفر وتاريخ تأسيسه وإجمالي الأعضاء والرتب."),
            ("`/faq [topic]`", "دليل الإجابات السريعة والأسئلة الشائعة والتعليمات التوجيهية."),
            ("`/report [target_user] [reason] [evidence_url]`", "إرسال بلاغ سري ومشفر عن مخالفة إلى إدارة السيرفر مع الأدلة."),
            ("`/help [category]`", "فتح لوحة الدليل الشامل واستعراض شرح وتفاصيل كافة الأوامر.")
        ]
    },
    "welcome": {
        "emoji": "✏️",
        "title": "الترحيب والاستقبال",
        "menu_desc": "أول انطباع يبقى بالذاكرة — ركب بأسلوبك أنت",
        "desc": "نظام الترحيب الفاخر بالأعضاء الجدد والعائدين مع إسناد الرتب التلقائية:",
        "commands": [
            ("`/test_welcome [rejoin]`", "معاينة واختبار بطاقة الترحيب الرخامية الفاخرة بشعار TS للأعضاء الجدد والعائدين.")
        ]
    },
    "leveling": {
        "emoji": "⚡",
        "title": "المستويات والبروفايل",
        "menu_desc": "كافئ النشيطين... وخلي السيرفر يدمن التفاعل",
        "desc": "نظام احتساب نقاط الخبرة (XP) والتفاعل وتوليد البطاقات الرسومية:",
        "commands": [
            ("`/rank [user]`", "استعراض بطاقة المستوى والخبرة الرسومية الفاخرة (PNG) ورتبة العضو بالسيرفر."),
            ("`/leaderboard`", "عرض لوحة الشرف التفاعلية لأعلى الأعضاء نشاطاً وتفاعلاً ومستويات بالسيرفر."),
            ("`/give_xp [user] [amount]`", "منح نقاط خبرة XP محددة لعضو كمكافأة تشجيعية (أدمن فقط)."),
            ("`/set_level [user] [level]`", "تعيين مستوى لفل محدد لعضو مباشرة في قاعدة البيانات."),
            ("`/reset_xp [user]`", "إعادة تصفير نقاط الخبرة والمستوى لعضو محدد.")
        ]
    },
    "ai_search": {
        "emoji": "🤖",
        "title": "الذكاء الاصطناعي والبحث",
        "menu_desc": "استخبارات فورية وبحث حي بالإنترنت مع تلخيص",
        "desc": "وحدة الاستخبارات والبحث الفوري وتحليل الأكواد بشخصية المساعد المنضبط:",
        "commands": [
            ("`/search [query]`", "بحث حي ومباشر في شبكة الإنترنت واستخراج الحقائق وتلخيصها بذكاء اصطناعي مع المصادر."),
            ("`/ask [question]`", "استشارة ومحاورة الذكاء الاصطناعي التكتيكي Neon AI مع ذاكرة سياقية للمحادثة."),
            ("`/explain_code [code]`", "تحليل الأكواد البرمجية، شرح المنطق، واكتشاف الأخطاء والثغرات وتقديم الحل الأمثل."),
            ("`/daily_intel`", "إصدار تقرير استخباراتي واستراتيجي شامل وفوري عن حالة السيرفر ونشاطه للقيادة."),
            ("`/report_bug [title] [description]`", "رفع تقرير فني سري عن وجود ثغرة أو خطأ برمجي للمطورين.")
        ]
    },
    "tickets": {
        "emoji": "🎫",
        "title": "التذاكر والدعم الفني",
        "menu_desc": "تذاكر آلية وأرشفة سجلات الدعم كاملة",
        "desc": "نظام تذاكر الدعم الفني المؤتمت بالذكاء الاصطناعي مع الأرشفة والتصعيد:",
        "commands": [
            ("`/ticket_panel`", "إنشاء لوحة زر فتح التذاكر التفاعلية في القناة الحالية لدعم الأعضاء."),
            ("`/close_ticket [ticket_channel]`", "إغلاق التذكرة فورياً وأرشفتها كملف HTML وإرسال التقرير لقناة السجلات.")
        ]
    },
    "setup": {
        "emoji": "👑",
        "title": "الإعدادات وتفويض الرتب",
        "menu_desc": "لوحة /setup وتخصيص قنوات وأنظمة السيرفر",
        "desc": "لوحات التحكم المركزية وضبط القنوات المخصصة وتفويض صلاحيات الرتب:",
        "commands": [
            ("`/setup`", "لوحة التحكم التفاعلية المركزية لضبط وتخصيص قنوات الترحيب والليفل واللوق والتذاكر."),
            ("`/role_selector`", "لوحة تفويض الرتب (المستوى الماكس للأدمن، المستوى التكتيكي للمشرفين، الحصانة)."),
            ("`/set_roles [admin_role] [mod_role]`", "تحديد رتبة الأدمنية ورتبة المشرفين المعترف بها للبوت."),
            ("`/view_config`", "عرض تقرير شامل بجميع إعدادات وقنوات ورولات البوت المضبوطة في السيرفر."),
            ("`/role_menu [title] [channel]`", "إنشاء لوحة الرتب التفاعلية التلقائية للأعضاء (Reaction Roles).")
        ]
    },
    "stats": {
        "emoji": "📊",
        "title": "الإحصائيات والنسخ الاحتياطي",
        "menu_desc": "تقارير شاملة، عتاد الخادم، وباك أب مشفر",
        "desc": "مراقبة الأداء، التقارير الدورية، عتاد الخادم، وتأمين السيرفر بالنسخ الاحتياطي:",
        "commands": [
            ("`/stats`", "عرض إحصائيات السيرفر التفاعلية ومعدلات النشاط وأكثر القنوات تفاعلاً."),
            ("`/cold_report`", "إرسال التقرير الإحصائي الدوري المفصل فورياً إلى قناة التقارير المخصصة."),
            ("`/backup_create`", "إنشاء نسخة احتياطية مشفرة وفورية لهيكل السيرفر (قنوات، رتب، إعدادات)."),
            ("`/backup_restore [backup_id]`", "استعادة هيكل وقنوات ورتب السيرفر من نسخة احتياطية سابقة."),
            ("`/server_snapshot`", "أخذ لقطة سريعة لهيكل السيرفر وحفظها للرجوع إليها في أي وقت."),
            ("`/db_export`", "تصدير قاعدة بيانات السيرفر كاملة كملف JSON آمن للقيادة."),
            ("`/health`", "فحص صحة البوت، سرعة الاستجابة (Ping)، وثبات الاتصال بالبوابة."),
            ("`/hardware`", "تقرير مفصل عن موارد السيرفر الفيزيائي (المعالج CPU، الذاكرة RAM، والمساحة).")
        ]
    }
}


class LonaStyleSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for cat_key, data in HELP_DATABASE.items():
            options.append(discord.SelectOption(
                label=data["title"],
                value=cat_key,
                description=data["menu_desc"][:100],
                emoji=data["emoji"]
            ))
        super().__init__(
            placeholder="📁  وش تبي تعرف عن نيون؟",
            options=options,
            min_values=1,
            max_values=1,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        cat_key = self.values[0]
        data = HELP_DATABASE.get(cat_key)
        if not data:
            return

        embed = build_category_embed(cat_key, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self.view)


class LonaStyleHelpView(discord.ui.View):
    def __init__(self, bot_id: int):
        super().__init__(timeout=300)
        self.add_item(LonaStyleSelect())

        dashboard_url = "https://loop-production-9e4f.up.railway.app/"
        self.add_item(discord.ui.Button(
            label="الداشبورد",
            emoji="💎",
            url=dashboard_url,
            style=discord.ButtonStyle.link,
            row=1
        ))
        
        invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot%20applications.commands"
        self.add_item(discord.ui.Button(
            label="دعوة نيون",
            emoji="🌙",
            url=invite_url,
            style=discord.ButtonStyle.link,
            row=1
        ))

    @discord.ui.button(label="الفهرس", style=discord.ButtonStyle.secondary, emoji="💖", row=1)
    async def show_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_overview_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


def build_overview_embed(guild: Optional[discord.Guild]) -> discord.Embed:
    total_cmds = sum(len(c["commands"]) for c in HELP_DATABASE.values())
    desc = (
        f"⚡ **إدارة بـ {total_cmds} أمر، حماية تكتيكية، واستخبارات كاملة.**\n\n"
        f"> **نيون** مساعد تكتيكي متطور مبني بأعلى درجات الانضباط لإدارة وحماية السيرفر.\n\n"
        f"👇 **كل المميزات تضبط بسهولة من الداشبورد — جرب الزر تحت** 💻"
    )
    embed = discord.Embed(
        description=desc,
        color=SLATE_DARK
    )
    if guild and guild.icon:
        embed.set_author(name=f"Neon Tactical Engine • {guild.name}", icon_url=guild.icon.url)
    else:
        embed.set_author(name="Neon Tactical Engine")
    return embed


def build_category_embed(cat_key: str, guild: Optional[discord.Guild]) -> discord.Embed:
    cat = HELP_DATABASE[cat_key]
    embed = discord.Embed(
        title=f"{cat['emoji']}  {cat['title']}",
        description=f"*{cat['desc']}*\n",
        color=SLATE_DARK
    )
    for cmd_syntax, cmd_expl in cat["commands"]:
        embed.add_field(
            name=f"📌 {cmd_syntax}",
            value=f"└ {cmd_expl}",
            inline=False
        )
    if guild and guild.icon:
        embed.set_footer(text=f"{guild.name} • عدد الأوامر: {len(cat['commands'])} أمر", icon_url=guild.icon.url)
    else:
        embed.set_footer(text=f"عدد الأوامر: {len(cat['commands'])} أمر")
    return embed


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="دليل الأوامر التفاعلي وشرح كافة مميزات نيون")
    @app_commands.describe(category="اختر قسماً محدداً لعرض أوامره مباشرة (اختياري)")
    @app_commands.choices(category=[
        app_commands.Choice(name="⚔️ الإدارة والإشراف (13 أمر)", value="moderation"),
        app_commands.Choice(name="🛡️ الحماية والدفاع (8 أوامر)", value="defense"),
        app_commands.Choice(name="💎 المعلومات والأدوات (7 أوامر)", value="utilities"),
        app_commands.Choice(name="✏️ الترحيب والاستقبال (1 أمر)", value="welcome"),
        app_commands.Choice(name="⚡ المستويات والبروفايل (5 أوامر)", value="leveling"),
        app_commands.Choice(name="🤖 الذكاء الاصطناعي والبحث (5 أوامر)", value="ai_search"),
        app_commands.Choice(name="🎫 التذاكر والدعم الفني (2 أوامر)", value="tickets"),
        app_commands.Choice(name="👑 الإعدادات وتفويض الرتب (5 أوامر)", value="setup"),
        app_commands.Choice(name="📊 الإحصائيات والنسخ الاحتياطي (8 أوامر)", value="stats"),
    ])
    async def help_command(self, interaction: discord.Interaction, category: Optional[str] = None):
        view = LonaStyleHelpView(self.bot.user.id if self.bot.user else 0)
        if category and category in HELP_DATABASE:
            embed = build_category_embed(category, interaction.guild)
        else:
            embed = build_overview_embed(interaction.guild)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
