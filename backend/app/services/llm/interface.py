from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class MessageContext:
    customer_name: str
    amount: float
    currency: str
    failure_reason: str | None
    payment_link: str | None
    merchant_tone: str = "friendly"  # friendly | formal | urgent


class MessageGenerator(ABC):
    """
    Interface for generating customer-facing recovery messages.

    Implementations can use a Hugging Face model, a template engine,
    or a mock. The rest of PayBack never depends on a concrete implementation.
    """

    @abstractmethod
    def whatsapp_message(self, ctx: MessageContext) -> str:
        ...

    @abstractmethod
    def email_body(self, ctx: MessageContext) -> str:
        ...
