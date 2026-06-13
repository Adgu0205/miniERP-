# Load Celery app if celery is installed; never block Django if it isn't.
try:
    from .celery import app as celery_app  # noqa: F401
    __all__ = ("celery_app",)
except Exception:  # celery not installed / broker unavailable
    pass
