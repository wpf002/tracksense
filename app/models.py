from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ------------------------------------------------------------------ #
# Multi-tenancy
# ------------------------------------------------------------------ #

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)   # UUID
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # URL-safe
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))

    venues: Mapped[list["VenueRecord"]] = relationship("VenueRecord", back_populates="tenant")
    horses: Mapped[list["Horse"]] = relationship("Horse", back_populates="tenant")
    races: Mapped[list["Race"]] = relationship("Race", back_populates="tenant")
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    webhook_subscriptions: Mapped[list["WebhookSubscription"]] = relationship(
        "WebhookSubscription", back_populates="tenant"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship("ApiKey", back_populates="tenant")


class Horse(Base):
    __tablename__ = "horses"

    epc: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    breed: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # ISO date string
    implant_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)    # ISO date string
    implant_vet: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    racing_api_horse_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="horses")
    owners: Mapped[list["Owner"]] = relationship("Owner", back_populates="horse", cascade="all, delete-orphan")
    trainers: Mapped[list["Trainer"]] = relationship("Trainer", back_populates="horse", cascade="all, delete-orphan")
    vet_records: Mapped[list["VetRecord"]] = relationship("VetRecord", back_populates="horse", cascade="all, delete-orphan")
    race_entries: Mapped[list["RaceEntry"]] = relationship("RaceEntry", back_populates="horse")
    gate_reads: Mapped[list["GateRead"]] = relationship("GateRead", back_populates="horse")
    race_results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="horse")
    workouts: Mapped[list["WorkoutRecord"]] = relationship("WorkoutRecord", back_populates="horse", cascade="all, delete-orphan")
    checkins: Mapped[list["CheckInRecord"]] = relationship("CheckInRecord", back_populates="horse", cascade="all, delete-orphan")
    test_barn_records: Mapped[list["TestBarnRecord"]] = relationship("TestBarnRecord", back_populates="horse", cascade="all, delete-orphan")


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False)
    owner_name: Mapped[str] = mapped_column(String, nullable=False)
    from_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # None = current owner

    horse: Mapped["Horse"] = relationship("Horse", back_populates="owners")


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False)
    trainer_name: Mapped[str] = mapped_column(String, nullable=False)
    from_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    horse: Mapped["Horse"] = relationship("Horse", back_populates="trainers")


class VenueRecord(Base):
    __tablename__ = "venue_records"

    venue_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False)

    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="venues")
    gate_records: Mapped[list["GateRecord"]] = relationship("GateRecord", back_populates="venue", cascade="all, delete-orphan")
    races: Mapped[list["Race"]] = relationship("Race", back_populates="venue")


class GateRecord(Base):
    __tablename__ = "gate_records"
    __table_args__ = (UniqueConstraint("venue_id", "reader_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venue_records.venue_id"), nullable=False)
    reader_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    is_finish: Mapped[bool] = mapped_column(Boolean, default=False)
    position_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # normalised 0.0–1.0
    position_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # normalised 0.0–1.0

    venue: Mapped["VenueRecord"] = relationship("VenueRecord", back_populates="gate_records")


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venue_records.venue_id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    race_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    surface: Mapped[str] = mapped_column(String, default="turf")
    conditions: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | active | finished
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="races")
    venue: Mapped["VenueRecord"] = relationship("VenueRecord", back_populates="races")
    entries: Mapped[list["RaceEntry"]] = relationship("RaceEntry", back_populates="race", cascade="all, delete-orphan")
    gate_reads: Mapped[list["GateRead"]] = relationship("GateRead", back_populates="race", cascade="all, delete-orphan")
    results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="race", cascade="all, delete-orphan")


class RaceEntry(Base):
    __tablename__ = "race_entries"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_epc"),
        UniqueConstraint("race_id", "saddle_cloth"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False)
    saddle_cloth: Mapped[str] = mapped_column(String, nullable=False)
    jockey: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="entries")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="race_entries")


class GateRead(Base):
    __tablename__ = "gate_reads"
    __table_args__ = (UniqueConstraint("race_id", "horse_epc", "reader_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False)
    reader_id: Mapped[str] = mapped_column(String, nullable=False)
    gate_name: Mapped[str] = mapped_column(String, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    race_elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    wall_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="gate_reads")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="gate_reads")


class RaceResult(Base):
    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_epc"),
        UniqueConstraint("race_id", "finish_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False)
    finish_position: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    race: Mapped["Race"] = relationship("Race", back_populates="results")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="race_results")


class VetRecord(Base):
    __tablename__ = "vet_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False)
    event_date: Mapped[str] = mapped_column(String, nullable=False)  # ISO date string
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "implant", "clearance", "treatment"
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vet_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    horse: Mapped["Horse"] = relationship("Horse", back_populates="vet_records")


class WorkoutRecord(Base):
    __tablename__ = "workout_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False, index=True)
    workout_date: Mapped[str] = mapped_column(String(10), nullable=False)          # YYYY-MM-DD
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    surface: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)      # Dirt | Turf | Synthetic
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)     # workout time in ms
    track_condition: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Fast | Good | Soft | Heavy
    trainer_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    horse: Mapped["Horse"] = relationship("Horse", back_populates="workouts")


class CheckInRecord(Base):
    __tablename__ = "checkin_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False, index=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True, index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    scanned_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    horse: Mapped["Horse"] = relationship("Horse", back_populates="checkins")


class TestBarnRecord(Base):
    __tablename__ = "test_barn_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_epc: Mapped[str] = mapped_column(String, ForeignKey("horses.epc"), nullable=False, index=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True)
    checkin_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    checkin_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    checkout_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # None = still in barn
    checkout_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sample_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)       # Pending | Clear | Positive | Void
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    horse: Mapped["Horse"] = relationship("Horse", back_populates="test_barn_records")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)          # UUID
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # JSON blob
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="race.finished")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="webhook_subscriptions")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        "WebhookDelivery", back_populates="subscription", cascade="all, delete-orphan"
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)          # UUID
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhook_subscriptions.id"), nullable=False, index=True
    )
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    subscription: Mapped["WebhookSubscription"] = relationship(
        "WebhookSubscription", back_populates="deliveries"
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)          # UUID
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA-256 hex
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="api_keys")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="viewer")
    # roles: admin | steward | trainer | vet | viewer
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="users")