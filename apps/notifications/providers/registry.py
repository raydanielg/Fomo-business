"""Provider registry — resolves configured providers from settings.

Provider names map to classes. Credentials come from env settings and are
never exposed via the API.
"""

import logging

from django.conf import settings

from .console import ConsoleEmailProvider, ConsoleSMSProvider, ConsoleWhatsAppProvider

logger = logging.getLogger("fomo.notifications")

SMS_PROVIDERS = {
    "console": ConsoleSMSProvider,
    # "beem": BeemSMSProvider,       # future
    # "twilio": TwilioSMSProvider,   # future
}

WHATSAPP_PROVIDERS = {
    "console": ConsoleWhatsAppProvider,
    # "whatsapp_cloud": WhatsAppCloudProvider,  # future
}

EMAIL_PROVIDERS = {
    "console": ConsoleEmailProvider,
    # "smtp": SMTPEmailProvider,  # future — Django SMTP backend
}


def _resolve(name, registry, fallback):
    cls = registry.get(name)
    if cls is None:
        logger.warning("Unknown provider '%s' — falling back to console", name)
        cls = fallback
    return cls()


def get_sms_provider():
    return _resolve(settings.SMS_PROVIDER, SMS_PROVIDERS, ConsoleSMSProvider)


def get_whatsapp_provider():
    return _resolve(
        settings.WHATSAPP_PROVIDER, WHATSAPP_PROVIDERS, ConsoleWhatsAppProvider
    )


def get_email_provider():
    return _resolve("console", EMAIL_PROVIDERS, ConsoleEmailProvider)
