from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Хранятся только зашифрованные значения (расшифровка только при отображении/экспорте)
    email: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    referrer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)  # Подписан на закрытый канал = прошёл очный этап
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # Подтверждён через CSV из CRM
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    referrals: Mapped[List["Referral"]] = relationship(
        "Referral",
        foreign_keys="Referral.referrer_id",
        back_populates="referrer",
        lazy="selectin"
    )
    grade_claims: Mapped[List["GradeClaim"]] = relationship(
        "GradeClaim",
        back_populates="user",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    referrer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referrer_id],
        back_populates="referrals"
    )

    def __repr__(self) -> str:
        return f"<Referral(referrer={self.referrer_id}, referred={self.referred_id})>"


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    recipients_count: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Broadcast(id={self.id}, recipients={self.recipients_count})>"


class Grade(Base):
    """Рубеж по количеству рефералов с наградами."""
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referral_threshold: Mapped[int] = mapped_column(Integer, nullable=False)  # рубеж (например 10)
    rewards: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array ["мерч", "тд"]
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    claims: Mapped[List["GradeClaim"]] = relationship(
        "GradeClaim",
        back_populates="grade",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Grade(id={self.id}, threshold={self.referral_threshold})>"


class UtmToken(Base):
    """Короткий токен для UTM (один зашифрованный значение → один токен)."""
    __tablename__ = "utm_tokens"
    __table_args__ = (UniqueConstraint("encrypted_value", "value_type", name="uq_utm_tokens_enc_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'email' | 'phone'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UtmToken(token={self.token}, type={self.value_type})>"


class GradeClaim(Base):
    """Фиксация выдачи награды за грейд пользователю."""
    __tablename__ = "grade_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False, index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    issued_by_admin: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="grade_claims")
    grade: Mapped["Grade"] = relationship("Grade", back_populates="claims")

    def __repr__(self) -> str:
        return f"<GradeClaim(user={self.user_id}, grade={self.grade_id})>"
