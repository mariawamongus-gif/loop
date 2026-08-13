import discord
from datetime import datetime
from typing import Optional
from config import Config


def _make_bar(pct: float, length: int = 10) -> str:
    """شريط تقدم نصي."""
    filled = int(min(max(pct, 0), 100) / 100 * length)
    return "█" * filled + "░" * (length - filled)


def create_neon_embed(
    title: str,
    description: str,
    color: Optional[int] = None,
    footer_text: str = "Neon Engine v2.0  •  Automated System",
    thumbnail_url: Optional[str] = None,
    image_url: Optional[str] = None,
) -> discord.Embed:
    """
    الـ Embed الأساسي — تصميم سايبر بارد مع فاصل هيكلي وتوقيت دقيق.
    """
    if color is None:
        color = Config.EMBED_COLOR

    styled_desc = f"{description}\n\n`─────────────── SYSTEM ACTIVE ───────────────`"

    embed = discord.Embed(
        title=f"❖  {title}",
        description=styled_desc,
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text=footer_text)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if image_url:
        embed.set_image(url=image_url)
    return embed


def create_success_embed(title: str, description: str) -> discord.Embed:
    """Embed نجاح — أخضر نيون."""
    embed = discord.Embed(
        title=f"✅  {title}",
        description=f"{description}\n\n`─────────────── OPERATION COMPLETE ───────────────`",
        color=Config.EMBED_COLOR_SUCCESS,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Neon Engine  •  Success")
    return embed


def create_error_embed(title: str, description: str) -> discord.Embed:
    """Embed خطأ — أحمر."""
    embed = discord.Embed(
        title=f"✖  {title}",
        description=f"{description}\n\n`─────────────── SYSTEM ALERT ───────────────`",
        color=Config.EMBED_COLOR_ERROR,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Neon Engine  •  Error")
    return embed


def create_warning_embed(title: str, description: str) -> discord.Embed:
    """Embed تحذير — برتقالي."""
    embed = discord.Embed(
        title=f"⚠️  {title}",
        description=f"{description}\n\n`─────────────── CAUTION ───────────────`",
        color=Config.EMBED_COLOR_WARNING,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Neon Engine  •  Warning")
    return embed


def create_critical_embed(title: str, description: str) -> discord.Embed:
    """Embed حرج — أحمر ساطع."""
    embed = discord.Embed(
        title=f"🚨  {title}",
        description=f"{description}\n\n`─────────────── CRITICAL ALERT ───────────────`",
        color=Config.EMBED_COLOR_CRITICAL,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Neon Engine  •  CRITICAL")
    return embed


def create_info_embed(title: str, description: str, guild: Optional[discord.Guild] = None) -> discord.Embed:
    """Embed معلومات — أزرق سماوي."""
    embed = discord.Embed(
        title=f"ℹ️  {title}",
        description=f"{description}\n\n`─────────────── INFO ───────────────`",
        color=0x00BFFF,
        timestamp=datetime.utcnow(),
    )
    if guild:
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="Neon Engine  •  Info")
    return embed
