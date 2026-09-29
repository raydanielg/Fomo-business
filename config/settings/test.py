from .base import *  # noqa: F401,F403

DEBUG = False

# Faster, isolated tests — use sqlite or dedicated test db via TEST settings
DATABASES["default"] = env.db(
    "TEST_DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "test_db.sqlite3")
)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Keep throttling enabled but with effectively unlimited rates
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "100000/minute",
    "user": "100000/minute",
    "auth": "100000/minute",
}
