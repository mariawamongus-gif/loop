from sqlalchemy.future import select
from datetime import datetime
import discord
from core.database import AsyncSessionLocal
from core.models import DecisionLogEntry, GuildConfig
from utils.embeds import create_neon_embed

async def log_decision(
    guild: discord.Guild,
    command: str,
    check_result: str,
    execution_step: str,
    outcome: str
):
    """
    تسجيل قرار آلي بتسلسل عمليات ثابت:
    أمر مستلم -> تحقق -> تنفيذ -> نتيجة
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # حفظ في قاعدة البيانات
    async with AsyncSessionLocal() as session:
        entry = DecisionLogEntry(
            guild_id=guild.id,
            command=command,
            check_result=check_result,
            execution_step=execution_step,
            outcome=outcome
        )
        session.add(entry)

        # جلب قناة السجلات
        result = await session.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild.id)
        )
        config = result.scalars().first()
        await session.commit()


        if config and config.logging_enabled and config.log_channel_id:
            channel = guild.get_channel(config.log_channel_id)
            if channel:
                desc = (
                    f"**الوقت:** `{now}`\n\n"
                    f"**1. أمر مستلم:** {command}\n"
                    f"**2. تحقق:** {check_result}\n"
                    f"**3. تنفيذ:** {execution_step}\n"
                    f"**4. نتيجة:** {outcome}"
                )
                embed = create_neon_embed(
                    title="سجل قرارات آلي | Decision Log",
                    description=desc,
                    footer_text="Neon Automated Decision Pipeline"
                )
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
