from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    """Base class for all outbound messaging providers."""

    name = "abstract"

    @abstractmethod
    def send(self, to: str, message: str, **kwargs) -> dict:
        """Send a message. Returns provider metadata. Raises on failure."""
        raise NotImplementedError


class SMSProvider(NotificationProvider):
    channel = "sms"


class WhatsAppProvider(NotificationProvider):
    channel = "whatsapp"


class EmailProvider(NotificationProvider):
    channel = "email"

    @abstractmethod
    def send(self, to: str, subject: str, message: str, html: str = None, **kwargs) -> dict:
        raise NotImplementedError
