import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig
from core.permissions import is_admin
from core.strings import Strings
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision


# ═══════════════════════════════════════════════════
# مكون اختيار القنوات العام - يُستخدم في كل الأنظمة
# ═══════════════════════════════════════════════════

class ChannelSetSelect(discord.ui.ChannelSelect):
    """ChannelSelect عام يحفظ القناة المختارة في العمود المحدد من GuildConfig."""
    def __init__(self, db_field: str, placeholder: str, ch_types=None, row: int = 0):
        super().__init__(
            placeholder=placeholder,
            channel_types=ch_types or [discord.ChannelType.text],
            min_values=1, max_values=1, row=row
        )
        self.db_field = db_field

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = result.scalars().first()
            if config:
                setattr(config, self.db_field, channel.id)
                await session.commit()
        embed = create_neon_embed("تم الضبط", f"تم تحديد القناة: {channel.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CategorySetSelect(discord.ui.ChannelSelect):
    """ChannelSelect لاختيار فئة (Category)."""
    def __init__(self, db_field: str, placeholder: str, row: int = 0):
        super().__init__(
            placeholder=placeholder,
            channel_types=[discord.ChannelType.category],
            min_values=1, max_values=1, row=row
        )
        self.db_field = db_field

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = result.scalars().first()
            if config:
                setattr(config, self.db_field, channel.id)
                await session.commit()
        embed = create_neon_embed("تم الضبط", f"تم تحديد الفئة: {channel.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RoleSetSelect(discord.ui.RoleSelect):
    """RoleSelect عام يحفظ الرول في العمود المحدد."""
    def __init__(self, db_field: str, placeholder: str, row: int = 0):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, row=row)
        self.db_field = db_field

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = result.scalars().first()
            if config:
                setattr(config, self.db_field, role.id)
                await session.commit()
        embed = create_neon_embed("تم الضبط", f"تم تحديد الرول: {role.mention}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════════
# الشاشة الرئيسية للإعدادات - Main Setup Dashboard
# ═══════════════════════════════════════════════════

class SetupDashboardView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="اختر النظام الذي تريد ضبطه...",
        options=[
            discord.SelectOption(label="الحماية والأمان", value="protection", emoji="🛡️", description="Anti-Raid / Anti-Nuke / Anti-Spam"),
            discord.SelectOption(label="التذاكر والدعم الفني", value="tickets", emoji="🎫", description="فئة التذاكر وإعداداتها"),
            discord.SelectOption(label="المستويات والخبرة", value="leveling", emoji="⭐", description="قناة الليفل أب ونظام XP"),
            discord.SelectOption(label="الترحيب والوداع", value="welcome", emoji="👋", description="قنوات الترحيب والمغادرة والأوتو رول"),
            discord.SelectOption(label="السجلات والتدقيق", value="logging", emoji="📋", description="قناة سجلات الأحداث"),
            discord.SelectOption(label="الإحصائيات والتقارير", value="stats", emoji="📊", description="قناة التقارير الدورية"),
            discord.SelectOption(label="الذكاء الاصطناعي", value="ai", emoji="🤖", description="تفعيل/تعطيل Neon AI"),
            discord.SelectOption(label="بروتوكول الصمت", value="silent", emoji="🔇", description="إيقاف جميع التفاعلات"),
            discord.SelectOption(label="تفويض الرتب والصلاحيات", value="roles", emoji="👑", description="ضبط رتب الماكس والتكتيكي والحصانة"),
        ]
    )
    async def select_system(self, interaction: discord.Interaction, select_menu: discord.ui.Select):
        system = select_menu.values[0]

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == self.guild_id))
            config = result.scalars().first()
            if not config:
                config = GuildConfig(guild_id=self.guild_id)
                session.add(config)
                await session.commit()
                await session.refresh(config)

        if system == "protection":
            view = ProtectionSettingsView(self.guild_id, config)
            embed = _build_system_embed("الحماية والأمان", config, "protection")
        elif system == "tickets":
            view = TicketsSettingsView(self.guild_id, config)
            embed = _build_system_embed("التذاكر والدعم الفني", config, "tickets")
        elif system == "leveling":
            view = LevelingSettingsView(self.guild_id, config)
            embed = _build_system_embed("المستويات والخبرة", config, "leveling")
        elif system == "welcome":
            view = WelcomeSettingsView(self.guild_id, config)
            embed = _build_system_embed("الترحيب والوداع", config, "welcome")
        elif system == "logging":
            view = LoggingSettingsView(self.guild_id, config)
            embed = _build_system_embed("السجلات والتدقيق", config, "logging")
        elif system == "stats":
            view = StatsSettingsView(self.guild_id, config)
            embed = _build_system_embed("الإحصائيات والتقارير", config, "stats")
        elif system == "ai":
            view = ToggleOnlyView(self.guild_id, "ai")
            embed = _build_system_embed("الذكاء الاصطناعي", config, "ai")
        elif system == "silent":
            view = ToggleOnlyView(self.guild_id, "silent")
            embed = _build_system_embed("بروتوكول الصمت", config, "silent")
        elif system == "roles":
            from cogs.role_selector import RoleSelectorView
            view = RoleSelectorView()
            desc = (
                "استخدم القوائم أدناه لتفويض الرتب والصلاحيات:\n"
                "• **المستوى الماكس:** للأوامر الخطيرة والإعدادات والقفل.\n"
                "• **المستوى التكتيكي:** لأوامر الإشراف والعقوبات.\n"
                "• **مستوى الحصانة:** للإعفاء من الفلاتر."
            )
            embed = create_neon_embed("تفويض الرتب والصلاحيات", desc, color=0x5865F2)
        else:
            return

        await interaction.response.edit_message(embed=embed, view=view)


