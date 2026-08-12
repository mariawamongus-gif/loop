import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime, timedelta
import random
from core.database import AsyncSessionLocal
from core.models import UserLevel, GuildConfig
from core.strings import Strings
from utils.embeds import create_neon_embed

class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
            config = res.scalars().first()
            if not config or not config.leveling_enabled:
                return

            res_level = await session.execute(
                select(UserLevel).where(UserLevel.guild_id == guild_id, UserLevel.user_id == user_id)
            )
            user_data = res_level.scalars().first()

            now = datetime.utcnow()
            if not user_data:
                user_data = UserLevel(guild_id=guild_id, user_id=user_id, xp=0, level=1, last_message_at=now)
                session.add(user_data)
                await session.commit()

            # Cooldown دقيقة بين منح الخبرة
            if now - user_data.last_message_at < timedelta(seconds=60):
                return

            added_xp = random.randint(15, 25)
            user_data.xp += added_xp
            user_data.last_message_at = now

            # معادلة احتساب مستوى الخبرة: XP_Needed = Level * 100
            xp_needed = user_data.level * 100
            if user_data.xp >= xp_needed:
                user_data.level += 1
                if not config.silent_protocol:
                    embed = create_neon_embed(
                        "ترقية مستوى | Level Up",
                        Strings.LEVEL_UP.format(user=message.author.mention, level=user_data.level)
                    )
                    try:
                        await message.channel.send(embed=embed)
                    except Exception:
                        pass

            await session.commit()

    @app_commands.command(name="rank", description="عرض بطاقة المستوى والخبرة الحالية")
    @app_commands.describe(user="العضو المراد استعراض مستواه (اختياري)")
    async def rank(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserLevel).where(UserLevel.guild_id == interaction.guild_id, UserLevel.user_id == target.id)
            )
            data = res.scalars().first()

            # حساب الترتيب العالمي في السيرفر
            res_rank = await session.execute(
                select(UserLevel)
                .where(UserLevel.guild_id == interaction.guild_id)
                .order_by(UserLevel.xp.desc())
            )
            all_users = res_rank.scalars().all()
            rank_pos = 1
            for idx, u in enumerate(all_users, 1):
                if u.user_id == target.id:
                    rank_pos = idx
                    break

        level = data.level if data else 1
        xp = data.xp if data else 0
        xp_needed = level * 100

        try:
            from utils.rank_card import generate_rank_card
            avatar_url = target.display_avatar.url if target.display_avatar else ""
            card_buffer = await generate_rank_card(
                username=target.name,
                avatar_url=avatar_url,
                level=level,
                xp=xp,
                xp_needed=xp_needed,
                rank_position=rank_pos
            )
            file = discord.File(card_buffer, filename=f"rank_{target.id}.png")
            await interaction.followup.send(file=file)
        except Exception:
            embed = create_neon_embed(
                f"بطاقة المستوى | {target.name}",
                f"**العضو:** {target.mention}\n**الترتيب:** #{rank_pos}\n**المستوى الحالي:** {level}\n**الخبرة:** {xp} / {xp_needed} XP"
            )
            await interaction.followup.send(embed=embed)


    @app_commands.command(name="leaderboard", description="عرض ترتيب متصدري الخبرة بالسيرفر")
    async def leaderboard(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserLevel)
                .where(UserLevel.guild_id == interaction.guild_id)
                .order_by(UserLevel.xp.desc())
            )
            all_users = res.scalars().all()

        if not all_users:
            embed = create_neon_embed("قائمة المتصدرين | Leaderboard", "لا توجد بيانات خبرة مسجلة بعد.")
            await interaction.response.send_message(embed=embed)
            return

        top_users = all_users[:10]
        max_xp = top_users[0].xp if top_users else 1
        medals = {1: "◈", 2: "◇", 3: "△"}

        desc = ""
        for idx, u in enumerate(top_users, 1):
            member = interaction.guild.get_member(u.user_id)
            name = member.name if member else f"ID: {u.user_id}"
            medal = medals.get(idx, f"#{idx}")

            bar_pct = min(u.xp / max(max_xp, 1), 1.0)
            filled = int(bar_pct * 8)
            bar = "█" * filled + "░" * (8 - filled)

            desc += f"**{medal}** `{name}` | LVL `{u.level}` | `{bar}` `{u.xp} XP`\n"

            if idx == 3 and len(top_users) > 3:
                desc += "`───────────────────────────────`\n"

        # عرض ترتيب الطالب إذا لم يكن في أول 10
        requester_rank = None
        for i, u in enumerate(all_users, 1):
            if u.user_id == interaction.user.id:
                requester_rank = i
                break

        if requester_rank and requester_rank > 10:
            req_data = all_users[requester_rank - 1]
            desc += f"\n`─── ترتيبك الحالي ───`\n**#{requester_rank}** `{interaction.user.name}` | LVL `{req_data.level}` | `{req_data.xp} XP`"

        embed = create_neon_embed(Strings.LEADERBOARD_TITLE, desc, color=0x00F5FF)
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))

