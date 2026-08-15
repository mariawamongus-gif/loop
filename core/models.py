from sqlalchemy import Column, Integer, BigInteger, String, Text, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class GuildConfig(Base):
    __tablename__ = "guild_configs"

    guild_id = Column(BigInteger, primary_key=True, index=True)
    admin_role_id = Column(BigInteger, nullable=True)
    mod_role_id = Column(BigInteger, nullable=True)
    log_channel_id = Column(BigInteger, nullable=True)
    ticket_category_id = Column(BigInteger, nullable=True)
    welcome_channel_id = Column(BigInteger, nullable=True)
    leave_channel_id = Column(BigInteger, nullable=True)
    auto_role_id = Column(BigInteger, nullable=True)
    stats_channel_id = Column(BigInteger, nullable=True)
    report_channel_id = Column(BigInteger, nullable=True)
    temp_voice_channel_id = Column(BigInteger, nullable=True)
    leveling_channel_id = Column(BigInteger, nullable=True)

    confidence_threshold = Column(Float, default=0.80)
    witness_required = Column(Integer, default=2)

    protection_enabled = Column(Boolean, default=True)
    moderation_enabled = Column(Boolean, default=True)
    tickets_enabled = Column(Boolean, default=True)
    leveling_enabled = Column(Boolean, default=True)
    welcome_enabled = Column(Boolean, default=True)
    logging_enabled = Column(Boolean, default=True)
    ai_enabled = Column(Boolean, default=True)
    stats_enabled = Column(Boolean, default=True)

    silent_protocol = Column(Boolean, default=False)
    silent_until = Column(DateTime, nullable=True)


class Whitelist(Base):
    __tablename__ = "whitelists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    target_id = Column(BigInteger, nullable=False)
    target_type = Column(String(10), nullable=False)  # 'user' or 'role'


class RolePermissionTier(Base):
    __tablename__ = "role_permission_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    tier = Column(String(30), index=True, nullable=False)  # 'EXECUTIVE', 'TACTICAL', 'IMMUNITY'
    role_id = Column(BigInteger, nullable=False)


class ModerationCase(Base):
    __tablename__ = "moderation_cases"

    case_id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    mod_id = Column(BigInteger, nullable=False)
    action = Column(String(20), nullable=False)  # BAN, KICK, MUTE, WARN, UNMUTE, UNBAN, TIMEOUT
    reason = Column(Text, nullable=False)
    duration = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    ticket_id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    status = Column(String(20), default="OPEN")  # OPEN, RESOLVED, ESCALATED, CLOSED
    severity = Column(String(20), default="TRIVIAL")  # TRIVIAL, SERIOUS, CRITICAL
    confidence = Column(Float, default=1.0)
    category = Column(String(50), default="GENERAL")
    priority = Column(String(20), default="NORMAL")
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    witnesses = relationship("TicketWitness", back_populates="ticket", cascade="all, delete-orphan")


class TicketWitness(Base):
    __tablename__ = "ticket_witnesses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.ticket_id"), nullable=False)
    witness_id = Column(BigInteger, nullable=False)
    approved = Column(Boolean, nullable=False)
    voted_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("SupportTicket", back_populates="witnesses")


class UserLevel(Base):
    __tablename__ = "user_levels"

    guild_id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, primary_key=True, nullable=False)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    last_message_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_guild_user_level"),
    )


class DecisionLogEntry(Base):
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    command = Column(String(100), nullable=False)
    check_result = Column(Text, nullable=False)
    execution_step = Column(Text, nullable=False)
    outcome = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class UserStrike(Base):
    __tablename__ = "user_strikes"

    strike_id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    user_id = Column(BigInteger, index=True, nullable=False)
    mod_id = Column(BigInteger, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AnonymousReport(Base):
    __tablename__ = "anonymous_reports"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    content = Column(Text, nullable=False)
    evidence_url = Column(Text, nullable=True)
    status = Column(String(20), default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)


class MemberHistory(Base):
    __tablename__ = "member_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, index=True, nullable=False)
    user_id = Column(BigInteger, index=True, nullable=False)
    first_joined_at = Column(DateTime, default=datetime.utcnow)
    last_joined_at = Column(DateTime, default=datetime.utcnow)
    join_count = Column(Integer, default=1)

