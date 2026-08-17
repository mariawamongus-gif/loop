import discord
from typing import Optional, List
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from core.models import GuildConfig, Whitelist, RolePermissionTier
from core.config_manager import (
    get_cached_guild_config,
    get_cached_tier_role_ids,
    set_cached_tier_roles,
    save_guild_config_field
)

async def get_guild_config(guild_id: int) -> Optional[GuildConfig]:
    """استرجاع إعدادات السيرفر المحمية من الذاكرة الدائمة والكاش."""
    return await get_cached_guild_config(guild_id)

async def get_tier_role_ids(guild_id: int, tier: str) -> List[int]:
    """استرجاع جميع معرّفات الرولات المسندة لمستوى صلاحية معين بدقة متناهية."""
    return await get_cached_tier_role_ids(guild_id, tier)

async def set_tier_roles(guild_id: int, tier: str, role_ids: List[int]):
    """تحديث رولات مستوى معين وحفظها في الكاش وقاعدة البيانات والـ JSON معاً."""
    await set_cached_tier_roles(guild_id, tier, role_ids)

async def is_admin(interaction: discord.Interaction) -> bool:
    """فحص صلاحية الرتبة الماكس (Executive / Head Admin / Owner)"""
    if not interaction.guild:
        return False
    if interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id:
        return True
    
    # فحص الرول المفرد من GuildConfig
    config = await get_guild_config(interaction.guild.id)
    if config and config.admin_role_id:
        if any(role.id == config.admin_role_id for role in interaction.user.roles):
            return True

    # فحص قائمة الرتب الماكس المسندة في RoleSelector
    executive_role_ids = await get_tier_role_ids(interaction.guild.id, "EXECUTIVE")
    if executive_role_ids:
        user_role_ids = {r.id for r in interaction.user.roles}
        if any(rid in user_role_ids for rid in executive_role_ids):
            return True

    return False

is_executive = is_admin

async def is_mod(interaction: discord.Interaction) -> bool:
    """فحص صلاحية الرتبة التكتيكية الإشرافية (Tactical / Moderator)"""
    if await is_admin(interaction):
        return True
    
    if interaction.user.guild_permissions.manage_messages:
        return True

    # فحص الرول المفرد من GuildConfig
    config = await get_guild_config(interaction.guild.id)
    if config and config.mod_role_id:
        if any(role.id == config.mod_role_id for role in interaction.user.roles):
            return True

    # فحص قائمة الرتب التكتيكية المسندة في RoleSelector
    tactical_role_ids = await get_tier_role_ids(interaction.guild.id, "TACTICAL")
    if tactical_role_ids:
        user_role_ids = {r.id for r in interaction.user.roles}
        if any(rid in user_role_ids for rid in tactical_role_ids):
            return True

    return False

is_tactical = is_mod

async def is_whitelisted(guild_id: int, user_or_role_id: int, target_type: str) -> bool:
    """فحص هل الهدف في قائمة الاستثناء أو يحمل رتبة حصانة"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Whitelist).where(
                Whitelist.guild_id == guild_id,
                Whitelist.target_id == user_or_role_id,
                Whitelist.target_type == target_type
            )
        )
        if result.scalars().first() is not None:
            return True

    # فحص رتب الحصانة المسندة في RoleSelector
    if target_type == "role":
        immunity_roles = await get_tier_role_ids(guild_id, "IMMUNITY")
        if user_or_role_id in immunity_roles:
            return True

    return False
