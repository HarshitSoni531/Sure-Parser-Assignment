from typing import List, Optional
from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[EmailStr] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    class Config:
        from_attributes = True

class TransactionInDB(BaseModel):
    id: int
    date: str
    description: str
    amount: str
    class Config:
        from_attributes = True

class StatementInDB(BaseModel):
    id: int
    issuer: str
    card_variant: str | None
    card_last_4: str | None
    billing_cycle: str | None
    payment_due_date: str | None
    total_amount_due: str | None
    parsed_at: str | None
    pdf_path: str | None
    json_path: str | None
    class Config:
        from_attributes = True

class StatementWithTxns(StatementInDB):
    transactions: List[TransactionInDB] = []

class ParseResponse(BaseModel):
    statement: StatementInDB
    transactions: List[TransactionInDB]
