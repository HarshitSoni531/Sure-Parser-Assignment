from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base  # relative

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    statements = relationship("Statement", back_populates="user", cascade="all, delete-orphan")


class Statement(Base):
    __tablename__ = "statements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    issuer = Column(String(50), index=True)
    card_variant = Column(String(120))
    card_last_4 = Column(String(8))
    billing_cycle = Column(String(64))
    payment_due_date = Column(String(32))
    total_amount_due = Column(String(32))

    parsed_at = Column(String(40))
    pdf_path = Column(Text)
    json_path = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="statements")
    transactions = relationship("Transaction", back_populates="statement", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)

    date = Column(String(32))
    description = Column(Text)
    amount = Column(String(32))

    statement = relationship("Statement", back_populates="transactions")

