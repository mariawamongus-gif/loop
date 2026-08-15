import discord
from discord import app_commands
from discord.ext import commands
from core.permissions import is_admin, get_tier_role_ids, set_tier_roles
from utils.embeds import create_neon_embed, create_success_embed, create_warning_embed
from utils.decision_log import log_decision


# ═════════════════════════════════════════════════════════════════
# واجهات الاختيار التفاعلية للرتب (Multi-Role Selectors)
# ═════════════════════════════════════════════════════════════════

class TierRoleSelect(discord.ui.RoleSelect):
    def __init__(self, tier: str, placeholder: str):
        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=25,
            custom_id=f"neon_tier_select_{tier.lower()}"
        )
        self.tier = tier.upper()

    async def callback(self, interaction: discord.Interaction):
        selected_roles = self.values
        role_ids = [r.id for r in selected_roles]
        
        await set_tier_roles(interaction.guild_id, self.tier, role_ids)

        tier_names = {
            "EXECUTIVE": "الرتبة الماكس (Executive Tier)",
            "TACTICAL": "الرتبة التكتيكية الإشرافية (Tactical Mod Tier)",
            "IMMUNITY": "رتب الحصانة والاستثناء (Immunity Tier)"
        }

        roles_text = "\n".join([f"• {r.mention} (`{r.name}`)" for r in selected_roles]) if selected_roles else "• *لم يتم تعيين أي رول (فارغ)*"

        embed = create_success_embed(
            f"تم تحديث {tier_names.get(self.tier, self.tier)}",
            f"تم اعتماد وتفويض **{len(selected_roles)}** رول لهذه الفئة بنجاح:\n\n"
            f"{roles_text}\n\n"
            f"تم تطبيق هذا التحديث على الفور في كافة أنظمة الفحص الأمني للأوامر."
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_decision(
            interaction.guild,
            command=f"/role_selector set_tier={self.tier} count={len(role_ids)}",
            check_result="صلاحيات القيادة العليا مؤكدة",
            execution_step=f"تحديث جدول الصلاحيات لفئة {self.tier}",
            outcome=f"تم إسناد {len(role_ids)} رتبة"
        )


class RoleSelectorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TierRoleSelect("EXECUTIVE", "🔴 الخانة 1: اختر رتب المستوى الماكس (حتى 25 رول)..."))
        self.add_item(TierRoleSelect("TACTICAL", "🟡 الخانة 2: اختر رتب الإشراف التكتيكي (حتى 25 رول)..."))
        self.add_item(TierRoleSelect("IMMUNITY", "🟢 الخانة 3: اختر رتب الحصانة والاستثناء (حتى 25 رول)..."))

    @discord.ui.button(label="استعراض الرتب المسندة حالياً", style=discord.ButtonStyle.primary, emoji="📋", row=3)
    async def view_current_tiers(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        exec_ids = await get_tier_role_ids(guild.id, "EXECUTIVE")
        tact_ids = await get_tier_role_ids(guild.id, "TACTICAL")
        immu_ids = await get_tier_role_ids(guild.id, "IMMUNITY")

        def format_roles(role_ids):
            if not role_ids:
                return "`غير محدد (فارغ)`"
            roles = [guild.get_role(rid) for rid in role_ids]
            valid = [r.mention for r in roles if r is not None]
            return " ".join(valid) if valid else "`رولات محذوفة`"

        desc = (
            f"`═════════ 🔴 المستوى الماكس (Executive) ═════════`\n"
            f"**الرتب المخولة:** {format_roles(exec_ids)}\n"
            f"**الصلاحيات:** إغلاق/فتح السيرفر، التدقيق الأمني، الإعدادات، النسخ الاحتياطي، تعديل الرتب والخبرات، الإعلانات.\n\n"
            f"`═════════ 🟡 المستوى التكتيكي (Tactical) ═════════`\n"
            f"**الرتب المخولة:** {format_roles(tact_ids)}\n"
            f"**الصلاحيات:** الحظر، الطرد، التايم آوت، الإنذارات، مسح الرسائل، كشف الحسابات، الاستبيانات، الأسئلة الشائعة.\n\n"
            f"`═════════ 🟢 مستوى الحصانة (Immunity) ═════════`\n"
            f"**الرتب المعفاة:** {format_roles(immu_ids)}\n"
            f"**الحصانة:** معفاة من فلتر الكلمات، الذكاء الاصطناعي السلوكي، وقيود الحماية التلقائية."
        )

        embed = create_neon_embed("خريطة تفويض الرتب والصلاحيات | Role Matrix", desc, color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ═════════════════════════════════════════════════════════════════
# الـ Cog الرئيسي لإدارة تفويض الرتب - Role Selector Cog
# ═════════════════════════════════════════════════════════════════

class RoleSelectorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="role_selector",
        description="لوحة التحكم الاستراتيجية لتفويض وتصنيف الرتب والصلاحيات (أكثر من 10 رتب لكل خانة)"
    )
    async def role_selector(self, interaction: discord.Interaction):
        # مقتصر حصراً على المالك أو من لديه Administrator
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message(
                "خطأ أمني: الوصول لهذا الأمر مقتصر حصراً على مالك السيرفر أو القيادة العليا (Administrator).",
                ephemeral=True
            )
            return

        desc = (
            "مرحباً بك في مركز التحكم الاستراتيجي بتفويض الرتب والصلاحيات.\n\n"
            "`──────── دليل الخانات والمستويات ────────`\n\n"
            "🔴 **الخانة 1 | الرتبة الماكس (Executive / Commander):**\n"
            "• مخصصة للأوامر الحساسة والاستراتيجية التي لا يمكن للأعضاء أو المشرفين العاديين لمسها:\n"
            "  `/setup`, `/lockdown_server`, `/unlock_server`, `/security_audit`, `/server_snapshot`,\n"
            "  `/db_export`, `/backup_create`, `/reset_xp`, `/set_level`, `/give_xp`, `/announce`\n"
            "• تدعم تحديد أكثر من 10 أو 20 رول دفعة واحدة.\n\n"
            "🟡 **الخانة 2 | الرتبة التكتيكية (Tactical / Field Moderator):**\n"
            "• مخصصة لأوامر الإشراف والتدخل الميداني وضبط المخالفين:\n"
            "  `/ban`, `/kick`, `/timeout`, `/remove_timeout`, `/warn`, `/strike`, `/strikes_list`,\n"
            "  `/clear`, `/history`, `/case`, `/scan_user`, `/poll`, `/faq`, `/role_menu`\n\n"
            "🟢 **الخانة 3 | رتب الحصانة والاستثناء (Immunity / Whitelist):**\n"
            "• رتب معفاة بالكامل من الرقابة التلقائية وفلاتر الكلمات والذكاء الاصطناعي السلوكي.\n\n"
            "`──────── التعليمات ────────`\n"
            "استخدم القوائم المنسدلة أدناه لاختيار الرتب لكل خانة (يمكنك اختيار حتى 25 رول لكل خانة)."
        )

        embed = create_neon_embed("نظام تفويض الصلاحيات | Strategic Role Selector", desc, color=0x00F5FF)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        view = RoleSelectorView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleSelectorCog(bot))
