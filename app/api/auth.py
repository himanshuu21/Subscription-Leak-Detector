from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
import bcrypt

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserOut
from app.config import settings

router = APIRouter(prefix='/api/auth', tags=['auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login', auto_error=False)
COOKIE_NAME = "sld_session"
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()
oauth = OAuth()
if settings.google_oauth_enabled:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _enforce_login_rate_limit(key: str) -> None:
    now = monotonic()
    cutoff = now - settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    with _rate_limit_lock:
        attempts = _login_attempts[key]
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        if len(attempts) >= settings.LOGIN_RATE_LIMIT_ATTEMPTS:
            retry_after = max(1, int(settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS - (now - attempts[0])))
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        attempts.append(now)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() == "production",
        samesite="strict",
        path="/",
    )

# Using bcrypt directly instead of passlib — passlib 1.7.4 is incompatible
# with bcrypt>=4.0 (API change in hashpw). Direct bcrypt is simpler and stable.
def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = request.cookies.get(COOKIE_NAME) or bearer_token
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/signup", response_model=TokenResponse)
def signup(request: SignupRequest, response: Response, db: Session = Depends(get_db)):
    # No refresh-token rotation in v1 — intentional simplification. Auth is not the feature; the detection pipeline is.
    email = request.email.lower()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already in use")
    
    hashed_password = _hash_password(request.password)
    new_user = User(email=email, hashed_password=hashed_password, auth_provider="local")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": str(new_user.id)})
    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, http_request: Request, response: Response, db: Session = Depends(get_db)):
    client_host = http_request.client.host if http_request.client else "unknown"
    email = request.email.lower()
    rate_key = f"{client_host}:{email}"
    _enforce_login_rate_limit(rate_key)
    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    with _rate_limit_lock:
        _login_attempts.pop(rate_key, None)
    _set_auth_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/google/login", name="google_login")
async def google_login(request: Request):
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    google = oauth.create_client("google")
    redirect_uri = str(request.url_for("google_callback"))
    return await google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    google = oauth.create_client("google")
    try:
        token = await google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse("/?oauth_error=google", status_code=303)

    userinfo = token.get("userinfo") or {}
    email = str(userinfo.get("email", "")).strip().lower()
    google_sub = str(userinfo.get("sub", "")).strip()
    email_verified = userinfo.get("email_verified") is True
    if not email or not google_sub or not email_verified:
        return RedirectResponse("/?oauth_error=unverified", status_code=303)

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user is None:
        user = db.query(User).filter(User.email == email).first()
        if user and user.google_sub and user.google_sub != google_sub:
            return RedirectResponse("/?oauth_error=conflict", status_code=303)
        if user is None:
            user = User(
                email=email,
                hashed_password=None,
                auth_provider="google",
                google_sub=google_sub,
            )
            db.add(user)
        else:
            # A verified Google address may safely add Google login to the
            # existing account with the same normalized email.
            user.google_sub = google_sub
        db.commit()
        db.refresh(user)

    response = RedirectResponse("/upload-page", status_code=303)
    _set_auth_cookie(response, create_access_token({"sub": str(user.id)}))
    return response


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict")
