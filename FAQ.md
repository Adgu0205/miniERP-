# ProcurERP — Full Project Knowledge & FAQ

Study guide for the whole team. **Part 0** is for everyone. **Parts A–D** are deep dives per owner. Pair this with `REVIEW.md` (the spoken scripts).

Owners: **A** = Architecture & Inventory · **B** = Sales & Procurement · **C** = Manufacturing/BoM & Purchase · **D** = Dashboard, RBAC, Audit, Users.

---

# PART 0 — Universal knowledge (EVERYONE memorizes)

### What is it, in one breath?
An Odoo-inspired **Mini ERP** for a furniture manufacturer. It ties Sales, Purchase, Manufacturing, Inventory and Procurement into **one inventory-driven system** with **automated procurement**, **demand forecasting**, **RBAC**, **audit logs**, and a **live executive dashboard**. Django MVT, Postgres (Supabase), Redis (Upstash).

### The ONE core idea (say it verbatim if asked "what makes this special")
> "Everything is an inventory movement. No code touches stock directly — every change goes through one service layer and writes a ledger row."

- File: `apps/inventory/services.py`
- `free_to_use = on_hand − reserved` drives every automation decision.
- The **StockLedger** is the single source of truth → full traceability.

### The 9 apps (and what each does)
| App | Responsibility |
|---|---|
| `products` | Central product model + stock fields (on_hand, reserved) + procurement config |
| `inventory` | StockLedger + the **only** stock-mutation service layer |
| `sales` | Customers, Sales Orders, reserve, deliver |
| `purchase` | Vendors, Purchase Orders, receiving |
| `manufacturing` | BoM, Work Centers, Manufacturing Orders, Work Orders |
| `procurement` | Shortage engine + demand forecast (the USP) |
| `users` | Roles, RBAC, in-app user management |
| `audit` | Immutable audit trail of all changes |
| `dashboard` | KPIs, charts, Sankey, alerts |

### Stack & WHY each piece
- **Django 5 (MVT)** — fast build, ORM, admin, auth included.
- **PostgreSQL (Supabase)** — managed prod DB; **SQLite fallback** if no `DATABASE_URL` → offline demo.
- **Upstash Redis** — caches dashboard analytics (60s), Celery broker; **locmem fallback** if no `REDIS_URL`.
- **HTMX + Alpine.js + Tailwind (CDN)** — interactivity, no SPA build step.
- **Chart.js** — all charts incl. Sankey flow.
- **Celery (optional)** — scheduled scans; automation **also works via signals** without it.

**Design principle:** *graceful degradation* — no Supabase→SQLite, no Redis→locmem, no Celery→signals. It always runs.

### The 3 order lifecycles
- **Sales:** Draft → Confirmed → Partially Delivered → Fully Delivered (or Cancelled)
- **Purchase:** Draft → Confirmed → Partially Received → Fully Received (or Cancelled)
- **Manufacturing:** Draft → Confirmed → In Progress → Done (or Cancelled)

### Stock impact cheat-sheet
| Module action | Effect |
|---|---|
| Purchase receive | + on_hand |
| Sales deliver | − on_hand |
| Mfg consume components | − on_hand |
| Mfg produce finished good | + on_hand |
| SO confirm / MO confirm | reserve (no on_hand change yet) |

### Run it
```
python -m venv .venv ; .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # users + products + BoMs
python manage.py seed_dashboard     # 30 days of history for charts
python manage.py runserver
```
Live DB = Supabase/Upstash via `.env`. No `.env` = SQLite + locmem.

### Demo logins
`admin / admin123` (all). Role users `sales / purchase / manufacturing / inventory / owner` — all `demo1234`.

### Glossary
- **On Hand** — physical stock. **Reserved** — committed to orders. **Free to Use** — on_hand − reserved.
- **MTS / MTO** — Make To Stock (replenish ahead) / Make To Order (replenish on demand).
- **BoM** — Bill of Materials (recipe: components + operations).
- **Lead time** — days to get/build a product.
- **Reorder point** — minimum free stock to keep.

