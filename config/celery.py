import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("procurerp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic stock scan (active only when a worker + beat run against Redis).
app.conf.beat_schedule = {
    "procurement-stock-scan": {
        "task": "apps.procurement.tasks.scheduled_stock_scan",
        "schedule": 6 * 60 * 60,  # every 6 hours
    },
}
