

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    results: Mapped[list["BenchmarkResult"]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )

class InputSet(Base):
    __tablename__ = "input_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # e.g. "small"
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    num_cases: Mapped[int] = mapped_column(Integer, nullable=False)

    results: Mapped[list["BenchmarkResult"]] = relationship(
        back_populates="input_set", cascade="all, delete-orphan"
    )

class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id"), nullable=False)
    input_set_id: Mapped[int] = mapped_column(ForeignKey("input_sets.id"), nullable=False)
    case_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Which line (0-18)
    time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    bot: Mapped["Bot"] = relationship(back_populates="results")
    input_set: Mapped["InputSet"] = relationship(back_populates="results")
