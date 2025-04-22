from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Float, Integer, String, Text

from database import Base  # Our base class for defining models

# ----------------------------
# ClaimStatus Enum
# ----------------------------


# Using an Enum to make claim status less error-prone
# (Way better than relying on string comparisons everywhere)
class ClaimStatus(PyEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    UNDER_REVIEW = "Under Review"  # Might add more states later (e.g., Escalated)


# ----------------------------
# Claim Model
# ----------------------------


# Represents a claim record in the database
class Claim(Base):
    __tablename__ = "claims"  # Table naming convention: plural + snake_case

    id = Column(Integer, primary_key=True, index=True)  # Auto-incrementing ID
    claimant_name = Column(String, nullable=False)  # Person who filed the claim
    claim_type = Column(String, nullable=False)  # e.g. 'Auto', 'Home', etc.
    amount = Column(Float, nullable=False)  # Claim value in dollars
    description = Column(String, nullable=True)  # Optional notes

    document_path = Column(
        String, nullable=True
    )  # File location (e.g., S3 or local path)

    file_name = Column(String, nullable=True)  # Original uploaded file name
    file_type = Column(String, nullable=True)  # Detected MIME type (e.g., image/png)
    file_size = Column(Integer, nullable=True)  # File size in bytes

    # Using Enum ensures controlled values — no rogue status strings
    status = Column(Enum(ClaimStatus), default=ClaimStatus.PENDING)

    # Using lambda + timezone-aware datetime to avoid deprecated utcnow()
    # This ensures consistency across systems regardless of local timezone
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Automatically updates when record is modified (helpful for audits/logs)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    ocr_text = Column(
        Text, nullable=True
    )  # Field for storing extracted OCR (audit/log-style)

    def __repr__(self):
        # For debugging/logs — gives a quick peek at core info
        return (
            f"<Claim(id={self.id}, claimant='{self.claimant_name}', "
            f"amount={self.amount}, status='{self.status.value}')>"
        )

    # NOTE: If this grows, consider breaking into ClaimBase / ClaimFull or adding validation
