import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from auth import (
    DUMMY_PASSWORD_HASH,
    TOKEN_LIFETIME_SECONDS,
    create_access_token,
    decode_access_token,
    get_current_user_id,
    hash_password,
    verify_password,
)
from admin_auth import (
    ADMIN_COOKIE_NAME,
    admin_configuration,
    admin_subject,
    require_admin,
)
from database import get_db
from schemas import (
    DriverTripComplete,
    DriverTripStart,
    ChatMessageCreate,
    ObservationDecision,
    ObservationCreate,
    ObservationReviewRequest,
    RoleTransitionRequest,
    StaffAccountCreate,
    UserLogin,
    UserRegister,
    UserRole,
)
from message_crypto import decrypt_message, encrypt_message
from message_crypto import validate_encryption_key
from safety_assistant import answer as answer_safety_question
from safety_assistant import nearby_stations

VERIFIED_REPORT_BONUS = 10
LOGGER = logging.getLogger(__name__)
DRIVER_ROUTES = (
    "Mirpur 1 – Farmgate",
    "Mirpur 1 – Motijheel",
    "Uttara – Shahbagh",
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_encryption_key()
    yield


app = FastAPI(
    title="SmartTransit AI",
    description=(
        "Private citizen assistance and role-based civic mobility portals "
        "for Bangladesh."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
FRONTEND_DIST = Path(__file__).with_name("frontend") / "dist"
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_DIST / "assets", check_dir=False),
    name="assets",
)


@app.exception_handler(OperationalError)
async def handle_database_unavailable(_, exc: OperationalError):
    LOGGER.exception("Database request failed: %s", exc.__class__.__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": (
                "MySQL is unavailable. Start MySQL in XAMPP and verify "
                "DATABASE_URL."
            )
        },
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="smarttransit_session",
        value=token,
        max_age=TOKEN_LIFETIME_SECONDS,
        httponly=True,
        secure=os.environ.get("APP_ENV") == "production",
        samesite="strict",
        path="/",
    )


def set_admin_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        max_age=TOKEN_LIFETIME_SECONDS,
        httponly=True,
        secure=os.environ.get("APP_ENV") == "production",
        samesite="strict",
        path="/",
    )


