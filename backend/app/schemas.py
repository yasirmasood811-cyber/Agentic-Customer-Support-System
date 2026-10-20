"""Request/response shapes for the API."""
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Text = lambda n: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=n)]  # noqa: E731


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: Optional[str] = Field(default=None, max_length=100)  # React sends the same id to keep the conversation memory


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    token: str


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: Optional[int]
    reason: str
    summary: str
    status: str
    created_at: datetime
    contact_email: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    notification: Optional[str] = None  # only set after an update: what happened to the email for the customer


class TicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    note: Optional[str] = Field(default=None, max_length=2000)  # message for the customer
    notify: bool = True  # email the customer about this update


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item: str
    amount: float
    status: str
    eta: Optional[str]
    refunded: bool
    refund_reference: Optional[str]
    payment_intent_id: Optional[str] = None
    payment_warning: Optional[str] = None  # only set when an order was just created
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None


class NewCustomer(BaseModel):
    name: Text(100)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=30)


class OrderCreate(BaseModel):
    """Admin 'Add order' form. Give an existing customer_id OR a new_customer."""
    customer_id: Optional[int] = None
    new_customer: Optional[NewCustomer] = None
    item: Text(150)
    amount: float = Field(gt=0, le=100000)
    status: Literal["processing", "shipped", "delivered", "cancelled"] = "processing"
    eta: Optional[str] = Field(default=None, max_length=50)
    shipping_address: Optional[str] = Field(default=None, max_length=255)
    create_payment: bool = True  # also create a Stripe TEST payment for this order

    @model_validator(mode="after")
    def exactly_one_customer(self):
        if (self.customer_id is None) == (self.new_customer is None):
            raise ValueError("Choose an existing customer or enter a new customer, not both and not neither.")
        return self
