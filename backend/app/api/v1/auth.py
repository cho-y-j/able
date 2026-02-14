from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, UserResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.account_lockout import get_account_lockout, validate_password_strength
from app.core.audit import audit_login_success, audit_login_failed, audit_register
from app.api.v1.deps import get_current_user

router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
              summary="Register a new user",
              description="Create a new user account. Password must be 8+ chars with uppercase, lowercase, and digit.")
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Password policy
    pw_error = validate_password_strength(req.password)
    if pw_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_error)

    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.flush()

    audit_register(str(user.id), req.email, _client_ip(request))

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse,
              summary="Login and get JWT tokens",
              description="Authenticate with email/password. Returns access + refresh tokens. Account locks after 5 failed attempts.")
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    lockout = get_account_lockout()

    # Check lockout
    if lockout.is_locked(req.email):
        audit_login_failed(req.email, ip, ua, reason="account_locked")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.",
        )

    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        locked = lockout.record_failure(req.email)
        audit_login_failed(req.email, ip, ua)
        if locked:
            from app.core.audit import audit_account_locked
            audit_account_locked(str(user.id) if user else "unknown", req.email, ip)
        remaining = lockout.get_remaining_attempts(req.email)
        detail = "Invalid credentials"
        if remaining > 0:
            detail += f" ({remaining} attempts remaining)"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    lockout.record_success(req.email)
    audit_login_success(str(user.id), req.email, ip, ua)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse, summary="Refresh JWT tokens")
async def refresh(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )
