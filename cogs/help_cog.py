import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from utils.embeds import create_neon_embed

GOLD_COLOR = 0xD4AF37

# الدليل الشامل لجميع أوامر البوت الـ 53 مصنفة حسب الفئات
HELP_DATABASE = {
    "moderation": {
        "title": "🛡️ الإشراف والعقوبات والمراقبة (Moderation)",
        "desc": "حزمة الأدوات التأديبية والإشرافية الميدانية للتحكم في الأعضاء وتنظيف القنوات:",
        "commands": [
            ("`/ban [user] [reason] [delete_days] [dm_notify]`", "حظر العضو نهائياً من السيرفر مع إمكانية مسح رسائله السابقة وإشعاره بالخاص."),
            ("`/unban [user_id] [reason]`", "إلغاء حظر عضو محظور مسبقاً باستخدام الآيدي الخاص به."),
            ("`/kick [user] [reason] [dm_notify]`", "طرد العضو من السيرفر مع إمكانية إرسال سبب الطرد له في الخاص."),
            ("`/timeout [user] [minutes] [reason] [dm_notify]`", "كتم مؤقت للعضو (Timeout) لمدة محددة بالدقائق لمنعه من الكتابة والتحدث."),
            ("`/remove_timeout [user] [reason]`", "فك الكتم المؤقت فوراً عن العضو وإعادة صلاحيات التفاعل له."),
            ("`/warn [user] [reason] [dm_notify]`", "تسجيل تحذير رسمي بحق العضو وحفظه في سجله التأديبي مع إشعار خاص."),
            ("`/strike [user] [reason]`", "تسجيل إنذار في السجل التراكمي (تطبيق عقوبات تصاعدية تلقائياً عند تكرار المخالفات)."),
            ("`/strikes_list [user]`", "عرض قائمة الإنذارات النشطة بحق عضو محدد وتاريخ كل إنذار والمشرف الذي سجله."),
            ("`/clear [amount]`", "مسح جماعي سريع لعدد محدد من الرسائل في القناة الحالية (حتى 100 رسالة)."),
            ("`/history [user]`", "استعراض السجل التأديبي والأمني الكامل للعضو وجميع القضايا والعقوبات السابقة."),
            ("`/case [case_id]`", "الاستعلام عن تفاصيل قضية إدارية محددة ومعرفة المشرف والسبب والإجراء المتخذ."),
            ("`/scan_user [user]`", "فحص أمني وتحليلي لحساب العضو (عمر الحساب، تاريخ الانضمام، الرتب، ونسبة الخطورة)."),
            ("`/audit [count]`", "مراقبة حية لسجل أحداث السيرفر (Audit Log) لمعرفة من قام بالطرد/الحظر/الكتم/التعديل.")
        ]
    },
    "defense": {
        "title": "🚨 الدفاع السيبراني والطوارئ (Cyber Defense)",
        "desc": "منظومة الطوارئ القصوى ومكافحة الرايد والتخريب وعزل الحسابات المشبوهة:",
        "commands": [
            ("`/red_alert [reason]`", "إعلان حالة الطوارئ القصوى (DEFCON 1) وقفل كافة قنوات السيرفر فوراً وتعطيل الدعوات."),
            ("`/cancel_red_alert`", "إلغاء حالة الإنذار الأحمر وفك القفل الشامل واستعادة النظام الطبيعي للسيرفر."),
            ("`/quarantine [user] [reason]`", "فرض الحجر الصحي الأمني الفوري على عضو مشبوه وعزله عن قنوات السيرفر."),
            ("`/unquarantine [user]`", "رفع الحجر الصحي الأمني عن العضو واستعادة رتب وصلاحيات التفاعل الطبيعية."),
            ("`/lockdown_server`", "إغلاق وقفل قنوات السيرفر لصد هجمات الرايد والدخول الجماعي المريب."),
            ("`/unlock_server`", "فك إغلاق قنوات السيرفر بعد السيطرة على الهجوم وانتهاء الخطر."),
            ("`/security_audit`", "تدقيق أمني شامل لكافة إعدادات السيرفر، الصلاحيات الخطيرة، والرتب الحساسة."),
            ("`/whitelist [action] [target]`", "إدارة قائمة الاستثناء والحصانة من أنظمة الحماية والفلاتر الذكية.")
        ]
    },
    "ai_search": {
        "title": "🤖 الذكاء الاصطناعي والبحث الحي (AI & Web Search)",
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
        "title": "🎫 التذاكر والدعم الفني الذكي (AI Support Tickets)",
        "desc": "نظام تذاكر الدعم الفني المؤتمت بالذكاء الاصطناعي مع الأرشفة والتصعيد:",
        "commands": [
            ("`/ticket_panel`", "إنشاء لوحة زر فتح التذاكر التفاعلية في القناة الحالية لدعم الأعضاء."),
            ("`/close_ticket [ticket_channel]`", "إغلاق التذكرة فورياً وأرشفتها كملف HTML وإرسال التقرير لقناة السجلات.")
        ]
    },
    "leveling": {
        "title": "⭐ المستويات وبطاقات الرانك (Leveling & XP)",
        "desc": "نظام احتساب نقاط الخبرة (XP) والتفاعل وتوليد البطاقات الرسومية:",
        "commands": [
            ("`/rank [user]`", "استعراض بطاقة المستوى والخبرة الرسومية الفاخرة (PNG) ورتبة العضو بالسيرفر."),
            ("`/leaderboard`", "عرض لوحة الشرف التفاعلية لأعلى الأعضاء نشاطاً وتفاعلاً ومستويات بالسيرفر."),
            ("`/give_xp [user] [amount]`", "منح نقاط خبرة XP محددة لعضو كمكافأة تشجيعية (أدمن فقط)."),
            ("`/set_level [user] [level]`", "تعيين مستوى لفل محدد لعضو مباشرة في قاعدة البيانات."),
            ("`/reset_xp [user]`", "إعادة تصفير نقاط الخبرة والمستوى لعضو محدد.")
        ]
    },
    "setup": {
        "title": "⚙️ الإعدادات المركزية وتفويض الرتب (Setup & Roles)",
        "desc": "لوحات التحكم المركزية وضبط القنوات المخصصة وتفويض صلاحيات الرتب:",
        "commands": [
            ("`/setup`", "لوحة التحكم التفاعلية المركزية لضبط وتخصيص قنوات الترحيب والليفل واللوق والتذاكر."),
            ("`/role_selector`", "لوحة تفويض الرتب (المستوى الماكس للأدمن، المستوى التكتيكي للمشرفين، الحصانة)."),
            ("`/set_roles [admin_role] [mod_role]`", "تحديد رتبة الأدمنية ورتبة المشرفين المعترف بها للبوت."),
            ("`/view_config`", "عرض تقرير شامل بجميع إعدادات وقنوات ورولات البوت المضبوطة في السيرفر."),
            ("`/role_menu [title] [channel]`", "إنشاء لوحة الرتب التفاعلية التلقائية للأعضاء (Reaction Roles)."),
            ("`/test_welcome [rejoin]`", "معاينة واختبار بطاقة الترحيب الرخامية الفاخرة بشعار TS للأعضاء الجدد والعائدين.")
        ]
    },
    "stats": {
        "title": "📊 الإحصائيات والنسخ الاحتياطي (Stats & Backup)",
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
    },
    "utilities": {
        "title": "🔧 الأدوات والمرافق العامة (General Utilities)",
        "desc": "أدوات نشر الإعلانات، الاستطلاعات، الاستعلام عن الأعضاء، والبلاغات السرية:",
        "commands": [
            ("`/announce [channel] [title] [message] [role_mention]`", "نشر إعلان رسمي منسق في قناة محددة مع منشن للرول."),
            ("`/poll [question] [options...] [duration]`", "إنشاء استطلاع رأي رسمي وتفاعلي للأعضاء مع مؤقت زمني للتصويت."),
            ("`/userinfo [user]`", "عرض بطاقة معلومات كاملة عن عضو (تاريخ الإنشاء، الانضمام، الرتب، والآيدي)."),
            ("`/serverinfo`", "استعراض ملف بيانات السيرفر وتاريخ تأسيسه وإجمالي الأعضاء والرتب والقنوات."),
            ("`/faq [topic]`", "دليل الإجابات السريعة والأسئلة الشائعة والتعليمات التوجيهية للأعضاء."),
            ("`/report [target_user] [reason] [evidence_url]`", "إرسال بلاغ سري ومشفر عن مخالفة إلى إدارة السيرفر مع الأدلة."),
            ("`/help [category]`", "فتح هذا الدليل الشامل واستعراض شرح وتفاصيل كافة أوامر البوت الـ 53.")
        ]
    }
}


