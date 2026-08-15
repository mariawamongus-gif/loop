import discord
from typing import Optional, List
from sqlalchemy.future import select
from sqlalchemy import delete
from core.database import AsyncSessionLocal
from core.models import GuildConfig, Whitelist, RolePermissionTier

async def get_guild_config(guild_id: int) -> Optional[GuildConfig]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        return result.scalars().first()

async def get_tier_role_ids(guild_id: int, tier: str) -> List[int]:
    """استرجاع جميع معرّفات الرولات المسندة لمستوى صلاحية معين"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RolePermissionTier.role_id).where(
                RolePermissionTier.guild_id == guild_id,
                RolePermissionTier.tier == tier.upper()
            )
        )
        return list(result.scalars().all())

async def set_tier_roles(guild_id: int, tier: str, role_ids: List[int]):
    """تحديث رولات مستوى معين (استبدال كامل)"""
    tier_upper = tier.upper()
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(RolePermissionTier).where(
                RolePermissionTier.guild_id == guild_id,
                RolePermissionTier.tier == tier_upper
            )
        )
        for rid in role_ids:
            session.add(RolePermissionTier(guild_id=guild_id, tier=tier_upper, role_id=rid))
        await session.commit()

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

# مرادف للرتبة الماكس
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

# مرادف للرتبة التكتيكية
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

    # فحص رتب الحصانة
    immunity_role_ids = await get_tier_role_ids(guild_id, "IMMUNITY")
    return user_or_role_id in immunity_role_ids
