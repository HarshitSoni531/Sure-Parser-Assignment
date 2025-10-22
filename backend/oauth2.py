from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from .database import get_db
from . import models
from .JWTtoken import verify_token

# If your auth router has NO prefix, keep "/login".
# If you add a prefix (e.g. router = APIRouter(prefix="/auth")), change to "/auth/login".
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_token(token)  # {'email': ...}
        email = payload["email"]
    except JWTError:
        raise creds_exc

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise creds_exc
    return user
