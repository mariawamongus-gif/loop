import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.future import select
from datetime import datetime, timedelta
import random
from core.database import AsyncSessionLocal
from core.models import UserLevel, GuildConfig
from core.permissions import is_admin, is_mod
from core.strings import Strings
from utils.embeds import create_neon_embed, create_success_embed, create_error_embed


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
            res = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            config = res.scalars().first()
            if not config or not config.leveling_enabled:
                return

            res_level = await session.execute(
                select(UserLevel).where(
                    UserLevel.guild_id == guild_id,
                    UserLevel.user_id == user_id
                )
            )
            user_data = res_level.scalars().first()

            now = datetime.utcnow()
            if not user_data:
                user_data = UserLevel(
                    guild_id=guild_id, user_id=user_id,
                    xp=0, level=1, last_message_at=now
                )
                session.add(user_data)
                await session.commit()

            # Cooldown: دقيقة بين منح الخبرة
            if now - user_data.last_message_at < timedelta(seconds=60):
                return

            added_xp = random.randint(15, 25)
            user_data.xp += added_xp
            user_data.last_message_at = now

            # معادلة: XP_Needed = Level * 100
            xp_needed = user_data.level * 100
            if user_data.xp >= xp_needed:
                user_data.level += 1
                if not config.silent_protocol:
                    embed = create_neon_embed(
                        "🎉 ترقية مستوى | Level Up!",
                        f"**{message.author.mention}** وصل للمستوى **{user_data.level}** 🚀\n"
                        f"استمر في النشاط للوصول للقمة!",
                        color=0x00F5FF
                    )
                    try:
                        # إرسال الإشعار للقناة المخصصة إن وُجدت، وإلا لنفس الشات
                        target_ch = message.channel
                        lvl_ch_id = getattr(config, 'leveling_channel_id', None)
                        if lvl_ch_id:
                            found = message.guild.get_channel(lvl_ch_id)
                            if found:
                                target_ch = found
                        await target_ch.send(embed=embed)
                    except Exception:
                        pass

            await session.commit()

    # ─── /rank ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="rank", description="عرض بطاقة المستوى والخبرة الحالية")
    @app_commands.describe(user="العضو المراد استعراض مستواه (اختياري)")
    async def rank(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        await interaction.response.defer()

        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserLevel).where(
                    UserLevel.guild_id == interaction.guild_id,
                    UserLevel.user_id == target.id
                )
            )
            data = res.scalars().first()

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
            # Fallback: embed
            bar_pct = min(xp / max(xp_needed, 1), 1.0)
            filled = int(bar_pct * 12)
            bar = "█" * filled + "░" * (12 - filled)
            embed = create_neon_embed(
                f"بطاقة المستوى | {target.name}",
                f"**العضو:** {target.mention}\n"
                f"**الترتيب:** `#{rank_pos}` من `{len(all_users)}`\n"
                f"**المستوى:** `{level}`\n"
                f"**الخبرة:** `{xp}` / `{xp_needed}` XP\n"
                f"**التقدم:** `{bar}` `{int(bar_pct*100)}%`",
                thumbnail_url=target.display_avatar.url if target.display_avatar else ""
            )
            await interaction.followup.send(embed=embed)

    # ─── /leaderboard ────────────────────────────────────────────────────────────
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
            embed = create_neon_embed(
                "قائمة المتصدرين | Leaderboard",
                "لا توجد بيانات خبرة مسجلة بعد. ابدأ بالتفاعل لكسب الـ XP!"
            )
            await interaction.response.send_message(embed=embed)
            return

        top_users = all_users[:10]
        max_xp = top_users[0].xp if top_users else 1
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        desc = ""
        for idx, u in enumerate(top_users, 1):
            member = interaction.guild.get_member(u.user_id)
            name = member.display_name if member else f"ID: {u.user_id}"
            medal = medals.get(idx, f"`#{idx}`")

            bar_pct = min(u.xp / max(max_xp, 1), 1.0)
            filled = int(bar_pct * 10)
            bar = "█" * filled + "░" * (10 - filled)

            desc += f"{medal} **{name}** | Lv `{u.level}` | `{bar}` `{u.xp} XP`\n"

            if idx == 3 and len(top_users) > 3:
                desc += "`─────────────────────────────────`\n"

        # ترتيب الطالب إذا لم يكن في أول 10
        requester_rank = None
        requester_data = None
        for i, u in enumerate(all_users, 1):
            if u.user_id == interaction.user.id:
                requester_rank = i
                requester_data = u
                break

        if requester_rank and requester_rank > 10 and requester_data:
            desc += (
                f"\n`─── ترتيبك الحالي ───`\n"
                f"`#{requester_rank}` **{interaction.user.display_name}** "
                f"| Lv `{requester_data.level}` | `{requester_data.xp} XP`"
            )

        embed = create_neon_embed(
            f"🏆 متصدرو الخبرة | {interaction.guild.name}",
            desc,
            color=0x00F5FF
        )
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        embed.set_footer(
            text=f"Neon Engine  •  إجمالي الأعضاء المتتبَّعين: {len(all_users)}"
        )
        await interaction.response.send_message(embed=embed)

    # ─── /set_level (Admin) ───────────────────────────────────────────────────────
    @app_commands.command(name="set_level", description="تعيين مستوى عضو مباشرة (أدمن فقط)")
    @app_commands.describe(user="العضو المستهدف", level="المستوى الجديد")
    async def set_level(self, interaction: discord.Interaction, user: discord.Member, level: int):
        if not await is_admin(interaction):
            await interaction.response.send_message(
                "خطأ: يقتصر هذا الأمر على الأدمنية.", ephemeral=True
            )
            return

        if level < 1 or level > 999:
            await interaction.response.send_message("المستوى يجب أن يكون بين 1 و 999.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserLevel).where(
                    UserLevel.guild_id == interaction.guild_id,
                    UserLevel.user_id == user.id
                )
            )
            user_data = res.scalars().first()
            if not user_data:
                user_data = UserLevel(
                    guild_id=interaction.guild_id,
                    user_id=user.id,
                    xp=0,
                    level=level,
                    last_message_at=datetime.utcnow()
                )
                session.add(user_data)
            else:
                user_data.level = level
                user_data.xp = 0
            await session.commit()

        embed = create_success_embed(
            "تعيين المستوى | Set Level",
            f"تم تعيين مستوى {user.mention} إلى **Level {level}** بنجاح."
        )
        await interaction.response.send_message(embed=embed)

    # ─── /give_xp (Admin) ────────────────────────────────────────────────────────
    @app_commands.command(name="give_xp", description="منح نقاط خبرة لعضو يدوياً (أدمن فقط)")
    @app_commands.describe(user="العضو المستهدف", amount="كمية الـ XP المراد منحها")
    async def give_xp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not await is_admin(interaction):
            await interaction.response.send_message("يقتصر هذا الأمر على الأدمنية.", ephemeral=True)
            return

        if amount < 1 or amount > 100000:
            await interaction.response.send_message("الكمية يجب أن تكون بين 1 و 100,000.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserLevel).where(
                    UserLevel.guild_id == interaction.guild_id,
                    UserLevel.user_id == user.id
                )
            )
            user_data = res.scalars().first()
            if not user_data:
                user_data = UserLevel(
                    guild_id=interaction.guild_id,
                    user_id=user.id,
                    xp=amount,
                    level=1,
                    last_message_at=datetime.utcnow()
                )
                session.add(user_data)
            else:
                user_data.xp += amount
                # تحقق من ترقية المستوى
                xp_needed = user_data.level * 100
                while user_data.xp >= xp_needed:
                    user_data.level += 1
                    xp_needed = user_data.level * 100
            await session.commit()

        embed = create_success_embed(
            "منح الخبرة | Give XP",
            f"تم منح **{amount} XP** لـ {user.mention}.\n"
            f"مستواه الحالي الآن: **Level {user_data.level}**"
        )
        await interaction.response.send_message(embed=embed)

    # ─── /reset_xp (Admin) ───────────────────────────────────────────────────────
    @app_commands.command(name="reset_xp", description="إعادة تعيين XP عضو لـ 0 (أدمن فقط)")
    @app_commands.describe(user="العضو المستهدف")
    async def reset_xp(self, interaction: discord.Interaction, user: discord.Member):
        if not await is_admin(interaction):
            await interaction.response.send_message("يقتصر هذا الأمر على الأدمنية.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(UserLevel).where(
                    UserLevel.guild_id == interaction.guild_id,
                    UserLevel.user_id == user.id
                )
            )
            user_data = res.scalars().first()
            if user_data:
                user_data.xp = 0
                user_data.level = 1
                await session.commit()

        embed = create_success_embed(
            "إعادة تعيين الخبرة | Reset XP",
            f"تم إعادة تعيين XP و Level لـ {user.mention} إلى الصفر."
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
