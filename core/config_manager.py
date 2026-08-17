import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.future import select
from sqlalchemy import delete
from core.database import AsyncSessionLocal
from core.models import GuildConfig, RolePermissionTier, Whitelist

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
PERSISTENT_JSON_PATH = os.path.join(DATA_DIR, "persistent_guild_configs.json")
TIERS_JSON_PATH = os.path.join(DATA_DIR, "persistent_tiers.json")

# ─── الذاكرة السريعة اللحظية في الرام (Ultra-Fast In-Memory Cache) ───────────
_CONFIG_CACHE: Dict[int, Dict[str, Any]] = {}
_TIERS_CACHE: Dict[int, Dict[str, List[int]]] = {}


def _save_json_file(filepath: str, data: dict):
    """حفظ البيانات كملف JSON احتياطي محلي دائم على القرص الصلب."""
    try:
        temp_file = filepath + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_file, filepath)
    except Exception as e:
        logger.warning(f"تعذر حفظ ملف الاستعادة JSON {filepath}: {e}")


def _load_json_file(filepath: str) -> dict:
    """قراءة ملف JSON الاحتياطي المحلي."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"تعذر قراءة ملف JSON {filepath}: {e}")
    return {}


async def preload_all_configs():
    """
    تحميل جميع الإعدادات فور إقلاع البوت من قاعدة البيانات والـ JSON إلى الذاكرة السريعة.
    يضمن بقاء الإعدادات 100% مستحيلة النسيان عبر عمليات إعادة التشغيل.
    """
    global _CONFIG_CACHE, _TIERS_CACHE
    # 1. تحميل من JSON أولاً كاحتياط
    json_configs = _load_json_file(PERSISTENT_JSON_PATH)
    for gid_str, conf in json_configs.items():
        try:
            _CONFIG_CACHE[int(gid_str)] = conf
        except Exception:
            pass

    json_tiers = _load_json_file(TIERS_JSON_PATH)
    for gid_str, tiers in json_tiers.items():
        try:
            _TIERS_CACHE[int(gid_str)] = tiers
        except Exception:
            pass

    # 2. تحميل وتحديث من قاعدة البيانات
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig))
            configs = res.scalars().all()
            for cfg in configs:
                conf_dict = {
                    "guild_id": cfg.guild_id,
                    "admin_role_id": cfg.admin_role_id,
                    "mod_role_id": cfg.mod_role_id,
                    "log_channel_id": cfg.log_channel_id,
                    "welcome_channel_id": cfg.welcome_channel_id,
                    "leave_channel_id": cfg.leave_channel_id,
                    "ticket_category_id": cfg.ticket_category_id,
                    "report_channel_id": cfg.report_channel_id,
                    "temp_voice_channel_id": cfg.temp_voice_channel_id,
                    "leveling_channel_id": cfg.leveling_channel_id,
                    "quarantine_role_id": cfg.quarantine_role_id,
                    "anti_raid_enabled": cfg.anti_raid_enabled,
                    "anti_nuke_enabled": cfg.anti_nuke_enabled,
                    "anti_spam_enabled": cfg.anti_spam_enabled,
                    "anti_phishing_enabled": cfg.anti_phishing_enabled,
                    "ai_mod_enabled": cfg.ai_mod_enabled,
                    "sentiment_mod_enabled": cfg.sentiment_mod_enabled,
                    "leveling_enabled": cfg.leveling_enabled,
                    "logging_enabled": cfg.logging_enabled,
                    "ai_enabled": cfg.ai_enabled,
                    "stats_enabled": cfg.stats_enabled,
                }
                _CONFIG_CACHE[cfg.guild_id] = conf_dict

            res_tiers = await session.execute(select(RolePermissionTier))
            tier_rows = res_tiers.scalars().all()
            for row in tier_rows:
                if row.guild_id not in _TIERS_CACHE:
                    _TIERS_CACHE[row.guild_id] = {}
                tier_key = row.tier.upper()
                if tier_key not in _TIERS_CACHE[row.guild_id]:
                    _TIERS_CACHE[row.guild_id][tier_key] = []
                if row.role_id not in _TIERS_CACHE[row.guild_id][tier_key]:
                    _TIERS_CACHE[row.guild_id][tier_key].append(row.role_id)

        # حفظ الحالة الحالية كـ JSON دائم
        _sync_json_disk()
        logger.info(f"تم تحميل وتأمين إعدادات {len(_CONFIG_CACHE)} سيرفر في الذاكرة الدائمة بنجاح.")
    except Exception as e:
        logger.warning(f"تنبيه أثناء تهيئة الذاكرة الدائمة للإعدادات: {e}")


def _sync_json_disk():
    """كتابة الكاش الحالي إلى ملفات الـ JSON في القرص الصلب."""
    try:
        _save_json_file(PERSISTENT_JSON_PATH, {str(k): v for k, v in _CONFIG_CACHE.items()})
        _save_json_file(TIERS_JSON_PATH, {str(k): v for k, v in _TIERS_CACHE.items()})
    except Exception:
        pass


async def get_cached_guild_config(guild_id: int) -> Optional[GuildConfig]:
    """
    استرجاع كائن GuildConfig دائم ومحصن ضد فقدان البيانات.
    يقرأ من الذاكرة اللحظية -> ثم قاعدة البيانات -> ثم ملف JSON الاحتياطي.
    """
    # 1. محاولة القراءة من الكاش أولاً
    cached = _CONFIG_CACHE.get(guild_id)
    if cached:
        cfg = GuildConfig()
        for k, v in cached.items():
            setattr(cfg, k, v)
        return cfg

    # 2. محاولة القراءة من DB
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
            cfg = result.scalars().first()
            if cfg:
                conf_dict = {
                    "guild_id": cfg.guild_id,
                    "admin_role_id": cfg.admin_role_id,
                    "mod_role_id": cfg.mod_role_id,
                    "log_channel_id": cfg.log_channel_id,
                    "welcome_channel_id": cfg.welcome_channel_id,
                    "leave_channel_id": cfg.leave_channel_id,
                    "ticket_category_id": cfg.ticket_category_id,
                    "report_channel_id": cfg.report_channel_id,
                    "temp_voice_channel_id": cfg.temp_voice_channel_id,
                    "leveling_channel_id": cfg.leveling_channel_id,
                    "quarantine_role_id": cfg.quarantine_role_id,
                    "anti_raid_enabled": cfg.anti_raid_enabled,
                    "anti_nuke_enabled": cfg.anti_nuke_enabled,
                    "anti_spam_enabled": cfg.anti_spam_enabled,
                    "anti_phishing_enabled": cfg.anti_phishing_enabled,
                    "ai_mod_enabled": cfg.ai_mod_enabled,
                    "sentiment_mod_enabled": cfg.sentiment_mod_enabled,
                    "leveling_enabled": cfg.leveling_enabled,
                    "logging_enabled": cfg.logging_enabled,
                    "ai_enabled": cfg.ai_enabled,
                    "stats_enabled": cfg.stats_enabled,
                }
                _CONFIG_CACHE[guild_id] = conf_dict
                _sync_json_disk()
                return cfg
    except Exception:
        pass

    return None


async def save_guild_config_field(guild_id: int, field_name: str, value: Any) -> GuildConfig:
    """
    حفظ أي إعداد (قناة، رتبة، تفعيل/تعطيل) في الطبقات الثلاث (الرام + DB + JSON) بضمان عدم النسيان.
    """
    # 1. تحديث الكاش
    if guild_id not in _CONFIG_CACHE:
        _CONFIG_CACHE[guild_id] = {"guild_id": guild_id}
    _CONFIG_CACHE[guild_id][field_name] = value

    # 2. تحديث ملف JSON
    _sync_json_disk()

    # 3. تحديث قاعدة البيانات
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        config = result.scalars().first()
        if not config:
            config = GuildConfig(guild_id=guild_id)
            session.add(config)

        setattr(config, field_name, value)
        await session.commit()
        await session.refresh(config)
        return config


async def get_cached_tier_role_ids(guild_id: int, tier: str) -> List[int]:
    """استرجاع معرفات رتب المستوى بسرعة فائقة ودقة مطلقة."""
    tier_upper = tier.upper()
    if guild_id in _TIERS_CACHE and tier_upper in _TIERS_CACHE[guild_id]:
        return list(_TIERS_CACHE[guild_id][tier_upper])

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(RolePermissionTier.role_id).where(
                    RolePermissionTier.guild_id == guild_id,
                    RolePermissionTier.tier == tier_upper
                )
            )
            role_ids = list(result.scalars().all())
            if guild_id not in _TIERS_CACHE:
                _TIERS_CACHE[guild_id] = {}
            _TIERS_CACHE[guild_id][tier_upper] = role_ids
            _sync_json_disk()
            return role_ids
    except Exception:
        return []


async def set_cached_tier_roles(guild_id: int, tier: str, role_ids: List[int]):
    """تحديث رتب المستوى وحفظها في الكاش والـ DB والـ JSON معاً."""
    tier_upper = tier.upper()
    if guild_id not in _TIERS_CACHE:
        _TIERS_CACHE[guild_id] = {}
    _TIERS_CACHE[guild_id][tier_upper] = list(role_ids)
    _sync_json_disk()

    try:
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
    except Exception as e:
        logger.warning(f"خطأ أثناء حفظ رتب المستوى في DB: {e}")
