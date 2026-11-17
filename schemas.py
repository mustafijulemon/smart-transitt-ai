from enum import Enum
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator, field_validator
import re

class IdentityType(str, Enum):
    NID = "NID"
    PASSPORT = "PASSPORT"
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"


class UserRole(str, Enum):
    CITIZEN = "CITIZEN"
    POLICE = "POLICE"
    DRIVER = "DRIVER"


class ObservationIssueType(str, Enum):
    OVERCROWDING = "OVERCROWDING"
    FEMALE_SEAT_VIOLATION = "FEMALE_SEAT_VIOLATION"
    FARE_BARGAINING = "FARE_BARGAINING"
    RASH_DRIVING = "RASH_DRIVING"


def validate_email_address(v: str) -> str:
    v = v.strip().lower()
    # Simple regex allowing .local and custom dev domains
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.match(pattern, v):
        raise ValueError("Invalid email format")
    return v


class UserRegister(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    phone: str = Field(min_length=7, max_length=30)
    profile_image_url: HttpUrl | None = None
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email_address(v)


class UserLogin(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email_address(v)


class StaffAccountCreate(UserRegister):
    user_role: UserRole

    @model_validator(mode="after")
    def require_staff_role(self):
        if self.user_role not in {UserRole.POLICE, UserRole.DRIVER}:
            raise ValueError("Admins can create only Police or Driver accounts.")
        return self


class ObservationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reporter_id: UUID
    bus_number: str = Field(min_length=1, max_length=50)
    route_name: str = Field(min_length=1, max_length=150)
    issue_type: ObservationIssueType
    image_url: HttpUrl | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LevelResponse(BaseModel):
    user_id: UUID
    total_points: int = Field(ge=0)
    current_level: int = Field(ge=1)
    level_title: str
    points_awarded: int = Field(ge=0)


class RoleTransitionRequest(BaseModel):
    user_id: UUID


class ObservationDecision(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ObservationReviewRequest(BaseModel):
    reviewer_id: UUID
    decision: ObservationDecision
    review_note: str = Field(default="", max_length=1000)
    fine_amount_bdt: Decimal = Field(default=Decimal("0"), ge=0, le=5000000)


class DriverTripStart(BaseModel):
    user_id: UUID
    route_name: str = Field(min_length=1, max_length=150)
    bus_number: str = Field(min_length=1, max_length=50)


class DriverTripComplete(BaseModel):
    user_id: UUID
    safe_actions: int = Field(default=0, ge=0, le=3)
    hard_brakes: int = Field(default=0, ge=0, le=3)
    speeding_events: int = Field(default=0, ge=0, le=3)

    @model_validator(mode="after")
    def require_three_checkpoints(self):
        if self.safe_actions + self.hard_brakes + self.speeding_events != 3:
            raise ValueError("Choose one driving action at each of the 3 checkpoints.")
        return self


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def require_complete_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Share both latitude and longitude, or neither.")
        return self