# ═══════════════════════════════════════════════════
# بناء الـ Embed لكل نظام مع عرض القناة المخصصة
# ═══════════════════════════════════════════════════

def _get_status(config, system: str) -> str:
    if system == "silent":
        return "مفعّل" if config.silent_protocol else "معطّل"
    field = f"{system}_enabled"
    return "مفعّل" if getattr(config, field, False) else "معطّل"


def _ch(val):
    return f"<#{val}>" if val else "`غير محدد`"

def _rl(val):
    return f"<@&{val}>" if val else "`غير محدد`"


def _build_system_embed(title: str, config, system: str) -> discord.Embed:
    status = _get_status(config, system)
    status_icon = "`ON`" if status == "مفعّل" else "`OFF`"

    # عرض القنوات المخصصة لكل نظام
    channels = ""
    if system == "logging":
        channels = f"\n📋 **قناة السجلات:** {_ch(config.log_channel_id)}"
    elif system == "welcome":
        channels = (
            f"\n👋 **قناة الترحيب:** {_ch(config.welcome_channel_id)}"
            f"\n🏷️ **رول انضمام تلقائي:** {_rl(config.auto_role_id)}"
        )
    elif system == "tickets":
        channels = f"\n🎫 **فئة التذاكر:** {_ch(config.ticket_category_id)}"
    elif system == "stats":
        channels = f"\n📊 **قناة التقارير:** {_ch(config.report_channel_id)}"
    elif system == "leveling":
        channels = f"\n⭐ **قناة الليفل أب:** {_ch(getattr(config, 'leveling_channel_id', None))}"

    desc = (
        f"**الحالة:** {status_icon} {status}\n"
        f"{channels}\n\n"
        f"استخدم القوائم والأزرار أدناه لضبط الإعدادات."
    )
    return create_neon_embed(f"إعدادات | {title}", desc)


# ═══════════════════════════════════════════════════
# زر التفعيل/التعطيل العام - Generic Toggle
# ═══════════════════════════════════════════════════

class ToggleOnlyView(discord.ui.View):
    def __init__(self, guild_id: int, system: str):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.system = system

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, self.system)

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# إعدادات الحماية - Protection Settings
# ═══════════════════════════════════════════════════

class ProtectionSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, config):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, "protection")

    @discord.ui.select(
        placeholder="حساسية Anti-Raid (عدد الانضمام قبل Lockdown)...",
        options=[
            discord.SelectOption(label="5 أعضاء / 10 ثوانٍ (عالية)", value="5"),
            discord.SelectOption(label="7 أعضاء / 10 ثوانٍ (افتراضي)", value="7"),
            discord.SelectOption(label="10 أعضاء / 10 ثوانٍ (منخفضة)", value="10"),
            discord.SelectOption(label="15 عضو / 10 ثوانٍ (كبيرة)", value="15"),
        ]
    )
    async def raid_sensitivity(self, interaction: discord.Interaction, select_menu: discord.ui.Select):
        val = select_menu.values[0]
        embed = create_neon_embed("تم الضبط", f"حساسية Anti-Raid: `{val}` أعضاء / 10 ثوانٍ.")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# إعدادات التذاكر - Tickets (تخصيص فئة القناة)
