# CLAUDE.md — Shiv ERP

Mini ERP (Odoo-inspired) for "Shiv Furniture Works". Inventory-driven. Django MVT.

## Run
```
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo       # demo data + users
python manage.py runserver
```
Login: `admin` / `admin123`. Role logins: `sales`, `purchase`, `manufacturing`, `inventory`, `owner` — all pwd `demo1234`.

## Stack
- Django 5 (MVT). DB: PostgreSQL via `DATABASE_URL` (Supabase); **falls back to SQLite** if unset → runs offline for demo.
- Frontend: Django templates + HTMX + Alpine.js + Tailwind (all CDN). Charts: Chart.js (CDN).
- Realtime/Cache/Celery: Redis optional. Procurement automation runs **synchronously via Django signals** so the demo works without Redis/Celery. Celery wiring present but optional.

## Architecture — the ONE rule
Everything is **inventory movement**. No model touches `Product.on_hand` directly.
All stock changes go through `apps/inventory/services.py`:
- `record_move(product, qty, type, ref, user)` — signed qty, writes a `StockLedger` row, updates `on_hand`, returns balance.
- `reserve(product, qty)` / `unreserve(product, qty)` — adjust `reserved`.
- `free_to_use = on_hand - reserved` (Product property).

Stock impact map:
| Module | Action | Effect |
|---|---|---|
| Purchase | receive | +on_hand |
| Sales | deliver | −on_hand |
| Manufacturing | consume components | −on_hand |
| Manufacturing | produce finished | +on_hand |
| Procurement | auto PO/MO | replenish |

## Apps (`apps/`)
`users` (roles+RBAC) · `products` (central inventory model) · `inventory` (StockLedger + services) · `sales` · `purchase` · `manufacturing` (BoM, WorkCenter, MO, WorkOrder) · `procurement` (shortage engine) · `audit` (AuditLog) · `dashboard` (KPIs + chart JSON).

## Workflows
- Sales: Draft → Confirmed → Partially Delivered → Fully Delivered (or Cancelled). Confirm = reserve + trigger procurement on shortage. Deliver = stock out.
- Purchase: Draft → Confirmed → Partially Received → Fully Received. Receive = stock in.
- Manufacturing: Draft → Confirmed → In Progress → Done. Confirm = reserve components. Done = consume components + produce finished good.

## Procurement automation (USP)
On SO confirm, for each line: `if free_to_use < required` → shortage.
Product.procurement_type == `manufacture` → auto-create MO for shortage; == `buy` → auto-create PO (draft) to product.vendor. Lives in `apps/procurement/engine.py`, fired by `apps/sales` signal.

## RBAC
Role on `users.Profile`. `apps/users/permissions.py` → `module_required("sales")` decorator + `has_module(user, module)`. Admin/owner = all. Module users = their module only.

## Conventions
- One service layer per side-effect; views stay thin.
- AuditLog written in services for status/stock/price/delivery changes.
- Money = `DecimalField`. Qty = `DecimalField` (supports fractional units).
- Keep templates in `templates/<app>/`. Base layout `templates/base.html` (sidebar + topbar + breadcrumb).
