# ProcurERP — Mini ERP: From Demand to Delivery .

An Odoo-inspired, **inventory-driven** Mini ERP for a furniture manufacturer ("Shiv Furniture Works").
Sales, Purchase, Manufacturing, BoM, Inventory & a real-time Stock Ledger, automated procurement (MTS/MTO), audit logs, and an executive dashboard — all connected as one system.

> The entire ERP revolves around one thing: **Inventory Movement**.
> Sales decrease stock · Purchase increases stock · Manufacturing consumes + produces · Procurement replenishes.

## Quick start (offline, zero external services)
```bash .
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Open http://127.0.0.1:8000 — login `admin` / `admin123`.

### Demo users
| User | Password | Role |
|---|---|---|
| admin | admin123 | Admin (everything + Audit Logs) |
| owner | demo1234 | Business Owner |
| sales | demo1234 | Sales |
| purchase | demo1234 | Purchase |
| manufacturing | demo1234 | Manufacturing |
| inventory | demo1234 | Inventory Manager |

## Use Postgres (Supabase) + Redis
Copy `.env.example` → `.env` and set:
```
DATABASE_URL=postgres://USER:PASS@HOST:5432/postgres
REDIS_URL=redis://default:PASS@HOST:6379
```
No `DATABASE_URL` → SQLite. No `REDIS_URL` → in-memory cache + synchronous procurement.

## Feature map
- **Products** — Stockable/Consumable, cost+sale price, MTS/MTO, Procure-on-Demand, On Hand / Reserved / Free-to-Use.
- **Sales** — list + kanban + form, stock-availability check, auto-reserve, auto-procurement on shortage, partial delivery.
- **Purchase** — vendors, partial receiving, auto stock-in.
- **Manufacturing** — BoM (components + operations), Work Centers, Work Orders, reserve→consume→produce.
- **Inventory** — real-time Stock Ledger, every movement traceable.
- **Procurement** — shortage engine auto-creates PO or MO (USP).
- **Audit Logs** — status / stock / price / delivery changes.
- **Dashboard** — KPI cards + Sales trend (line), Inventory distribution (donut), Top products (bar), BoM tree.

## The procurement demo (the "wow")
1. Product *Wooden Table* is MTO (procurement_type = manufacture), stock = 2.
2. Create a Sales Order for 10 → confirm.
3. System reserves available, detects shortage of 8, **auto-creates a draft Manufacturing Order for 8** (or a Purchase Order if the product is buy-type).
4. Everything logged in Audit + reflected in the Stock Ledger and dashboard KPIs.

## Tech
Django 5 (MVT) · PostgreSQL/SQLite · Redis (optional) · HTMX + Alpine.js + Tailwind (CDN) · Chart.js · Celery (optional).
