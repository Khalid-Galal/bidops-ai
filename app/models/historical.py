"""HistoricalPrice model — the corpus for price-benchmark learning."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HistoricalPrice(Base, TimestampMixin):
    """A single observed historical unit rate, used for benchmark suggestions.

    Sources: imported rate sheets, snapshots of a project's priced BOQ, or
    accepted/corrected user feedback. Decoupled from any one project so it can
    be reused across tenders.
    """

    __tablename__ = "historical_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    trade_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Provenance / traceability
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. import:/project:/feedback
    source_project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<HistoricalPrice {self.description[:40]} @ {self.rate}>"
