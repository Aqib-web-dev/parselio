import sys

from .base import BASE_DIR, env
from .base import *

env.read_env(BASE_DIR / ".env")

# Run Celery tasks inline ONLY while pytest is running — so tests need no
# Redis/worker. `runserver` never imports pytest, so it keeps the real queue
# (tasks go to Redis, the worker runs them) exactly as in production.
if "pytest" in sys.modules:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True  # let task exceptions surface as test failures

SECRET_KEY = env("SECRET_KEY", default="dev-only-secret-key")

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
INTERNAL_IPS = ["127.0.0.1"]