### Top 5 "gotcha" facts (everyone should know)
1. Stock is **only** changed via `inventory/services.py` (ledger-backed, transaction-safe).
2. Procurement is **idempotent** — re-running never duplicates orders.
3. Forecast is a **moving average** — deliberately explainable, not a black box.
4. Dashboard is **near-real-time** (Redis cache 60s + refresh), not WebSocket push.
5. Chart.js **animations are off on purpose** — the Tailwind Play CDN's DOM observer crashed the animation loop; cards still animate via CSS.

---

# PART A — Architecture & Inventory Core (Owner A)

**Files:** `apps/inventory/{models,services}.py`, `apps/products/{models,forms}.py`, `config/{settings,celery,utils}.py`

### A1. How does a stock change actually happen?
`record_move(product, signed_qty, movement_type, reference, user)`:
1. `select_for_update()` locks the product row (concurrency safe).
2. computes `new_balance = on_hand + qty`.
3. `Product.objects.filter(pk=...).update(on_hand=F('on_hand')+qty)` — atomic DB-level increment.
4. creates a **StockLedger** row with `balance_after`.
5. writes an **AuditLog** entry.
All inside `@transaction.atomic`.

### A2. Why keep `on_hand` if the ledger is the truth?
Ledger = immutable history (sum of moves = current stock). `on_hand` is a **cached aggregate** for fast reads, updated in the *same transaction* as the ledger row → they never drift.

### A3. What are reserve/unreserve?
`reserve(product, qty)` increments `reserved` (commit stock to an order). `unreserve()` decrements (and floors at 0). They don't touch `on_hand` — reservation is a *promise*, delivery is the physical move.

### A4. Why can free_to_use go negative?
Intentional. Confirming an order reserves the full quantity even if stock is short → `free_to_use` goes negative, which **surfaces the shortage** that procurement then covers. It's a feature, not a bug.

### A5. MovementType values?
`purchase` (+), `sale` (−), `mfg_consume` (−), `mfg_produce` (+), `adjust` (±, used for opening stock in seed).

