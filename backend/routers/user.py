from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import UserCreate, UserOut
from hashing import Hash
from oauth2 import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(models.User.email == user_in.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(email=user_in.email, hashed_password=Hash.encrypt(user_in.password))
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.get("/", response_model=List[UserOut])
def all_users(db: Session = Depends(get_db)):
    return [UserOut.model_validate(u, from_attributes=True) for u in db.query(models.User).all()]

@router.get("/{user_id}", response_model=UserOut)
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found")
    return UserOut.model_validate(user, from_attributes=True)

@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return UserOut.model_validate(current_user, from_attributes=True)

