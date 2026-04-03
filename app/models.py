from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Horse(Base):
    __tablename__ = "horses"

    epc: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    breed: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # ISO date string
    implant_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)    # ISO date string
    implant_vet: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owners: Mapped[list["Owner"]] = relationship("Owner", back_populates="horse", cascade="all, delete-orphan")
    trainers: Mapped[list["Trainer"]] = relationship("Trainer", back_populates="horse", cascade="all, delete-orphan")
    vet_records: Mapped[list["VetRecord"]] = relationship("VetRecord", back_populates="horse", cascade="all, delete-orphan")
    race_entries: Mapped[list["RaceEntry"]] = relationship("RaceEntry", back_populates="horse")
    gate_reads: Mapped[list["GateRead"]] = relationship("GateRead", back_populates="horse")
    race_results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="horse")


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

    venue: Mapped["VenueRecord"] = relationship("VenueRecord", back_populates="gate_records")


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venue_records.venue_id"), nullable=False)
    race_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    surface: Mapped[str] = mapped_column(String, default="turf")
    conditions: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | active | finished

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