import discord
from discord import app_commands
from discord.ext import commands
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class RoleSelectMenu(discord.ui.Select):
    def __init__(self, roles: list[discord.Role]):
        options = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"اضغط لاختيار أو إزالة رول {role.name}"
            )
            for role in roles[:25]
        ]
        super().__init__(
            placeholder="اختر الرولات التي تريد الحصول عليها...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="neon_self_role_select"
        )

    async def callback(self, interaction: discord.Interaction):
        selected_ids = [int(v) for v in self.values]
        member = interaction.user

        added = []
        removed = []

        for option in self.options:
            role_id = int(option.value)
            role = interaction.guild.get_role(role_id)
            if not role:
                continue

            if role_id in selected_ids:
                if role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Self-assigned via Role Menu")
                        added.append(role.name)
                    except Exception:
                        pass
            else:
                if role in member.roles:
                    try:
                        await member.remove_roles(role, reason="Self-removed via Role Menu")
                        removed.append(role.name)
                    except Exception:
                        pass

        msg_parts = []
        if added:
            msg_parts.append(f"• **تمت إضافة الرولات:** {', '.join(added)}")
        if removed:
            msg_parts.append(f"• **تمت إزالة الرولات:** {', '.join(removed)}")
        if not msg_parts:
            msg_parts.append("لم يتم إجراء أي تغييرات على رولاتك.")

        desc = "\n".join(msg_parts)
        embed = create_neon_embed("تحديث الرولات | Role Update", desc, color=0x50FA7B)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RoleMenuView(discord.ui.View):
    def __init__(self, roles: list[discord.Role]):
        super().__init__(timeout=None)
        self.add_item(RoleSelectMenu(roles))


class ReactionRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="role_menu", description="إنشاء لوحة اختيار الرولات التفاعلية للأعضاء")
    @app_commands.describe(
        title="عنوان لوحة اختيار الرولات",
        role1="الرول الأول",
        role2="الرول الثاني (اختياري)",
        role3="الرول الثالث (اختياري)",
        role4="الرول الرابع (اختياري)",
        role5="الرول الخامس (اختياري)"
    )
    async def role_menu(
        self,
        interaction: discord.Interaction,
        title: str,
        role1: discord.Role,
        role2: discord.Role = None,
        role3: discord.Role = None,
        role4: discord.Role = None,
        role5: discord.Role = None
    ):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر هذا الأمر على أدمنية السيرفر فقط.", ephemeral=True)
            return

        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]

        roles_list_str = "\n".join([f"• {r.mention}" for r in roles])
        desc = (
            f"اختر الرولات المخصصة لك من القائمة المنسدلة أدناه:\n\n"
            f"**الرولات المتاحة:**\n{roles_list_str}"
        )

        embed = create_neon_embed(f"لوحة اختيار الرولات | {title}", desc, color=0x5865F2)
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        view = RoleMenuView(roles)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("تم إنشاء لوحة اختيار الرولات بنجاح.", ephemeral=True)

        await log_decision(
            interaction.guild,
            command=f"/role_menu title={title}",
            check_result="صلاحيات الأدمن مفحوصة",
            execution_step=f"إرسال لوحة اختيار لـ {len(roles)} رولات",
            outcome="تم إنشاء القائمة بنجاح"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRolesCog(bot))