def get_level(total_points: int) -> tuple[int, str]:
    if total_points < 100:
        return 1, "Novice Observer"
    if total_points < 1000:
        return min(total_points // 100 + 1, 9), "City Warden"
    return total_points // 100, "Urban Guardian"


def award_points(db: Session, user_id: UUID, points: int) -> dict:
    updated = db.execute(
        text(
            """
            UPDATE user_game_profiles
            SET total_points = total_points + :points,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id, "points": points},
    )
    if updated.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or game profile not found.",
        )
    total_points = db.execute(
        text("SELECT total_points FROM user_game_profiles WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).scalar_one()

    level, title = get_level(total_points)
    db.execute(
        text(
            """
            UPDATE user_game_profiles
            SET current_level = :level,
                is_police_eligible = :eligible,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id, "level": level, "eligible": level >= 10},
    )
    return {
        "user_id": user_id,
        "total_points": total_points,
        "current_level": level,
        "level_title": title,
        "points_awarded": points,
    }


def get_user_profile(db: Session, user_id: UUID):
    profile = db.execute(
        text(
            """
            SELECT u.id, u.full_name, u.profile_image_url, u.user_role,
                   p.total_points, p.current_level, p.is_police_eligible,
                   p.is_driver_trained, p.has_gov_license, p.driver_rating,
                   p.completed_trips
            FROM users AS u
            JOIN user_game_profiles AS p ON p.user_id = u.id
            WHERE u.id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or game profile not found.",
        )
    return profile


def require_same_user(authenticated_user_id: UUID, requested_user_id: UUID) -> None:
    if authenticated_user_id != requested_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only perform this action for your own account.",
        )


def find_police_contacts(db: Session, message: str) -> list[dict]:
    stop_words = {
        "the", "and", "for", "from", "phone", "number", "contact", "police",
        "station", "thana", "duty", "officer", "oc", "please", "tell", "me",
    }
    terms = [
        term
        for term in re.findall(r"[a-z0-9]+", message.casefold())
        if len(term) >= 3 and term not in stop_words
    ][:5]
    if not terms:
        return []

    predicates = []
    parameters = {}
    for index, term in enumerate(terms):
        predicates.append(f"station_name LIKE :term_{index}")
        parameters[f"term_{index}"] = f"%{term}%"
    parameters["source_url"] = (
        "https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf"
    )
    rows = db.execute(
        text(
            """
            SELECT unit_name, station_name, designation, official_phone,
                   listed_phone, new_phone, source_published_on
            FROM police_contacts
            WHERE source_url = :source_url
              AND ("""
            + " OR ".join(predicates)
            + """)
            ORDER BY station_name
            LIMIT 5
            """
        ),
        parameters,
    ).mappings().all()
    return [dict(row) for row in rows]


def authenticated_user(user_id: UUID, profile: dict) -> dict:
    return {
        "id": user_id,
        "full_name": profile["full_name"],
        "profile_image_url": profile["profile_image_url"],
        "user_role": profile["user_role"],
        "total_points": profile["total_points"],
        "current_level": profile["current_level"],
        "level_title": get_level(profile["total_points"])[1],
        "is_police_eligible": profile["is_police_eligible"],
        "is_driver_trained": profile["is_driver_trained"],
        "has_gov_license": profile["has_gov_license"],
        "driver_rating": profile["driver_rating"],
        "completed_trips": profile["completed_trips"],
    }


@app.get("/", include_in_schema=False)
def home():
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="React frontend is not built. Run npm install and npm run build in frontend/.",
        )
    return FileResponse(index)


@app.get("/admin", include_in_schema=False)
def admin_home():
    return home()


@app.post("/api/v1/admin/login")
def login_admin(user_data: UserLogin, response: Response):
    email, password_hash = admin_configuration()
    if email is None or password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin login is not configured. Run configure_admin.py locally.",
        )
    password_valid = verify_password(
        user_data.password,
        password_hash if str(user_data.email).casefold() == email.casefold() else DUMMY_PASSWORD_HASH,
    )
    if not password_valid or str(user_data.email).casefold() != email.casefold():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    set_admin_session_cookie(
        response, create_access_token(admin_subject(email))
    )
    return {"status": "success", "admin_email": email}


@app.get("/api/v1/admin/session")
def read_admin_session(request: Request):
    email, password_hash = admin_configuration()
    if email is None or password_hash is None:
        return {"configured": False, "admin_email": None}
    try:
        authenticated_subject = decode_access_token(
            request.cookies.get(ADMIN_COOKIE_NAME, "")
        )
    except HTTPException:
        return {"configured": True, "admin_email": None}
    if authenticated_subject != admin_subject(email):
        return {"configured": True, "admin_email": None}
    return {"configured": True, "admin_email": email}


@app.post("/api/v1/admin/logout")
def logout_admin(response: Response):
    response.delete_cookie(
        ADMIN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=os.environ.get("APP_ENV") == "production",
        samesite="strict",
    )
    return {"status": "success"}


@app.post("/api/v1/admin/staff", status_code=status.HTTP_201_CREATED)
def create_staff_account(
    user_data: StaffAccountCreate,
    admin_email: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    duplicate = db.execute(
        text(
            "SELECT 1 FROM users WHERE email = :email OR phone = :phone LIMIT 1"
        ),
        {"email": str(user_data.email).lower(), "phone": user_data.phone},
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        )

    user_id = uuid4()
    role = user_data.user_role
    try:
        db.execute(
            text(
                """
                INSERT INTO users
                    (id, full_name, email, phone, user_role, password_hash, created_at)
                VALUES
                    (:id, :full_name, :email, :phone, :user_role, :password_hash,
                     CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": user_id,
                "full_name": user_data.full_name,
                "email": str(user_data.email).lower(),
                "phone": user_data.phone,
                "user_role": role.value,
                "password_hash": hash_password(user_data.password),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO user_game_profiles
                    (user_id, total_points, current_level, is_police_eligible,
                     is_driver_trained, has_gov_license, updated_at)
                VALUES
                    (:user_id, 0, 1, :is_police, :is_driver, :is_driver,
                     CURRENT_TIMESTAMP)
                """
            ),
            {
                "user_id": user_id,
                "is_police": role == UserRole.POLICE,
                "is_driver": role == UserRole.DRIVER,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        ) from exc

    LOGGER.info("Admin %s created %s portal account %s", admin_email, role.value, user_id)
    return {
        "status": "success",
        "user": {
            "id": user_id,
            "full_name": user_data.full_name,
            "email": str(user_data.email).lower(),
            "phone": user_data.phone,
            "user_role": role.value,
        },
    }


@app.get("/api/v1/emergency/contacts")
def read_emergency_contacts(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT code, service_name, phone_number, situations, source_url,
                   source_published_on, verified
            FROM emergency_hotlines
            WHERE active = TRUE
            ORDER BY verified DESC, service_name ASC
            """
        )
    ).mappings().all()
    return {
        "contacts": [
            {
                **dict(row),
                "source_published_on": (
                    row["source_published_on"].isoformat()
                    if row["source_published_on"]
                    else None
                ),
            }
            for row in rows
        ]
    }


@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserRegister,
    response: Response,
    db: Session = Depends(get_db),
):
    duplicate = db.execute(
        text(
            """
            SELECT id FROM users
            WHERE email = :email
               OR phone = :phone
            LIMIT 1
            """
        ),
        {"email": user_data.email, "phone": user_data.phone},
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        )

    user_id = uuid4()
    try:
        db.execute(
            text(
                """
                INSERT INTO users
                    (id, full_name, email, phone, profile_image_url,
                     user_role, password_hash, created_at)
                VALUES
                    (:id, :full_name, :email, :phone, :profile_image_url,
                     :user_role, :password_hash, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": user_id,
                "full_name": user_data.full_name,
                "email": str(user_data.email),
                "phone": user_data.phone,
                "profile_image_url": (
                    str(user_data.profile_image_url)
                    if user_data.profile_image_url
                    else None
                ),
                "user_role": UserRole.CITIZEN.value,
                "password_hash": hash_password(user_data.password),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO user_game_profiles
                    (user_id, total_points, current_level, is_police_eligible,
                     is_driver_trained, has_gov_license, updated_at)
                VALUES (:user_id, 0, 1, FALSE, FALSE, FALSE, CURRENT_TIMESTAMP)
                """
            ),
            {"user_id": user_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        ) from exc

    profile = get_user_profile(db, user_id)
    token = create_access_token(user_id)
    set_session_cookie(response, token)
    return {
        "status": "success",
        "message": "User registered successfully.",
        "user": authenticated_user(user_id, profile),
    }


@app.post("/api/v1/auth/login")
def login_user(
    user_data: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.execute(
        text(
            """
            SELECT id, password_hash
            FROM users
            WHERE LOWER(email) = :email
            """
        ),
        {"email": str(user_data.email).lower()},
    ).mappings().first()
    stored_hash = user["password_hash"] if user is not None else DUMMY_PASSWORD_HASH
    if not verify_password(user_data.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = UUID(str(user["id"]))
    profile = get_user_profile(db, user_id)
    token = create_access_token(user_id)
    set_session_cookie(response, token)
    return {
        "status": "success",
        "user": authenticated_user(user_id, profile),
    }


@app.post("/api/v1/auth/logout")
def logout_user(response: Response):
    response.delete_cookie(
        "smarttransit_session",
        path="/",
        httponly=True,
        secure=os.environ.get("APP_ENV") == "production",
        samesite="strict",
    )
    return {"status": "success"}


@app.get("/api/v1/auth/me")
def read_current_user(
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(db, current_user_id)
    return authenticated_user(current_user_id, profile)


@app.get("/api/v1/auth/session")
def read_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    token = request.cookies.get("smarttransit_session")
    if token is None:
        return {"user": None}
    try:
        user_id = decode_access_token(token)
    except HTTPException:
        response.delete_cookie(
            "smarttransit_session",
            path="/",
            httponly=True,
            secure=os.environ.get("APP_ENV") == "production",
            samesite="strict",
        )
        return {"user": None}
    profile = get_user_profile(db, user_id)
    return {"user": authenticated_user(user_id, profile)}


@app.post("/api/v1/observations", status_code=status.HTTP_201_CREATED)
def submit_observation(
    observation: ObservationCreate,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, observation.reporter_id)
    observation_id = uuid4()
    try:
        db.execute(
            text(
                """
                INSERT INTO bus_observations
                    (id, reporter_id, bus_number, route_name, issue_type,
                     image_url, latitude, longitude, status, created_at, review_note)
                VALUES
                    (:id, :reporter_id, :bus_number, :route_name, :issue_type,
                     :image_url, :latitude, :longitude, 'PENDING', CURRENT_TIMESTAMP, '')
                """
            ),
            {
                "id": observation_id,
                "reporter_id": observation.reporter_id,
                "bus_number": observation.bus_number,
                "route_name": observation.route_name,
                "issue_type": observation.issue_type.value,
                "image_url": (
                    str(observation.image_url) if observation.image_url else None
                ),
                "latitude": observation.latitude,
                "longitude": observation.longitude,
            },
        )
        level = award_points(db, observation.reporter_id, 20)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reporter not found.",
        ) from exc

    return {
        "status": "success",
        "message": "Observation submitted for verification.",
        "observation_id": observation_id,
        "observation_status": "PENDING",
        "points_awarded": 20,
        "level": level,
    }


@app.post("/api/v1/user/promote-to-police")
def promote_to_police(
    request: RoleTransitionRequest,
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, request.user_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Police portal access must be assigned by an authorized administrator.",
    )


@app.post("/api/v1/driver/complete-training")
def complete_driver_training(
    request: RoleTransitionRequest,
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, request.user_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Driver portal access must be assigned by an authorized administrator.",
    )


@app.post("/api/v1/driver/issue-license")
def issue_driver_license(
    request: RoleTransitionRequest,
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, request.user_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Driver portal access must be assigned by an authorized administrator.",
    )


@app.get("/api/v1/user/profile")
def read_user_profile(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, user_id)
    profile = get_user_profile(db, user_id)
    level, title = get_level(profile["total_points"])
    return {
        "id": profile["id"],
        "full_name": profile["full_name"],
        "profile_image_url": profile["profile_image_url"],
        "user_role": profile["user_role"],
        "total_points": profile["total_points"],
        "current_level": level,
        "level_title": title,
        "is_police_eligible": profile["is_police_eligible"],
        "is_driver_trained": profile["is_driver_trained"],
        "has_gov_license": profile["has_gov_license"],
        "driver_rating": profile["driver_rating"],
        "completed_trips": profile["completed_trips"],
    }


@app.get("/api/v1/observations")
def list_observations(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    rows = db.execute(
        text(
            """
            SELECT o.id, o.reporter_id,
                   o.bus_number, o.route_name, o.issue_type, o.image_url,
                   o.latitude, o.longitude, o.status, o.created_at,
                   o.review_note, o.fine_amount_bdt, o.bonus_points_awarded
            FROM bus_observations AS o
            WHERE o.reporter_id = :reporter_id
            ORDER BY o.created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit, "reporter_id": current_user_id},
    ).mappings().all()
    return {"observations": [dict(row) for row in rows]}


@app.get("/api/v1/police/observations")
def police_review_queue(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, user_id)
    profile = get_user_profile(db, user_id)
    if profile["user_role"] != UserRole.POLICE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only POLICE users can access the report review queue.",
        )
    rows = db.execute(
        text(
            """
            SELECT o.id, o.reporter_id, u.full_name AS reporter_name,
                   o.bus_number, o.route_name, o.issue_type, o.image_url,
                   o.latitude, o.longitude, o.created_at
            FROM bus_observations AS o
            JOIN users AS u ON u.id = o.reporter_id
            WHERE o.status = 'PENDING'
            ORDER BY o.created_at ASC
            LIMIT 100
            """
        )
    ).mappings().all()
    return {"observations": [dict(row) for row in rows]}


@app.post("/api/v1/police/observations/{observation_id}/review")
def review_observation(
    observation_id: UUID,
    request: ObservationReviewRequest,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, request.reviewer_id)
    profile = get_user_profile(db, request.reviewer_id)
    if profile["user_role"] != UserRole.POLICE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only POLICE users can review observations.",
        )
    if request.decision == ObservationDecision.REJECTED and request.fine_amount_bdt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A fine can only be recorded for a verified report.",
        )

    bonus_points = (
        VERIFIED_REPORT_BONUS
        if request.decision == ObservationDecision.VERIFIED
        else 0
    )
    try:
        report = db.execute(
            text(
                """
                SELECT reporter_id
                FROM bus_observations
                WHERE id = :observation_id AND status = 'PENDING'
                FOR UPDATE
                """
            ),
            {"observation_id": observation_id},
        ).first()
        if report is None:
            exists = db.execute(
                text("SELECT 1 FROM bus_observations WHERE id = :id"),
                {"id": observation_id},
            ).first()
            db.rollback()
            if exists is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Observation not found.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Observation has already been reviewed.",
            )

        reporter_id = report[0]
        db.execute(
            text(
                """
                UPDATE bus_observations
                SET status = :decision,
                    reviewed_by = :reviewer_id,
                    reviewed_at = CURRENT_TIMESTAMP,
                    review_note = :review_note,
                    fine_amount_bdt = :fine_amount_bdt,
                    bonus_points_awarded = :bonus_points
                WHERE id = :observation_id AND status = 'PENDING'
                """
            ),
            {
                "decision": request.decision.value,
                "reviewer_id": request.reviewer_id,
                "review_note": request.review_note,
                "fine_amount_bdt": str(request.fine_amount_bdt),
                "bonus_points": bonus_points,
                "observation_id": observation_id,
            },
        )
        updated_level = None
        if bonus_points:
            updated_level = award_points(db, reporter_id, bonus_points)
        db.commit()
    except HTTPException:
        db.rollback()
        raise

    return {
        "status": "success",
        "observation_id": observation_id,
        "decision": request.decision,
        "fine_amount_bdt": request.fine_amount_bdt,
        "bonus_points_awarded": bonus_points,
        "reporter_level": updated_level,
    }


@app.get("/api/v1/driver/routes")
def list_driver_routes():
    return {
        "routes": [
            {"route_name": route, "checkpoints": 3} for route in DRIVER_ROUTES
        ]
    }


@app.post("/api/v1/driver/trips", status_code=status.HTTP_201_CREATED)
def start_driver_trip(
    request: DriverTripStart,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, request.user_id)
    profile = get_user_profile(db, request.user_id)
    if (
        profile["user_role"] != UserRole.DRIVER.value
        or not profile["has_gov_license"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A government-licensed DRIVER role is required to start a trip.",
        )
    if request.route_name not in DRIVER_ROUTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Choose a supported Dhaka training route.",
        )

    trip_id = uuid4()
    try:
        db.execute(
            text(
                """
                INSERT INTO driver_trips
                    (id, driver_id, active_driver_id, bus_number, route_name, status, started_at)
                VALUES
                    (:id, :driver_id, :active_driver_id, :bus_number, :route_name,
                     'IN_PROGRESS', CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": trip_id,
                "driver_id": request.user_id,
                "active_driver_id": request.user_id,
                "bus_number": request.bus_number,
                "route_name": request.route_name,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish your active trip before starting another.",
        ) from exc
    return {
        "trip_id": trip_id,
        "status": "IN_PROGRESS",
        "route_name": request.route_name,
        "bus_number": request.bus_number,
        "checkpoints": 3,
    }


@app.post("/api/v1/driver/trips/{trip_id}/complete")
def complete_driver_trip(
    trip_id: UUID,
    request: DriverTripComplete,
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    require_same_user(current_user_id, request.user_id)
    profile = get_user_profile(db, request.user_id)
    if profile["user_role"] != UserRole.DRIVER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only DRIVER users can complete a driving simulation.",
        )

    rating = max(
        1.0,
        round(5.0 - request.hard_brakes * 0.5 - request.speeding_events, 1),
    )
    safety_score = round(
        100
        * (request.safe_actions + 0.5 * request.hard_brakes)
        / 3
    )
    trip = db.execute(
        text(
            """
            SELECT id FROM driver_trips
            WHERE id = :trip_id AND driver_id = :driver_id
              AND status = 'IN_PROGRESS'
            FOR UPDATE
            """
        ),
        {"trip_id": trip_id, "driver_id": request.user_id},
    ).first()
    if trip is None:
        exists = db.execute(
            text(
                "SELECT 1 FROM driver_trips WHERE id = :trip_id AND driver_id = :driver_id"
            ),
            {"trip_id": trip_id, "driver_id": request.user_id},
        ).first()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver trip not found.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This trip is already completed.",
        )

    db.execute(
        text(
            """
            UPDATE driver_trips
            SET status = 'COMPLETED',
                active_driver_id = NULL,
                safety_score = :safety_score,
                rating = :rating,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = :trip_id
              AND driver_id = :driver_id
              AND status = 'IN_PROGRESS'
            """
        ),
        {
            "trip_id": trip_id,
            "driver_id": request.user_id,
            "safety_score": safety_score,
            "rating": rating,
        },
    )

    average_rating = db.execute(
        text(
            """
            SELECT AVG(rating) FROM driver_trips
            WHERE driver_id = :driver_id AND status = 'COMPLETED'
            """
        ),
        {"driver_id": request.user_id},
    ).scalar_one()
    db.execute(
        text(
            """
            UPDATE user_game_profiles
            SET driver_rating = :rating,
                completed_trips = completed_trips + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
            """
        ),
        {"user_id": request.user_id, "rating": average_rating},
    )
    completed_trips = db.execute(
        text("SELECT completed_trips FROM user_game_profiles WHERE user_id = :user_id"),
        {"user_id": request.user_id},
    ).scalar_one()
    db.commit()
    return {
        "trip_id": trip_id,
        "status": "COMPLETED",
        "safety_score": safety_score,
        "trip_rating": rating,
        "driver_rating": round(float(average_rating), 1),
        "completed_trips": completed_trips,
    }


@app.get("/api/v1/game/leaderboard")
def get_leaderboard(
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    profile = get_user_profile(db, current_user_id)
    if profile["user_role"] != UserRole.CITIZEN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The citizen leaderboard is available only in the Citizen portal.",
        )
    rows = db.execute(
        text(
            """
            SELECT p.total_points, p.current_level
            FROM users AS u
            JOIN user_game_profiles AS p ON p.user_id = u.id
            WHERE u.user_role = 'CITIZEN'
            ORDER BY p.total_points DESC, p.updated_at ASC, u.id ASC
            LIMIT 10
            """
        )
    ).mappings().all()
    leaderboard = []
    for rank, row in enumerate(rows, start=1):
        level, level_title = get_level(row["total_points"])
        leaderboard.append(
            {
                "rank": rank,
                "display_name": f"নাগরিক {rank:02d}",
                "total_points": row["total_points"],
                "current_level": level,
                "level_title": level_title,
            }
        )
    return {"status": "success", "leaderboard": leaderboard}


@app.get("/api/v1/chat/history")
def read_chat_history(
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(db, current_user_id)
    rows = db.execute(
        text(
            """
            SELECT id, message_role, encrypted_content, created_at
            FROM chat_messages
            WHERE user_id = :user_id AND portal_role = :portal_role
            ORDER BY id DESC
            LIMIT 100
            """
        ),
        {"user_id": current_user_id, "portal_role": profile["user_role"]},
    ).mappings().all()
    messages = [
        {
            "id": row["id"],
            "role": row["message_role"],
            "content": decrypt_message(row["encrypted_content"]),
            "created_at": row["created_at"],
        }
        for row in reversed(rows)
    ]
    return {"portal_role": profile["user_role"], "messages": messages}


@app.post("/api/v1/chat/messages", status_code=status.HTTP_201_CREATED)
def send_chat_message(
    request: ChatMessageCreate,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(db, current_user_id)
    role = profile["user_role"]
    faqs = db.execute(
        text(
            """
            SELECT category, question, answer, keywords, verified
            FROM emergency_faqs
            WHERE active = TRUE
            """
        )
    ).mappings().all()
    hotlines = db.execute(
        text(
            """
            SELECT code, service_name, phone_number, situations, keywords,
                   source_url, source_published_on, verified
            FROM emergency_hotlines
            WHERE active = TRUE
            """
        )
    ).mappings().all()
    police_contacts = []
    if any(
        term in request.message.casefold()
        for term in (
            "police station",
            "thana",
            "থানার নম্বর",
            "থানার ফোন",
            "oc number",
            "duty officer",
            "police phone",
            "station number",
        )
    ):
        police_contacts = find_police_contacts(db, request.message)
    stations = []
    if request.latitude is not None and role == UserRole.CITIZEN.value:
        rows = db.execute(
            text(
                """
                SELECT name, address, area, phone, latitude, longitude
                FROM police_stations
                WHERE verified = TRUE
                """
            )
        ).mappings().all()
        stations = nearby_stations(
            request.latitude,
            request.longitude,
            [dict(row) for row in rows],
        )

    assistant_reply = answer_safety_question(
        request.message,
        role,
        stations,
        [dict(faq) for faq in faqs],
        [dict(hotline) for hotline in hotlines],
        police_contacts,
    )
    db.execute(
        text(
            """
            INSERT INTO chat_messages (user_id, portal_role, message_role, encrypted_content)
            VALUES (:user_id, :portal_role, 'USER', :content)
            """
        ),
        {
            "user_id": current_user_id,
            "portal_role": role,
            "content": encrypt_message(request.message),
        },
    )
    db.execute(
        text(
            """
            INSERT INTO chat_messages (user_id, portal_role, message_role, encrypted_content)
            VALUES (:user_id, :portal_role, 'ASSISTANT', :content)
            """
        ),
        {
            "user_id": current_user_id,
            "portal_role": role,
            "content": encrypt_message(assistant_reply),
        },
    )
    db.commit()
    return {
        "portal_role": role,
        "reply": assistant_reply,
        "nearby_stations": [
            {
                "name": station["name"],
                "address": station["address"],
                "area": station["area"],
                "phone": station["phone"],
                "distance_km": station["distance_km"],
            }
            for station in stations
        ],
    }
