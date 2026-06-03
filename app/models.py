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

    chip_id: Mapped[str] = mapped_column(String, primary_key=True)  # Jockey Club LF microchip (ISO 11784/11785, 15-digit)
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
    race_results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="horse")
    workouts: Mapped[list["WorkoutRecord"]] = relationship("WorkoutRecord", back_populates="horse", cascade="all, delete-orphan")
    checkins: Mapped[list["CheckInRecord"]] = relationship("CheckInRecord", back_populates="horse", cascade="all, delete-orphan")
    test_barn_records: Mapped[list["TestBarnRecord"]] = relationship("TestBarnRecord", back_populates="horse", cascade="all, delete-orphan")
    biosensor_readings: Mapped[list["BiosensorReading"]] = relationship("BiosensorReading", back_populates="horse", cascade="all, delete-orphan")
    treatments: Mapped[list["TreatmentRecord"]] = relationship("TreatmentRecord", back_populates="horse", cascade="all, delete-orphan")
    stewards_rulings: Mapped[list["StewardsRuling"]] = relationship("StewardsRuling", back_populates="horse")
    vet_checks: Mapped[list["VetCheckRecord"]] = relationship("VetCheckRecord", back_populates="horse", cascade="all, delete-orphan")


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False)
    owner_name: Mapped[str] = mapped_column(String, nullable=False)
    from_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # None = current owner

    horse: Mapped["Horse"] = relationship("Horse", back_populates="owners")


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False)
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
    races: Mapped[list["Race"]] = relationship("Race", back_populates="venue")


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
    results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="race", cascade="all, delete-orphan")


class RaceEntry(Base):
    __tablename__ = "race_entries"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_chip_id"),
        UniqueConstraint("race_id", "saddle_cloth"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False)
    saddle_cloth: Mapped[str] = mapped_column(String, nullable=False)
    jockey: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="entries")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="race_entries")


class RaceResult(Base):
    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint("race_id", "horse_chip_id"),
        UniqueConstraint("race_id", "finish_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False)
    finish_position: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    race: Mapped["Race"] = relationship("Race", back_populates="results")
    horse: Mapped["Horse"] = relationship("Horse", back_populates="race_results")


class VetRecord(Base):
    __tablename__ = "vet_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False)
    event_date: Mapped[str] = mapped_column(String, nullable=False)  # ISO date string
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "implant", "clearance", "treatment"
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vet_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    horse: Mapped["Horse"] = relationship("Horse", back_populates="vet_records")


class WorkoutRecord(Base):
    __tablename__ = "workout_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
    workout_date: Mapped[str] = mapped_column(String(10), nullable=False)          # YYYY-MM-DD
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    surface: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)      # Dirt | Turf | Synthetic
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)     # workout time in ms
    track_condition: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Fast | Good | Soft | Heavy
    trainer_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    rider_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)       # exercise rider
    clocker_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)     # who clocked the work
    timekeeper_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    splits_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)             # JSON list of sectional dicts
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")   # manual | sim
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    horse: Mapped["Horse"] = relationship("Horse", back_populates="workouts")


class CheckInRecord(Base):
    __tablename__ = "checkin_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True, index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    scanned_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # thermal chip read

    horse: Mapped["Horse"] = relationship("Horse", back_populates="checkins")


class TestBarnRecord(Base):
    __tablename__ = "test_barn_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
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


# ------------------------------------------------------------------ #
# Biosensor (Item 2)
# ------------------------------------------------------------------ #

class BiosensorReading(Base):
    __tablename__ = "biosensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=lambda: datetime.now(timezone.utc))
    heart_rate_bpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stride_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="wearable")

    horse: Mapped["Horse"] = relationship("Horse", back_populates="biosensor_readings")


# ------------------------------------------------------------------ #
# Phase 3 — HISA Reporting Module
# ------------------------------------------------------------------ #