### A6. What's on the Product model?
Identity (name, sku, type), pricing (sale_price, cost_price), procurement config (strategy MTS/MTO, procurement_type buy/manufacture, procure_on_demand, vendor, bom, reorder_point, manufacture_lead_days), stock (on_hand, reserved). Properties: `free_to_use`, `stock_value` (on_hand×cost), `is_low`, `lead_time_days` (vendor's for buy, manufacture_lead_days for make).

### A7. Concurrency safety — defend it.
Every stock op is `@transaction.atomic` + `select_for_update()` row lock + `F()` expression update (no read-modify-write race). Two simultaneous sales can't corrupt the balance.

### A8. Graceful degradation — where?
`config/settings.py`: `DATABASE_URL`→Postgres else SQLite; `REDIS_URL`→RedisCache else LocMemCache; `CELERY_TASK_ALWAYS_EAGER` when no broker. So the app runs with zero external services.

### A9. Likely hard questions
- *"What if record_move fails mid-way?"* → atomic transaction rolls back ledger + on_hand together.
- *"Negative stock allowed?"* → physical on_hand can go to 0 on delivery (we only deliver what's on hand); reserved can exceed on_hand to signal shortage.
- *"How do you audit a stock change?"* → ledger row + AuditLog row, both written in the service.

---

# PART B — Sales & the Procurement Engine (Owner B) ⭐ the USP

**Files:** `apps/sales/{models,services,signals}.py`, `apps/procurement/{engine,forecast,handlers,tasks}.py`

### B1. What happens when a Sales Order is confirmed?
`sales/services.confirm()`:
1. reserves each line's quantity (`inventory.reserve`),
2. sets status = Confirmed,
3. writes audit,
4. **fires the `sales_order_confirmed` signal**.
The procurement app's `handlers.on_sales_order_confirmed` catches it → `engine.run_for_order()`.

### B2. Why signals instead of calling procurement directly?
**Decoupling.** Sales doesn't import procurement. You could delete the procurement app and sales still works. It also models real ERP event-driven design and runs **without Celery/Redis** (synchronous).

### B3. How does the engine decide Buy vs Make?
Per product: `shortage = reserved − on_hand`. If `shortage > 0` and `procure_on_demand`:
- `procurement_type == manufacture` → create a **Manufacturing Order**,
- else → create a **Purchase Order** to the product's vendor.
Logged in **ProcurementLog**.

### B4. How is it idempotent (no duplicate orders)?
Before ordering, `open_replenishment_qty(product)` sums quantities already on **open** MOs (draft/confirmed/in-progress) or **open** PO lines (remaining qty). It orders only the *uncovered* gap (`needed = shortage − already_on_order`); if `needed ≤ 0` it does nothing. Re-running scans creates 0. (Verified.)

### B5. How does the demand forecast work?
`forecast.py`, moving average over last 30 days:
- `avg_daily = qty_sold_30d / 30`
- `predicted_30 = avg_daily × 30`
- `demand_during_lead = avg_daily × lead_time_days`
- `suggested_reorder = (demand_during_lead + reorder_point) − free_to_use` (≥ 0)
- `days_cover = free_to_use / avg_daily`
Deliberately **explainable** — easy to defend, easy to upgrade to ML later.

### B6. Reactive vs proactive procurement?
- **Reactive:** SO confirm → cover hard shortage (event-driven, signals).
- **Proactive:** `scan_all()` (scheduled / "Run Stock Scan" button / `run_procurement_scan` command) → covers hard shortages **and** forecast-based reorders before stockout.

### B7. Sales lifecycle details
Draft→Confirmed→Partial→Delivered/Cancelled. `deliver()` delivers up to physical on_hand per line (partial if short), unreserves + stock-out, updates `delivered_qty`, recomputes status. `cancel()` releases reservations.

### B8. SalesOrderLine.shortage?
`max(0, quantity − product.free_to_use)` — per-line view shown on the order detail "availability" table.

### B9. Likely hard questions
- *"Forecast accuracy?"* → moving average is a baseline; it's transparent and tunable (window, safety stock). ML is a drop-in upgrade.
- *"What if vendor is missing for a buy product?"* → PO is still created (vendor null) as a draft to fill in; alert flags it.
- *"Race between two confirms causing double procurement?"* → engine refreshes product state and nets open orders; worst case it under-orders, never double-orders.
- *"Where's the proof it's idempotent?"* → run the scan twice; second run raises 0.

---

# PART C — Manufacturing, BoM & Purchase (Owner C)

**Files:** `apps/manufacturing/{models,services}.py`, `apps/purchase/{models,services}.py`

### C1. What's a BoM made of?
`BoM` (for a product, output `quantity`) → `BoMLine`s (component + qty) + `BoMOperation`s (name, work_center, duration, sequence). `component_cost` sums line costs live → dynamic costing.

### C2. MO lifecycle and stock effects?
Draft → **Confirmed** (reserve all components) → In Progress → **Done** (unreserve + consume components, produce finished good). All through `inventory.services`. `cancel()` releases reservations.

### C3. How are component requirements scaled?
`component_requirements(mo)`: factor = `mo.quantity / bom.quantity`; each component need = `bom_line.quantity × factor`. So a BoM that yields 1 table needing 4 legs → an MO for 8 tables needs 32 legs.

### C4. Where do Work Orders come from?
`build_work_orders(mo)` generates a WorkOrder per BoM operation on confirm (Assembly, Painting, Packing…), each with work center + duration. They flip to In Progress / Done with the MO.

### C5. Purchase lifecycle and receiving?
Draft → Confirmed → Partial/Fully Received. `receive_line(line, qty)` is the **only** path that stocks in (`inventory.stock_in_purchase`), updates `received_qty`, recomputes status. `receive_all()` receives every remaining line.

### C6. Vendors and lead time?
`Vendor` has `lead_time_days` — feeds Owner B's forecast (`product.lead_time_days` returns vendor lead for buy products). `create_po_for_product()` is what the procurement engine calls to auto-raise a PO.

### C7. What if components aren't available to build the MO?
You can still confirm (reservation records the commitment, can go negative free). Smart Alerts flags "MO blocked: low components"; procurement covers component shortage on the next scan.

### C8. Likely hard questions
- *"Multi-level BoM (sub-assemblies)?"* → current BoM is one level; nested BoMs are a roadmap item (the engine already recurses conceptually via per-product procurement).
- *"Partial receiving math?"* → `remaining = quantity − received_qty`; status = Partial if any received, Received when all done.
- *"Where does finished-good cost come from?"* → product cost_price; BoM gives component cost for analysis.

---

# PART D — Dashboard, RBAC, Audit & Users (Owner D)

**Files:** `apps/dashboard/{views,alerts}.py`, `apps/users/{models,permissions,context,forms,views}.py`, `apps/audit/{models,services}.py`

### D1. What's on the dashboard?
8 KPI tiles (revenue, sales orders, pending deliveries, open MOs, delayed, POs, inventory value, fulfilment %) + 4 tabs of charts: **Overview** (sales trend, inventory donut), **Sales & Customers** (top products, revenue by customer, pipeline), **Manufacturing & Procurement** (MO status, procurement buy/make), **Inventory** (Sankey flow + value donut). Plus Smart Alerts bell.

### D2. How does the data flow to charts?
`dashboard/views.analytics` builds **one JSON payload** of all series, **cached in Redis 60s** (`dash:analytics`, bypass with `?fresh=1`). Charts render client-side (Chart.js); each tab renders only when opened (perf + reliability).

### D3. What does the Sankey show?
Material flow: Purchases → Warehouse → Manufacturing → Finished Goods → Customers, with unit quantities (received qty, components consumed by done MOs via BoM, produced qty, delivered qty).

### D4. How does RBAC work?
`Profile.role` (admin/owner/sales/purchase/manufacturing/inventory) → `ROLE_MODULES` map → each role's allowed module set. `@module_required("sales")` decorator gates views; `has_module(user, module)` powers the sidebar. Admin/superuser = all. A sales user hitting `/purchase/` gets **403**.

### D5. How is the audit trail trustworthy?
`audit.services.log()` is called **inside the service layer** (stock moves, status changes, price edits, deliveries, procurement) — so it can't be bypassed by going through views. AuditLog stores who/when/module/action/object/field/old→new.

### D6. What can User Management do?
`/u/manage/` (admin only): list users with role + accessible modules + status; create user (username, password, role, position, phone); edit role/position/active + reset password. Auto-creates a Profile via signal. Matches the wireframe's admin screen.

### D7. Smart Alerts?
`alerts.build_alerts(user)` — role-aware: out-of-stock products, overdue SOs/MOs, **MOs blocked by component shortage**. Shown as a topbar bell with a live count (context processor → every page).

### D8. Is it real-time?
Near-real-time: Redis-cached analytics with on-demand Refresh (60s TTL). Honest framing: WebSocket/SSE push is the roadmap; cache keeps it fast and cheap.

### D9. Likely hard questions
- *"Field-level permissions (the wireframe grid)?"* → we ship module-level RBAC; field-level is scoped next.
- *"Why cache the dashboard?"* → aggregations are expensive; 60s cache cuts DB load and is plenty fresh for a manager view.
- *"Can roles be changed live?"* → yes, via User Management; takes effect next request.
- *"CSV export?"* → every list (sales/purchase/products/ledger) exports with current filters (`config/utils.csv_response`).

---

# PART E — Cross-cutting tough questions (anyone may get these)

- **"Is this just CRUD with extra steps?"** → No. The inventory-movement core + automated, idempotent, predictive procurement + BoM-driven manufacturing is genuine ERP logic.
- **"How would it scale?"** → stateless Django behind gunicorn (Procfile/Dockerfile included), Postgres, Redis cache, Celery for async. Standard horizontal scale.
- **"Data integrity under load?"** → atomic transactions + row locks + F() updates on every stock op.
- **"Security?"** → Django auth + CSRF + RBAC decorators; secure cookies/HSTS when DEBUG off; secrets in env.
- **"Deployability?"** → live on Supabase + Upstash today; Dockerfile + Procfile for any host.
- **"Biggest engineering challenge?"** → keeping stock correct across concurrent operations and making procurement idempotent (no duplicate POs/MOs).
- **"What would you build next?"** → WebSocket real-time, multi-level BoM, field-level RBAC, in-UI BoM editor, ML forecast, automated tests.
- **"What's the single most impressive thing?"** → confirm one sales order and watch the system reserve stock, detect the shortage, and auto-create the exact manufacturing order to cover it — fully logged and traceable.