class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛡️ الإشراف والعقوبات والمراقبة", value="moderation", description="أوامر البان، الكيك، الكتم، الإنذارات، والمسح (13 أمر)"),
            discord.SelectOption(label="🚨 الدفاع السيبراني والطوارئ", value="defense", description="الإنذار الأحمر، الحجر الصحي، وقفل الرايد (8 أوامر)"),
            discord.SelectOption(label="🤖 الذكاء الاصطناعي والبحث الحي", value="ai_search", description="البحث بالنت، استشارة AI، وتحليل الأكواد (5 أوامر)"),
            discord.SelectOption(label="🎫 التذاكر والدعم الفني الذكي", value="tickets", description="لوحة التذاكر، الأرشفة، والدعم الفني (2 أوامر)"),
            discord.SelectOption(label="⭐ المستويات وبطاقات الرانك", value="leveling", description="بطاقة الرانك، الليدربورد، وتعديل XP (5 أوامر)"),
            discord.SelectOption(label="⚙️ الإعدادات وتفويض الرتب", value="setup", description="لوحة /setup، تفويض الرتب، والرتب التفاعلية (6 أوامر)"),
            discord.SelectOption(label="📊 الإحصائيات والنسخ الاحتياطي", value="stats", description="التقارير، النسخ الاحتياطي، وفحص العتاد (8 أوامر)"),
            discord.SelectOption(label="🔧 الأدوات والمرافق العامة", value="utilities", description="الإعلانات، الاستطلاعات، البلاغات، والمعلومات (7 أوامر)"),
        ]
        super().__init__(placeholder="اختر فئة الأوامر لعرض تفاصيلها وشرحها الكامل...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        cat_key = self.values[0]
        data = HELP_DATABASE.get(cat_key)
        if not data:
            return

        embed = build_category_embed(cat_key, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(HelpCategorySelect())

    @discord.ui.button(label="📜 الفهرس الشامل", style=discord.ButtonStyle.primary, emoji="👑", row=1)
    async def show_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_overview_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


def build_overview_embed(guild: Optional[discord.Guild]) -> discord.Embed:
    total_cmds = sum(len(c["commands"]) for c in HELP_DATABASE.values())
    desc = (
        f"مرحباً بك في **الدليل الاستراتيجي الشامل لأوامر Neon Engine v2.0**.\n"
        f"يحتوي البوت على **{total_cmds} أمر Slash تفاعلي** مبرمج بالكامل وبدون أي نواقص.\n\n"
        f"`──────── الأقسام والفئات المتاحة ────────`\n"
        f"**1. 🛡️ الإشراف والعقوبات:** `13` أمر (طرد، حظر، كتم، إنذارات، ومراقبة)\n"
        f"**2. 🚨 الدفاع السيبراني:** `8` أوامر (الإنذار الأحمر، الحجر، والرايد)\n"
        f"**3. 🤖 الذكاء الاصطناعي:** `5` أوامر (بحث حي بالإنترنت، استشارة، وأكواد)\n"
        f"**4. 🎫 التذاكر والدعم:** `2` أوامر (تذاكر ذكية وأرشفة HTML)\n"
        f"**5. ⭐ المستويات والخبرة:** `5` أوامر (بطاقات رانك وليدربورد)\n"
        f"**6. ⚙️ الإعدادات والرتب:** `6` أوامر (لوحة /setup وتفويض الصلاحيات)\n"
        f"**7. 📊 الإحصائيات والنسخ:** `8` أوامر (تقارير، عتاد، وباك أب مشفر)\n"
        f"**8. 🔧 الأدوات العامة:** `7` أوامر (إعلانات، استطلاعات، وبلاغات)\n\n"
        f"`──────── طريقة التصفح ────────`\n"
        f"اختر أي فئة من القائمة المنسدلة أدناه لعرض شرح كل أمر ومعاملاته وصلاحياته بالتفصيل."
    )
    embed = discord.Embed(
        title="❖ الدليل الاستراتيجي الشامل | Neon Command Matrix ❖",
        description=desc,
        color=GOLD_COLOR
    )
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"إجمالي الأوامر: {total_cmds} أمر • Neon Engine v2.0 Tactical System")
    return embed


def build_category_embed(cat_key: str, guild: Optional[discord.Guild]) -> discord.Embed:
    cat = HELP_DATABASE[cat_key]
    embed = discord.Embed(
        title=f"❖ {cat['title']} ❖",
        description=f"*{cat['desc']}*\n\n`──────── قائمة الأوامر والشرح المفصل ────────`",
        color=GOLD_COLOR
    )
    for cmd_syntax, cmd_expl in cat["commands"]:
        embed.add_field(
            name=f"📌 {cmd_syntax}",
            value=f"└ {cmd_expl}",
            inline=False
        )
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"عدد الأوامر في هذا القسم: {len(cat['commands'])} • Neon Engine v2.0")
    return embed


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="الدليل الاستراتيجي الشامل وشرح تفصيلي لكافة أوامر البوت الـ 53")
    @app_commands.describe(category="اختر قسماً محدداً لعرض أوامره مباشرة (اختياري)")
    @app_commands.choices(category=[
        app_commands.Choice(name="🛡️ الإشراف والعقوبات (13 أمر)", value="moderation"),
        app_commands.Choice(name="🚨 الدفاع السيبراني والطوارئ (8 أوامر)", value="defense"),
        app_commands.Choice(name="🤖 الذكاء الاصطناعي والبحث الحي (5 أوامر)", value="ai_search"),
        app_commands.Choice(name="🎫 التذاكر والدعم الفني (2 أوامر)", value="tickets"),
        app_commands.Choice(name="⭐ المستويات وبطاقات الرانك (5 أوامر)", value="leveling"),
        app_commands.Choice(name="⚙️ الإعدادات وتفويض الرتب (6 أوامر)", value="setup"),
        app_commands.Choice(name="📊 الإحصائيات والنسخ الاحتياطي (8 أوامر)", value="stats"),
        app_commands.Choice(name="🔧 الأدوات والمرافق العامة (7 أوامر)", value="utilities"),
    ])
    async def help_command(self, interaction: discord.Interaction, category: Optional[str] = None):
        view = HelpMainView()
        if category and category in HELP_DATABASE:
            embed = build_category_embed(category, interaction.guild)
        else:
            embed = build_overview_embed(interaction.guild)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
