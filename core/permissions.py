import discord
from typing import Optional
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, Whitelist

async def get_guild_config(guild_id: int) -> Optional[GuildConfig]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        return result.scalars().first()

async def is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    if interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id:
        return True
    
    config = await get_guild_config(interaction.guild.id)
    if config and config.admin_role_id:
        return any(role.id == config.admin_role_id for role in interaction.user.roles)
    return False

async def is_mod(interaction: discord.Interaction) -> bool:
    if await is_admin(interaction):
        return True
    
    config = await get_guild_config(interaction.guild.id)
    if config and config.mod_role_id:
        return any(role.id == config.mod_role_id for role in interaction.user.roles)
    return interaction.user.guild_permissions.manage_messages

async def is_whitelisted(guild_id: int, user_or_role_id: int, target_type: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Whitelist).where(
                Whitelist.guild_id == guild_id,
                Whitelist.target_id == user_or_role_id,
                Whitelist.target_type == target_type
            )
        )
        return result.scalars().first() is not None
