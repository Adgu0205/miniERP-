import csv

from django.http import HttpResponse


def csv_response(filename, header, rows):
    """Stream a list of row tuples as a downloadable CSV."""
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(resp)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)
    return resp
