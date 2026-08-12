import discord
from datetime import datetime
from typing import Optional
from config import Config

def create_neon_embed(
    title: str,
    description: str,
    color: Optional[int] = None,
    footer_text: str = "Neon Automated Engine | System v2.0",
    thumbnail_url: Optional[str] = None
) -> discord.Embed:
    """
    مُنشئ الـ Embed الفائق المطور لبوت Neon.
    تصميم سايبر بارد وأنيق ومظلم مع فاصل هيكلي وتوقيت دقيق.
    """
    if color is None:
        color = Config.EMBED_COLOR

    styled_desc = f"{description}\n\n`─────────────── SYSTEM ACTIVE ───────────────`"

    embed = discord.Embed(
        title=f"❖ {title}",
        description=styled_desc,
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=footer_text)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    return embed