# ═══════════════════════════════════════════════════

class TicketsSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, config):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.add_item(CategorySetSelect("ticket_category_id", "اختر فئة (Category) لقنوات التذاكر...", row=0))

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡", row=2)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, "tickets")

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# إعدادات المستويات - Leveling (تخصيص قناة الليفل أب)
# ═══════════════════════════════════════════════════

class LevelingSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, config):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.add_item(ChannelSetSelect("leveling_channel_id", "اختر قناة إشعارات الليفل أب...", row=0))

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡", row=2)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, "leveling")

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# إعدادات الترحيب - Welcome (3 قنوات + رول)
# ═══════════════════════════════════════════════════

class WelcomeSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, config):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.add_item(ChannelSetSelect("welcome_channel_id", "اختر قناة الترحيب (Welcome)...", row=0))
        self.add_item(RoleSetSelect("auto_role_id", "اختر رول الانضمام التلقائي (Auto-Role)...", row=1))

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡", row=3)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, "welcome")

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀", row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# إعدادات السجلات - Logging (تخصيص قناة السجلات)
# ═══════════════════════════════════════════════════

class LoggingSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, config):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.add_item(ChannelSetSelect("log_channel_id", "اختر قناة السجلات (Audit Log)...", row=0))

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡", row=2)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, "logging")

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# إعدادات التقارير - Stats (تخصيص قناة التقارير)
# ═══════════════════════════════════════════════════

class StatsSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, config):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.add_item(ChannelSetSelect("report_channel_id", "اختر قناة التقارير الدورية...", row=0))

    @discord.ui.button(label="تفعيل / تعطيل", style=discord.ButtonStyle.primary, emoji="⚡", row=2)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _toggle_system(interaction, self.guild_id, "stats")

    @discord.ui.button(label="رجوع", style=discord.ButtonStyle.secondary, emoji="◀", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back(interaction, self.guild_id)


# ═══════════════════════════════════════════════════
# دوال مساعدة مشتركة
# ═══════════════════════════════════════════════════

async def _toggle_system(interaction: discord.Interaction, guild_id: int, system: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        config = result.scalars().first()

        if system == "silent":
            config.silent_protocol = not config.silent_protocol
            status = config.silent_protocol
        else:
            field_name = f"{system}_enabled"
            current = getattr(config, field_name, False)
            setattr(config, field_name, not current)
            status = not current

        await session.commit()

    status_text = "مفعّل" if status else "معطّل"
    embed = create_neon_embed(
        "تم تحديث الإعدادات",
        f"**النظام:** `{system.upper()}`\n**الحالة:** `{status_text}`",
        color=0x50FA7B if status else 0xFF5555
    )
    await interaction.response.edit_message(embed=embed, view=None)

    await log_decision(
        interaction.guild,
        command=f"/setup toggle {system}",
        check_result="صلاحيات الإدارة مؤكدة",
        execution_step=f"تحديث قاعدة البيانات لـ {system}",
        outcome=f"الحالة الجديدة: {status_text}"
    )


async def _go_back(interaction: discord.Interaction, guild_id: int):
    embed = _build_dashboard_embed(interaction.guild)
    view = SetupDashboardView(guild_id)
    await interaction.response.edit_message(embed=embed, view=view)


def _build_dashboard_embed(guild) -> discord.Embed:
    desc = (
        "اختر نظاماً من القائمة لضبط **القناة المخصصة** له وتفعيله/تعطيله.\n\n"
        "**1.** الحماية والأمان\n"
        "**2.** التذاكر — تحديد فئة التذاكر\n"
        "**3.** المستويات — تحديد قناة الليفل أب\n"
        "**4.** الترحيب — تحديد قنوات الترحيب والوداع + الأوتو رول\n"
        "**5.** السجلات — تحديد قناة الـ Logs\n"
        "**6.** التقارير — تحديد قناة التقارير\n"
        "**7.** الذكاء الاصطناعي — تفعيل/تعطيل\n"
        "**8.** بروتوكول الصمت — تفعيل/تعطيل\n"
        "**9.** تفويض الرتب — ماكس / تكتيكي / حصانة"
    )
    embed = create_neon_embed("لوحة التحكم | Neon Setup", desc, color=0x5865F2)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    return embed


# ═══════════════════════════════════════════════════
# الـ Cog الرئيسي - Setup Cog
# ═══════════════════════════════════════════════════

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="لوحة التحكم لإعدادات Neon وتخصيص القنوات")
    async def setup_cmd(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = result.scalars().first()
            if not config:
                config = GuildConfig(guild_id=interaction.guild_id)
                session.add(config)
                await session.commit()

        embed = _build_dashboard_embed(interaction.guild)
        view = SetupDashboardView(interaction.guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ═══════════════════════════════════════════════════
    # أمر تحديد رتبة الأدمنية والمشرفين
    # ═══════════════════════════════════════════════════

    @app_commands.command(name="set_roles", description="تحديد رتبة الأدمنية ورتبة المشرفين للبوت")
    @app_commands.describe(
        admin_role="الرول الذي سيتم اعتباره أدمن كامل الصلاحيات للبوت",
        mod_role="الرول الذي سيتم اعتباره مشرف بصلاحيات إدارية محدودة"
    )
    async def set_roles(
        self,
        interaction: discord.Interaction,
        admin_role: discord.Role = None,
        mod_role: discord.Role = None
    ):
        # فقط مالك السيرفر أو من لديه صلاحية Administrator الأصلية يستطيع تعيين الرولات
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message(
                "هذا الأمر مقتصر على مالك السيرفر أو من يملك صلاحية `Administrator` الأصلية فقط.",
                ephemeral=True
            )
            return

        if not admin_role and not mod_role:
            await interaction.response.send_message("يجب تحديد رول واحد على الأقل (admin_role أو mod_role).", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = result.scalars().first()
            if not config:
                config = GuildConfig(guild_id=interaction.guild_id)
                session.add(config)

            changes = []
            if admin_role:
                config.admin_role_id = admin_role.id
                changes.append(f"**رتبة الأدمن:** {admin_role.mention}")
            if mod_role:
                config.mod_role_id = mod_role.id
                changes.append(f"**رتبة المشرف:** {mod_role.mention}")

            await session.commit()

        changes_text = "\n".join(changes)
        embed = create_neon_embed(
            "تعيين رتب الإدارة",
            f"{changes_text}\n\nالأعضاء بهذه الرتب سيتم الاعتراف بهم في أوامر Neon الإدارية.",
            color=0x50FA7B
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command=f"/set_roles admin={admin_role.id if admin_role else 'N/A'} mod={mod_role.id if mod_role else 'N/A'}",
            check_result="صلاحيات المالك/الأدمن مؤكدة",
            execution_step="تحديث رولات الإدارة في قاعدة البيانات",
            outcome=f"تم تعيين الرولات: {changes_text}"
        )

    @app_commands.command(name="view_config", description="عرض جميع إعدادات البوت الحالية للسيرفر")
    async def view_config(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(Strings.ERROR_PERMISSIONS, ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
            config = result.scalars().first()

        if not config:
            await interaction.response.send_message("لم يتم ضبط إعدادات السيرفر بعد. استخدم `/setup`.", ephemeral=True)
            return

        def s(val):
            return "`ON`" if val else "`OFF`"

        desc = (
            f"`════════ الأنظمة ════════`\n"
            f"الحماية: {s(config.protection_enabled)} | الإدارة: {s(config.moderation_enabled)}\n"
            f"التذاكر: {s(config.tickets_enabled)} | المستويات: {s(config.leveling_enabled)}\n"
            f"الترحيب: {s(config.welcome_enabled)} | السجلات: {s(config.logging_enabled)}\n"
            f"AI: {s(config.ai_enabled)} | الإحصائيات: {s(config.stats_enabled)}\n"
            f"الصمت: {s(config.silent_protocol)}\n\n"
            f"`════════ القنوات ════════`\n"
            f"السجلات: {_ch(config.log_channel_id)}\n"
            f"الترحيب: {_ch(config.welcome_channel_id)} | الوداع: {_ch(config.leave_channel_id)}\n"
            f"الليفل أب: {_ch(getattr(config, 'leveling_channel_id', None))}\n"
            f"التقارير: {_ch(config.report_channel_id)}\n"
            f"الروم الصوتي المؤقت: {_ch(getattr(config, 'temp_voice_channel_id', None))}\n"
            f"فئة التذاكر: {_ch(config.ticket_category_id)}\n\n"
            f"`════════ الرولات ════════`\n"
            f"رتبة الأدمن: {_rl(config.admin_role_id)}\n"
            f"رتبة المشرف: {_rl(config.mod_role_id)}\n"
            f"رول انضمام تلقائي: {_rl(config.auto_role_id)}"
        )
        embed = create_neon_embed("ملخص الإعدادات | Server Config", desc, color=0x00F5FF)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
