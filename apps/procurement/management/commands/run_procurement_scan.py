"""Run the procurement scan (shortages + forecast). Cron-friendly so it works
without Celery/Redis:  `python manage.py run_procurement_scan`  (e.g. nightly)."""
from django.core.management.base import BaseCommand

from apps.procurement import engine


class Command(BaseCommand):
    help = "Scan catalog and auto-raise PO/MO for shortages and forecast demand."

    def handle(self, *args, **opts):
        results = engine.scan_all()
        for r in results:
            self.stdout.write(f"  {r.product.name}: {r.get_action_display()} "
                              f"{r.result_ref} (qty {r.shortage})")
        self.stdout.write(self.style.SUCCESS(
            f"Procurement scan done — {len(results)} order(s) raised."))
