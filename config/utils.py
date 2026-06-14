import csv

from django.http import HttpResponse


def pipeline(current, stages):
    """Build an Odoo-style status-bar from ordered (code,label) stages.
    Returns (steps, cancelled) where each step has done/current flags."""
    codes = [c for c, _ in stages]
    rank = codes.index(current) if current in codes else -1
    steps = [{"label": label, "done": i < rank, "current": i == rank}
             for i, (code, label) in enumerate(stages)]
    return steps, current == "cancelled"


def csv_response(filename, header, rows):
    """Stream a list of row tuples as a downloadable CSV."""
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(resp)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)
    return resp