class TreatmentRecord(Base):
    """ADMC: medication/treatment record distinct from free-form VetRecord."""
    __tablename__ = "treatment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
    treatment_date: Mapped[str] = mapped_column(String(10), nullable=False)          # YYYY-MM-DD
    substance: Mapped[str] = mapped_column(String(200), nullable=False)
    dose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)         # IV/IM/oral/topical
    withdrawal_time_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prescribed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    administered_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_prohibited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    horse: Mapped["Horse"] = relationship("Horse", back_populates="treatments")


class StewardsRuling(Base):
    """Official rulings with 48-hour HISA submission deadline."""
    __tablename__ = "stewards_rulings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ruling_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True, index=True)
    horse_chip_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=True, index=True)
    jockey_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    rule_violated: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    penalty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")  # draft|submitted|accepted|rejected
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    horse: Mapped[Optional["Horse"]] = relationship("Horse", back_populates="stewards_rulings")


class SurfaceConditionLog(Base):
    """Daily track surface conditions for HISA Rule 2151/2154."""
    __tablename__ = "surface_condition_logs"
    __table_args__ = (UniqueConstraint("venue_id", "logged_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venue_records.venue_id"), nullable=False, index=True)
    logged_date: Mapped[str] = mapped_column(String(10), nullable=False)             # YYYY-MM-DD
    surface_type: Mapped[str] = mapped_column(String(32), nullable=False)            # Dirt/Turf/Synthetic
    going_description: Mapped[str] = mapped_column(String(64), nullable=False)       # Fast/Good/Soft/Heavy/Firm
    moisture_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    maintenance_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logged_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HISASubmission(Base):
    """Tracks every HISA submission — the backbone of the Compliance Dashboard."""
    __tablename__ = "hisa_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # WORKOUTS|ADMC_TREATMENT|ADMC_SAMPLE|SURFACE|STEWARDS_RULING|CHECKIN
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    # pending|submitted|accepted|rejected|needs_correction
    source_record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    horse_chip_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)  # denormalised
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# ------------------------------------------------------------------ #
# Phase 4 — Training Center Module
# ------------------------------------------------------------------ #

class VetCheckRecord(Base):
    """Structured barn/training vet check — distinct from clinical VetRecord."""
    __tablename__ = "vet_check_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
    check_date: Mapped[str] = mapped_column(String(10), nullable=False)              # YYYY-MM-DD
    check_type: Mapped[str] = mapped_column(String(32), nullable=False)              # routine|lameness|pre_shipment|post_race|other
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)                 # cleared|restricted|scratched|referred
    vet_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    race_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("races.id"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    horse: Mapped["Horse"] = relationship("Horse", back_populates="vet_checks")


# ------------------------------------------------------------------ #
# Phase 5 — Race Day Operations Module
# ------------------------------------------------------------------ #

class ScratchRecord(Base):
    """Horse scratched from a race — creates HISA scratch documentation."""
    __tablename__ = "scratch_records"
    __table_args__ = (UniqueConstraint("race_id", "horse_chip_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False, index=True)
    horse_chip_id: Mapped[str] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=False, index=True)
    scratch_type: Mapped[str] = mapped_column(String(32), nullable=False)  # veterinary|trainer|steward|official
    declared_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   default=lambda: datetime.now(timezone.utc))
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RidingCropViolation(Base):
    """Rule 2280/2281 riding crop violation — generates HISA submission."""
    __tablename__ = "riding_crop_violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[int] = mapped_column(Integer, ForeignKey("races.id"), nullable=False, index=True)
    horse_chip_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("horses.chip_id"), nullable=True, index=True)
    jockey_name: Mapped[str] = mapped_column(String(128), nullable=False)
    crop_count: Mapped[int] = mapped_column(Integer, nullable=False)        # number of crop uses
    violation_determined: Mapped[bool] = mapped_column(Boolean, default=False)
    penalty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    official_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    race_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
