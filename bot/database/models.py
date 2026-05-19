import enum
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    owner = "owner"
    superadmin = "superadmin"
    admin = "admin"
    guest = "guest"


class MessageStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"
    failed = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Unknown")
    username = Column(String(255), nullable=True)
    # Raw Telegram status string: member / administrator / creator / kicked / left
    status = Column(String(32), nullable=False, default="member")
    is_active = Column(Boolean, default=False, nullable=False)
    added_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)

    stats = relationship("MessageStat", back_populates="group", lazy="select")

    def __repr__(self) -> str:
        return f"<Group id={self.chat_id} title={self.title!r} active={self.is_active}>"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    added_by = Column(BigInteger, nullable=True)
    added_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # For existing DBs: ALTER TABLE users ADD COLUMN language_code VARCHAR(8) NOT NULL DEFAULT 'ru';
    language_code = Column(String(8), nullable=False, server_default="ru", default="ru")

    def __repr__(self) -> str:
        return f"<User id={self.user_id} role={self.role} name={self.full_name!r}>"


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    master_message_id = Column(BigInteger, nullable=False)
    master_chat_id = Column(BigInteger, nullable=False)
    # JSON-serialized list of message IDs for media groups
    media_group_ids = Column(Text, nullable=True)
    content_preview = Column(Text, nullable=True)
    status = Column(Enum(MessageStatus), default=MessageStatus.pending, nullable=False)
    censorship_triggered = Column(Boolean, default=False, nullable=False)
    censorship_reason = Column(Text, nullable=True)
    approved_by = Column(BigInteger, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    # ID of the control-panel message (for later editing / deletion)
    control_panel_message_id = Column(BigInteger, nullable=True)
    # Channel post view tracking
    channel_views = Column(Integer, default=0, nullable=False)
    views_synced_at = Column(DateTime(timezone=True), nullable=True)
    content_full = Column(Text, nullable=True)
    zwsp_toggle = Column(Boolean, default=False, nullable=False)  # legacy, unused

    stats = relationship("MessageStat", back_populates="broadcast", lazy="select")

    def __repr__(self) -> str:
        return f"<BroadcastMessage id={self.id} status={self.status}>"


class MessageStat(Base):
    __tablename__ = "message_stats"
    __table_args__ = (UniqueConstraint("broadcast_id", "group_id", name="uq_broadcast_group"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    broadcast_id = Column(Integer, ForeignKey("broadcast_messages.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.chat_id", ondelete="SET NULL"), nullable=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    views = Column(Integer, default=0, nullable=False)        # actual views (from micro-edit)
    member_count = Column(Integer, default=0, nullable=False) # members at delivery time
    zwsp_toggle = Column(Boolean, default=False, nullable=False)
    last_updated = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    broadcast = relationship("BroadcastMessage", back_populates="stats")
    group = relationship("Group", back_populates="stats")


class AnalyticsSource(Base):
    """
    One row per (broadcast × group) — tracks the hub-channel message whose
    view count mirrors reads of the forwarded post in that group.
    """
    __tablename__ = "analytics_sources"
    __table_args__ = (UniqueConstraint("broadcast_id", "group_id", name="uq_hub_broadcast_group"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    broadcast_id = Column(Integer, ForeignKey("broadcast_messages.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(BigInteger, ForeignKey("groups.chat_id", ondelete="SET NULL"), nullable=True)
    hub_message_id = Column(BigInteger, nullable=False)
    hub_message_url = Column(String(255), nullable=True)  # https://t.me/{username}/{id}
    views = Column(Integer, default=0, nullable=False)
    last_synced = Column(DateTime(timezone=True), nullable=True)


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    target_id = Column(BigInteger, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
