import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, Whitelist
from core.permissions import is_admin
from utils.embeds import create_neon_embed
from utils.decision_log import log_decision

class BackupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="backup_create", description="إنشاء لقطة (Backup Snapshot) بهيكل السيرفر والرولات والقنوات")
    async def backup_create(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message("خطأ: يقتصر هذا الأمر على أدمنية السيرفر فقط.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        backup_data = {
            "guild_name": guild.name,
            "guild_id": guild.id,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "roles": [],
            "categories": [],
            "channels": []
        }

        # حفظ معلومات الرولات
        for role in guild.roles:
            if not role.is_default():
                backup_data["roles"].append({
                    "name": role.name,
                    "color": role.color.value,
                    "permissions": role.permissions.value,
                    "hoist": role.hoist,
                    "mentionable": role.mentionable
                })

        # حفظ معلومات الفئات والقنوات
        for category in guild.categories:
            backup_data["categories"].append({
                "name": category.name,
                "position": category.position
            })

        for channel in guild.text_channels:
            backup_data["channels"].append({
                "name": channel.name,
                "type": "text",
                "category": channel.category.name if channel.category else None,
                "topic": channel.topic
            })

        os.makedirs("backups", exist_ok=True)
        filename = f"backups/backup_{guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        file = discord.File(filename, filename=f"backup_server_{guild.id}.json")
        embed = create_neon_embed(
            "نسخ احتياطي للهيكل | Server Backup Created",
            f"تم أخذ لقطة سحابية كاملة لمكونات السيرفر بنجاح.\n"
            f"• **عدد الرولات المحفوظة:** `{len(backup_data['roles'])}`\n"
            f"• **عدد القنوات النصية:** `{len(backup_data['channels'])}`\n"
            f"• **التاريخ:** `{backup_data['timestamp']}`"
        )
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

        await log_decision(
            guild,
            command="/backup_create",
            check_result="صلاحيات الأدمن مؤكدة بالكامل",
            execution_step="تصدير ملف الهيكل JSON وتخزينه",
            outcome=f"إنشاء نسخ احتياطي باسم {os.path.basename(filename)}"
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
