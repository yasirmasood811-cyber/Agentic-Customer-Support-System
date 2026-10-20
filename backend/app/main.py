"""FastAPI app. Run from backend/:  uvicorn app.main:app --reload --port 8000
Docs (Swagger): http://localhost:8000/docs
Public:  /api/health, /api/chat          Admin only (login first): /api/tickets, /api/orders"""
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth, payments
from app.db import models
from app.db.database import Base, engine, get_db
from app.db.migrate import ensure_columns
from app.graph import get_graph
from app.notifications import notify_customer_ticket_update
from app.schemas import (ChatRequest, CustomerOut, LoginRequest, LoginResponse, OrderCreate, OrderOut,
                         TicketOut, TicketUpdate)
from app.streaming import chat_events


def _warm_up():
    """Load the embedding model in the background so the first chat is not slow."""
    try:
        from app.tools.kb_tools import _retriever
        _retriever()
    except Exception as e:  # e.g. docs not ingested yet
        print(f"[warm-up skipped] {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns()  # adds new columns to existing tables
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="ShopEase Support Agent API", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- public ----------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Streams events (SSE). React reads them one by one."""
    return StreamingResponse(
        chat_events(get_graph(), req.message, req.thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------- admin login ----------------
@app.post("/api/admin/login", response_model=LoginResponse)
def admin_login(body: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    return {"token": auth.login(body.password, ip)}


@app.post("/api/admin/logout")
def admin_logout(authorization: Optional[str] = Header(default=None)):
    auth.logout(auth.bearer_token(authorization))
    return {"ok": True}


# ---------------- admin only ----------------
def _ticket_out(t: models.Ticket) -> TicketOut:
    out = TicketOut.model_validate(t)
    if t.customer:
        out.customer_name, out.customer_email = t.customer.name, t.customer.email
    return out


@app.get("/api/tickets", response_model=list[TicketOut], dependencies=[Depends(auth.require_admin)])
def list_tickets(db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).order_by(models.Ticket.id.desc()).all()
    return [_ticket_out(t) for t in tickets]


@app.patch("/api/tickets/{ticket_id}", response_model=TicketOut, dependencies=[Depends(auth.require_admin)])
def update_ticket(ticket_id: int, body: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.get(models.Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    note = (body.note or "").strip()
    status_changed = ticket.status != body.status
    ticket.status = body.status
    if note:
        ticket.resolution_note = note
    if status_changed:
        ticket.resolved_at = datetime.utcnow() if body.status == "resolved" else None
    db.commit()
    db.refresh(ticket)

    out = _ticket_out(ticket)
    if not body.notify:
        out.notification = "not requested"
    elif not (status_changed or note):
        out.notification = "skipped: nothing new to tell the customer"
    else:
        out.notification = notify_customer_ticket_update(
            ticket.id, ticket.reason, ticket.status, note or None,
            ticket.contact_email, ticket.customer.name if ticket.customer else None,
        )
    return out


@app.get("/api/orders", response_model=list[OrderOut], dependencies=[Depends(auth.require_admin)])
def list_orders(db: Session = Depends(get_db)):
    orders = db.query(models.Order).order_by(models.Order.id).all()
    result = []
    for o in orders:
        out = OrderOut.model_validate(o)
        out.customer_name, out.customer_email = o.customer.name, o.customer.email
        result.append(out)
    return result


@app.get("/api/customers", response_model=list[CustomerOut], dependencies=[Depends(auth.require_admin)])
def list_customers(db: Session = Depends(get_db)):
    return db.query(models.Customer).order_by(models.Customer.id).all()


def _order_out(o: models.Order) -> OrderOut:
    out = OrderOut.model_validate(o)
    out.customer_name, out.customer_email = o.customer.name, o.customer.email
    return out


@app.post("/api/orders", response_model=OrderOut, status_code=201, dependencies=[Depends(auth.require_admin)])
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    """Admin 'Add order'. Ids are assigned here (the seed script used fixed ids, so the database counters are behind).
    A Stripe TEST payment is created for the order (if asked) and its id is stored, so a later refund uses it."""
    new_customer = None
    if body.new_customer:
        nc = body.new_customer
        same = db.query(models.Customer).filter(func.lower(models.Customer.email) == nc.email.strip().lower()).first()
        if same:
            raise HTTPException(status_code=409, detail=(
                f"A customer with this email already exists ({same.name}, id {same.id}). Choose them from the list, "
                "or use a different email (for example yourname+test2@gmail.com)."))
        new_customer = models.Customer(id=(db.query(func.max(models.Customer.id)).scalar() or 0) + 1,
                                       name=nc.name, email=nc.email.strip(), phone=(nc.phone or "").strip() or None)
        customer_id = new_customer.id
    else:
        customer = db.get(models.Customer, body.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer_id = customer.id

    order_id = max(1000, db.query(func.max(models.Order.id)).scalar() or 0) + 1
    amount = round(body.amount, 2)

    # Stripe first (before touching the database). If it fails the order is still saved, with a warning.
    payment_id, warning = None, None
    if body.create_payment:
        try:
            payment_id = payments.create_test_payment(amount, order_id)
        except Exception as e:
            warning = (f"Order saved, but the Stripe test payment could not be created ({str(e)[:150]}). "
                       "A refund for this order will use the create-then-refund shortcut.")

    order = models.Order(
        id=order_id, customer_id=customer_id, item=body.item, amount=amount, status=body.status,
        eta=(body.eta or "").strip() or "-", shipping_address=(body.shipping_address or "").strip() or None,
        created_at=datetime.utcnow(), refunded=False, payment_intent_id=payment_id,
    )
    if new_customer:
        db.add(new_customer)
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not save the order (duplicate id or email). Please try again.")
    db.refresh(order)
    out = _order_out(order)
    out.payment_warning = warning
    return out
