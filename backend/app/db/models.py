"""Tables: customers, orders, tickets."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # e.g. 1001 (customer says "#1001")
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    item: Mapped[str] = mapped_column(String(150))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="processing")  # processing/shipped/delivered/cancelled
    eta: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shipping_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Refund info (filled by process_refund tool)
    refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    refund_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Stripe test payment made for this order (None for the seed orders)
    payment_intent_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)  # full context for the human agent
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/in_progress/resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # How to reach the customer, and what support told them
    contact_email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="tickets")
