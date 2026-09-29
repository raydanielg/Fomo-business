"""Messaging provider abstraction.

Adding a provider: subclass the relevant base (SMSProvider, WhatsAppProvider,
EmailProvider), implement `send()`, and register in the PROVIDERS map or via
settings (SMS_PROVIDER / WHATSAPP_PROVIDER names).
"""

from .base import EmailProvider, NotificationProvider, SMSProvider, WhatsAppProvider
from .console import ConsoleEmailProvider, ConsoleSMSProvider, ConsoleWhatsAppProvider
from .registry import get_email_provider, get_sms_provider, get_whatsapp_provider

__all__ = [
    "NotificationProvider",
    "SMSProvider",
    "WhatsAppProvider",
    "EmailProvider",
    "ConsoleSMSProvider",
    "ConsoleEmailProvider",
    "ConsoleWhatsAppProvider",
    "get_sms_provider",
    "get_email_provider",
    "get_whatsapp_provider",
]
