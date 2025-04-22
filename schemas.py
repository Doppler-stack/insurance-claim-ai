from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.generics import GenericModel


# Match ClaimStatus enum for updates
class ClaimStatusEnum(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    UNDER_REVIEW = "Under Review"


# Incoming request to create a claim
class ClaimCreate(BaseModel):
    claimant_name: str
    claim_type: str
    amount: float
    description: Optional[str] = None


# Update just the status
class StatusUpdate(BaseModel):
    new_status: ClaimStatusEnum


# Full outgoing response
class ClaimOut(BaseModel):
    id: int
    claimant_name: str
    claim_type: str
    amount: float
    description: Optional[str]
    document_path: Optional[str]
    file_name: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    status: ClaimStatusEnum
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# OCR result model
class ClaimAnalysisResponse(BaseModel):
    claim_id: int
    source_file: str
    extracted_text: str

    model_config = ConfigDict(from_attributes=True)  # Enables ORM mode


# Generic API wrapper for consistent "status + data" response format
T = TypeVar("T")


class APIResponse(GenericModel, Generic[T]):
    status: str
    data: T
