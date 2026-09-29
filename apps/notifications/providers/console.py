"""Console/log providers — default for development. Credentials never needed."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from .base import EmailProvider, SMSProvider, WhatsAppProvider

logger = logging.getLogger("fomo.notifications")


class ConsoleSMSProvider(SMSProvider):
    name = "console"

    def send(self, to: str, message: str, **kwargs) -> dict:
        logger.info("[SMS → %s] %s", to, message)
        return {"provider": self.name, "to": to, "delivered": True}


class ConsoleWhatsAppProvider(WhatsAppProvider):
    name = "console"

    def send(self, to: str, message: str, **kwargs) -> dict:
        logger.info("[WhatsApp → %s] %s", to, message)
        return {"provider": self.name, "to": to, "delivered": True}


class ConsoleEmailProvider(EmailProvider):
    name = "console"

    def send(self, to: str, subject: str, message: str, html: str = None,
             attachment=None, **kwargs) -> dict:
        email = EmailMessage(
            subject=subject,
            body=html or message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        if html:
            email.content_subtype = "html"
        if attachment:
            filename, payload, content_type = attachment
            email.attach(filename, payload, content_type)
        email.send(fail_silently=False)
        return {"provider": self.name, "to": to, "delivered": True}
