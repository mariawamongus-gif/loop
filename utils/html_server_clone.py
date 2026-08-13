import os
import html
from datetime import datetime
import discord

async def generate_server_html_clone(guild: discord.Guild) -> str:
    """
    يولّد ملف HTML أسطوري يمثل نسخة تفاعلية (Discord UI Clone) لشكل السيرفر،
    تتضمن القنوات، الفئات، القنوات المستقلة، الرولات، وأسماء وصور جميع الأدمنية والمشرفين.
    """
    os.makedirs("backups", exist_ok=True)
    filename = f"backups/server_snapshot_{guild.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"

    # 1. تجميع الأدمنية والمشرفين بصورهم ورولاتهم
    admins_html = ""
    admin_count = 0
    for member in guild.members:
        if member.guild_permissions.administrator or member.id == guild.owner_id:
            admin_count += 1
            avatar_url = member.display_avatar.url if member.display_avatar else ""
            top_role = member.top_role.name if member.top_role else "Admin"
            status_color = "#23a55a" if str(member.status) == "online" else ("#f0b232" if str(member.status) == "idle" else ("#f23f43" if str(member.status) == "dnd" else "#80848e"))
            admins_html += f"""
            <div class="admin-card">
                <div class="avatar-wrap">
                    <img class="admin-avatar" src="{avatar_url}" alt="" />
                    <span class="status-dot" style="background-color: {status_color};"></span>
                </div>
                <div class="admin-info">
                    <div class="admin-name">{html.escape(member.display_name)} <span class="username">({html.escape(member.name)})</span></div>
                    <div class="admin-id">ID: {member.id}</div>
                    <div class="admin-role">{html.escape(top_role)}</div>
                </div>
            </div>
            """

    # 2. تجميع هيكل الفئات والقنوات (شامل القنوات المستقلة)
    channels_html = ""

    # القنوات غير المصنفة
    uncategorized = [c for c in guild.channels if c.category is None]
    if uncategorized:
        uncat_channels_html = ""
        for channel in uncategorized:
            if isinstance(channel, discord.CategoryChannel):
                continue
            icon = "#" if isinstance(channel, discord.TextChannel) else ("🔊" if isinstance(channel, discord.VoiceChannel) else "📢")
            uncat_channels_html += f"""
            <div class="channel-item">
                <span class="channel-icon">{icon}</span>
                <span class="channel-name">{html.escape(channel.name)}</span>
            </div>
            """
        if uncat_channels_html:
            channels_html += f"""
            <div class="category-block">
                <div class="category-title">▾ قنوات عامة / UNCATEGORIZED</div>
                <div class="category-channels">{uncat_channels_html}</div>
            </div>
            """

    for category in guild.categories:
        cat_channels_html = ""
        for channel in category.channels:
            icon = "#" if isinstance(channel, discord.TextChannel) else ("🔊" if isinstance(channel, discord.VoiceChannel) else "📢")
            cat_channels_html += f"""
            <div class="channel-item">
                <span class="channel-icon">{icon}</span>
                <span class="channel-name">{html.escape(channel.name)}</span>
            </div>
            """
        channels_html += f"""
        <div class="category-block">
            <div class="category-title">▾ {html.escape(category.name).upper()}</div>
            <div class="category-channels">{cat_channels_html}</div>
        </div>
        """

    # 3. تجميع الرولات
    roles_html = ""
    for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if not role.is_default():
            color_hex = f"#{role.color.value:06x}" if role.color.value else "#99aab5"
            roles_html += f"""
            <div class="role-badge" style="border-color: {color_hex}; color: {color_hex};">
                ● {html.escape(role.name)} <span class="role-count">({len(role.members)})</span>
            </div>
            """

    guild_icon = guild.icon.url if guild.icon else ""
    created_at_str = guild.created_at.strftime("%Y-%m-%d")
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count or 0

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Discord Server Snapshot | {html.escape(guild.name)}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background-color: #1e1f22;
            color: #dbdee1;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}

        /* Sidebar - Categories & Channels */
        .sidebar {{
            width: 280px;
            background-color: #2b2d31;
            display: flex;
            flex-direction: column;
            border-left: 1px solid #1e1f22;
        }}
        .server-header {{
            height: 56px;
            padding: 0 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid #1f2023;
            font-weight: 700;
            font-size: 16px;
            color: #f2f3f5;
            background: #2b2d31;
        }}
        .server-icon {{ width: 34px; height: 34px; border-radius: 50%; object-fit: cover; border: 2px solid #5865f2; }}
        .channels-scroll {{ flex: 1; overflow-y: auto; padding: 14px 10px; }}
        .category-block {{ margin-bottom: 18px; }}
        .category-title {{ font-size: 11px; font-weight: 700; color: #949ba4; margin-bottom: 6px; padding: 0 8px; letter-spacing: 0.5px; }}
        .channel-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 7px 10px;
            border-radius: 6px;
            color: #949ba4;
            font-size: 14px;
            cursor: default;
            transition: all 0.15s ease;
        }}
        .channel-item:hover {{ background-color: #35373c; color: #dbdee1; }}
        .channel-icon {{ font-weight: 700; width: 18px; text-align: center; color: #80848e; }}

        /* Main Dashboard */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: #313338;
            overflow-y: auto;
            padding: 32px;
        }}
        .snapshot-banner {{
            background: linear-gradient(135deg, #2b2d31 0%, #1e1f22 100%);
            border: 1px solid #3f4147;
            border-radius: 14px;
            padding: 28px;
            margin-bottom: 28px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}
        .snapshot-banner h1 {{ color: #5865f2; font-size: 26px; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }}
        .snapshot-banner p {{ color: #949ba4; font-size: 14px; margin-bottom: 16px; }}
        .meta-grid {{ display: flex; gap: 16px; flex-wrap: wrap; }}
        .meta-item {{ background: #2b2d31; padding: 12px 18px; border-radius: 10px; border: 1px solid #383a40; font-size: 13px; }}
        .meta-item strong {{ color: #00f5ff; font-size: 15px; margin-right: 4px; }}

        /* Sections */
        .section-title {{ font-size: 19px; font-weight: 700; color: #f2f3f5; margin: 24px 0 14px 0; border-bottom: 1px solid #3f4147; padding-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }}
        .section-badge {{ font-size: 12px; background: #383a40; padding: 4px 10px; border-radius: 12px; color: #50fa7b; font-weight: 600; }}
        .admins-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }}
        .admin-card {{
            background-color: #2b2d31;
            border: 1px solid #383a40;
            border-radius: 10px;
            padding: 14px;
            display: flex;
            align-items: center;
            gap: 14px;
            transition: transform 0.15s ease, border-color 0.15s ease;
        }}
        .admin-card:hover {{ transform: translateY(-2px); border-color: #5865f2; }}
        .avatar-wrap {{ position: relative; width: 46px; height: 46px; }}
        .admin-avatar {{ width: 46px; height: 46px; border-radius: 50%; border: 2px solid #5865f2; object-fit: cover; }}
        .status-dot {{ position: absolute; bottom: 0; right: 0; width: 14px; height: 14px; border-radius: 50%; border: 2.5px solid #2b2d31; }}
        .admin-name {{ font-weight: 700; color: #f2f3f5; font-size: 14px; }}
        .username {{ font-size: 11px; color: #949ba4; font-weight: 400; }}
        .admin-id {{ font-size: 11px; color: #80848e; margin-top: 2px; }}
        .admin-role {{ font-size: 11px; color: #50fa7b; font-weight: 600; margin-top: 3px; }}

        .roles-flex {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .role-badge {{
            background: #2b2d31;
            border: 1px solid;
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 13px;
            font-weight: 600;
        }}
        .role-count {{ font-size: 11px; opacity: 0.8; margin_right: 4px; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="server-header">
            {f'<img class="server-icon" src="{guild_icon}" alt="" />' if guild_icon else '<span class="server-icon" style="background:#5865f2;display:flex;align-items:center;justify-content:center;font-weight:bold;color:white;">'+html.escape(guild.name[:2])+'</span>'}
            <span>{html.escape(guild.name)}</span>
        </div>
        <div class="channels-scroll">
            {channels_html}
        </div>
    </div>
    <div class="main-content">
        <div class="snapshot-banner">
            <h1>🌐 Discord Server Snapshot | {html.escape(guild.name)}</h1>
            <p>نسخة أرشفية تفاعلية لهيكل السيرفر، الفئات، القنوات، الأدمنية، والرولات.</p>
            <div class="meta-grid">
                <div class="meta-item">إجمالي الأعضاء: <strong>{guild.member_count}</strong></div>
                <div class="meta-item">عدد القنوات: <strong>{len(guild.channels)}</strong></div>
                <div class="meta-item">عدد الرولات: <strong>{len(guild.roles)}</strong></div>
                <div class="meta-item">مستوى البوست: <strong>Level {boost_level} ({boost_count} Boosts)</strong></div>
                <div class="meta-item">تاريخ الإنشاء: <strong>{created_at_str}</strong></div>
                <div class="meta-item">تاريخ الأرشفة: <strong>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</strong></div>
            </div>
        </div>

        <div class="section-title">
            <span>👑 كادر الإدارة والأدمنية (Admins & Staff)</span>
            <span class="section-badge">{admin_count} أدمن</span>
        </div>
        <div class="admins-grid">
            {admins_html}
        </div>

        <div class="section-title">
            <span>🏷️ رولات السيرفر (Roles)</span>
            <span class="section-badge">{len(guild.roles) - 1} رول</span>
        </div>
        <div class="roles-flex">
            {roles_html}
        </div>
    </div>
</body>
</html>
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filename
