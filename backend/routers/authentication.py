# backend/routers/authentication.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
import models
from hashing import Hash
from JWTtoken import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from schemas import UserCreate, UserOut, Token  # <-- IMPORTANT

# No change to your imports above

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(models.User.email == user_in.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(email=user_in.email, hashed_password=Hash.encrypt(user_in.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    """
    Accept EITHER:
      - JSON: { "email": "...", "password": "..." }  (your frontend)
      - FORM (OAuth2 Password): username=..., password=... (Swagger UI)
    """
    email = None
    password = None

    ctype = request.headers.get("content-type", "")
    try:
        if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith("multipart/form-data"):
            form = await request.form()
            # OAuth2PasswordRequestForm uses field name 'username' for the login identifier
            email = form.get("username")
            password = form.get("password")
        else:
            body = await request.json()
            email = (body or {}).get("email")
            password = (body or {}).get("password")
    except Exception:
        # If body parsing fails, keep email/password as None
        pass

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Email/username and password required")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not Hash.verify(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        {"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token)

