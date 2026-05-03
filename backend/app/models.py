from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True)
    start_at = Column(DateTime, nullable=False, unique=True)
    duration_minutes = Column(Integer, nullable=False, default=15)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    booking = relationship("Booking", back_populates="slot", uselist=False, cascade="all, delete-orphan")

    @property
    def is_booked(self) -> bool:
        return self.booking is not None


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_booking_slot"),)

    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    child_first_name = Column(String(100), nullable=False)
    child_last_name = Column(String(100), nullable=False)
    parent_note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    slot = relationship("Slot", back_populates="booking")
