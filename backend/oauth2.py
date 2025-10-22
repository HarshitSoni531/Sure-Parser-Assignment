from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from database import get_db
import models
from JWTtoken import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Verifies the JWT token and retrieves the current user from the database.
    Raises HTTP 401 if the token is invalid or user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(token, credentials_exception)
        user_email: str = payload.get("sub")
        if user_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == user_email).first()
    if user is None:
        raise credentials_exception

    return user
