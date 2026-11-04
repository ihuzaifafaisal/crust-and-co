from enum import StrEnum

from pydantic import BaseModel, Field


class Language(StrEnum):
    ENGLISH = "english"
    URDU = "urdu"


class CartItem(BaseModel):
    """A validated menu selection kept in the shared session cart."""

    variant_id: int
    product: str
    variant: str
    quantity: int
    unit_price_rupees: int
    modifiers: list[dict] = Field(default_factory=list)


class RestaurantSessionState(BaseModel):
    """Authoritative state shared by every agent during one call."""

    language: Language | None = None
    active_agent: str = "receptionist"
    handoff_count: int = 0
    last_handoff_reason: str | None = None
    order_completed: bool = False
    session_active: bool = True
    cart: list[CartItem] = Field(default_factory=list)
    customer_id: int | None = None
    customer_phone: str | None = None
    customer_name: str | None = None
    customer_address_id: int | None = None
    fulfillment_type: str | None = None
    order_id: int | None = None
