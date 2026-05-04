from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


# Liste ordonnée des classes proposées (clé en BDD, libellé affiché)
CLASS_LEVELS = [
    ("TPS", "Maternelle TPS — Toute Petite Section"),
    ("PS",  "Maternelle PS — Petite Section"),
    ("MS",  "Maternelle MS — Moyenne Section"),
    ("GS",  "Maternelle GS — Grande Section"),
    ("CP",  "CP — Cours Préparatoire"),
    ("CE1", "CE1 — Cours Élémentaire 1ère année"),
    ("CE2", "CE2 — Cours Élémentaire 2ème année"),
    ("CM1", "CM1 — Cours Moyen 1ère année"),
    ("CM2", "CM2 — Cours Moyen 2ème année"),
]
CLASS_LEVEL_KEYS = {key for key, _ in CLASS_LEVELS}
CLASS_LEVEL_LABELS = dict(CLASS_LEVELS)

ROLE_SUPER_ADMIN = "super_admin"
ROLE_TEACHER = "teacher"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    full_name = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    role = Column(String(20), nullable=False, default=ROLE_TEACHER)
    class_level = Column(String(20), nullable=True)
    class_label = Column(String(255), nullable=True)  # libellé libre, prioritaire à l'affichage
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    slots = relationship("Slot", back_populates="teacher", cascade="all, delete-orphan")

    @property
    def is_super_admin(self) -> bool:
        return self.role == ROLE_SUPER_ADMIN

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    @property
    def class_display(self) -> str:
        """Libellé affiché : class_label si renseigné, sinon le libellé standard du niveau."""
        if self.class_label:
            return self.class_label
        return CLASS_LEVEL_LABELS.get(self.class_level, self.class_level or "")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("teacher_id", "start_at", name="uq_slot_teacher_start"),
    )

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=15)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    teacher = relationship("User", back_populates="slots")
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
