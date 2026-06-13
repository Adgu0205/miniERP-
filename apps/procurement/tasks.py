"""Optional Celery task wrappers. Run inline (eager) when no broker is set,
so the demo works without Redis/Celery."""
try:
    from celery import shared_task
except Exception:  # celery not installed
    def shared_task(fn=None, **_):
        def wrap(f):
            f.delay = f  # allow .delay() to call inline
            return f
        return wrap(fn) if fn else wrap


@shared_task
def scheduled_stock_scan():
    from . import engine
    return [r.id for r in engine.scan_all()]
