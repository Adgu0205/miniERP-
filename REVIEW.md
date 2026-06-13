# ProcurERP — Hackathon Review Playbook

> Mini ERP for a furniture manufacturer ("Shiv Furniture Works"). Inventory-driven, automated procurement, real-time dashboards. Django MVT + Postgres (Supabase) + Redis (Upstash).

This doc preps a **4-person team** to defend the project. Each person owns one area, but everyone must know the **one core idea** (below) and the **golden demo**.

---

## 0. The 30-second elevator pitch (anyone can say this)
> "Spreadsheets break manufacturing businesses: stock goes wrong, orders get missed, nobody knows what to make or buy. ProcurERP is a Mini ERP where **everything is one thing — inventory movement.** A sale reserves stock; if there isn't enough, the system **automatically raises a purchase or manufacturing order**, forecasts future demand, and shows the whole business on a live dashboard. It's not a CRUD app — it's a digital backbone that runs the shop floor."

---

## 1. Why / Whom / What

**WHY (the problem).** Small/mid manufacturers run on spreadsheets. Three pains:
1. **No single source of truth for stock** → overselling, stockouts, dead inventory.
2. **Manual procurement** → someone has to *notice* a shortage and *remember* to buy/build. They don't.
3. **No visibility** → owners can't see sales, production, or what's delayed.

**WHOM (the users).** "Shiv Furniture Works" — an SMB that buys raw material (wood, screws), manufactures furniture (tables, chairs), and sells to customers. Five roles: **Sales, Purchase, Manufacturing, Inventory Manager, Owner/Admin** — each sees only their module.

**WHAT (the solution).** An Odoo-inspired modular ERP that ties Sales → Inventory → Manufacturing → Purchase → Procurement into one inventory-driven system with automation and an executive dashboard.

---

## 2. The ONE core idea (everyone memorizes this)
**Everything is an inventory movement. No code ever touches stock directly — it all goes through one service layer (`apps/inventory/services.py`).**

| Module | Action | Stock effect |
|---|---|---|
| Purchase | receive | **+** on_hand |
| Sales | deliver | **−** on_hand |
| Manufacturing | consume components | **−** on_hand |
| Manufacturing | produce finished good | **+** on_hand |
| Procurement | auto PO/MO | replenish |

- `record_move(product, signed_qty, type, ref, user)` → writes a **StockLedger** row, updates `on_hand`, returns balance.
- `reserve()` / `unreserve()` → commit stock to orders.
- `free_to_use = on_hand − reserved`.
- The **StockLedger is the source of truth** → full audit trail, every unit traceable.

Why this matters: it's what makes us "an ERP, not a CRUD app." Say it in the review.

---

## 3. Tech stack (one line + why each)
- **Django 5 (MVT)** — batteries-included, fast to build, ORM + admin + auth for free.
- **PostgreSQL via Supabase** — production DB; **falls back to SQLite** so the demo runs offline.
- **Upstash Redis** — caches dashboard analytics (60s TTL) and is the Celery broker.
- **HTMX + Alpine.js + Tailwind (CDN)** — interactivity without a heavy SPA build.
- **Chart.js** — KPIs, line/donut/bar/polar + **Sankey** flow diagram.
- **Celery (optional)** — scheduled stock scans; **runs synchronously via signals** so the demo needs no worker.

Design principle to state: **"Degrade gracefully."** No Supabase → SQLite. No Redis → in-memory cache. No Celery → signals. It always runs.

---

## 4. Team division — who owns what

| # | Owner | Area | Apps / files | The story they tell |
|---|---|---|---|---|
| **1** | Person A | **Architecture & Inventory Core** | `inventory/`, `products/`, `config/` | The foundation — "everything is stock movement" |
| **2** | Person B | **Sales & the Procurement Engine (USP)** | `sales/`, `procurement/` | Demand in → automation → replenish |
| **3** | Person C | **Manufacturing, BoM & Purchase** | `manufacturing/`, `purchase/` | How shortages get fulfilled |
| **4** | Person D | **Dashboard, RBAC, Audit & Users** | `dashboard/`, `users/`, `audit/` | Visibility & governance — the control tower |

Present in this order — it's a narrative: **Foundation → Demand/Automation → Supply/Production → Visibility.**

---

## 5. Per-owner scripts

### 👤 Person A — Architecture & Inventory Core
**Owns:** `apps/inventory` (StockLedger + services), `apps/products` (the central model), `config` (settings, graceful fallbacks).

**Say this:**
> "I own the spine. In ProcurERP every module — sales, purchase, manufacturing — speaks to inventory through **one service layer**. Nobody mutates stock directly. Every change writes a **ledger row** with the running balance, so we get audit-grade traceability for free. A Product exposes three numbers: **On Hand, Reserved, and Free-to-Use** (= on_hand − reserved). 'Free to use' is what drives every automation decision."

**Key technical points to defend:**
- `record_move()` uses `select_for_update()` inside a DB transaction → **concurrency-safe** balances.
- Products carry procurement config: type (Buy/Manufacture), strategy (MTS/MTO), reorder point, lead time.
- Graceful degradation in `config/settings.py` (Postgres↔SQLite, Redis↔locmem).

**Demo bit:** Open **Stock Ledger** after a sale/build — show every movement with signed qty + balance + who did it.

**Likely questions:**
- *"What if two orders hit the same product at once?"* → row-level lock + atomic transaction; ledger balance is always consistent.
- *"Why store on_hand if you have a ledger?"* → ledger = truth; on_hand = cached aggregate for speed, always updated in the same transaction.

---

### 👤 Person B — Sales & the Procurement Engine (the USP)
**Owns:** `apps/sales` (orders, reserve, deliver) and `apps/procurement` (the smart engine + forecast).

**Say this:**
> "This is our differentiator. When a sales order is **confirmed**, we reserve stock and fire a signal. The **procurement engine** catches it: for each product, if free stock < demand, it **automatically creates the right order** — a Manufacturing Order if we build it, a Purchase Order if we buy it. On top of that, a **demand-forecast** model predicts future need from sales history and suggests reorders *before* we run out. The whole thing is **idempotent** — re-running never creates duplicates."

**Key technical points to defend:**
- **Decoupling via Django signals** (`sales_order_confirmed`) → sales doesn't know about procurement; clean separation.
- `engine.replenish_product()` covers hard shortage (`reserved − on_hand`); `scan_all()` adds **proactive** forecast-based replenishment.
- **Forecast** (`forecast.py`): moving average of last 30 days → avg/day → demand over **lead time** + reorder point − free = suggested qty. *No ML black box — explainable and defensible.*
- **Idempotency:** `open_replenishment_qty()` nets out orders already in flight, so scans don't stack duplicates.
- Every decision logged in **ProcurementLog** (trigger, shortage, action, resulting order).

**Demo bit (the money shot):** Create SO for 20 Wooden Tables (stock = 2) → Confirm → show Free = −18 → open **Procurement**: forecast table + a decision-log row "shortage 18 → MO auto-created."

**Likely questions:**
- *"Why signals instead of Celery here?"* → automation must be instant and work without infra; Celery is wired for *scheduled* scans, signals handle *event-driven* ones.
- *"How does the forecast work?"* → simple moving average over sales; intentionally explainable. Easy to swap for ARIMA/ML later.
- *"What stops infinite duplicate orders?"* → we subtract open POs/MOs before ordering (proved idempotent).

---

### 👤 Person C — Manufacturing, BoM & Purchase
**Owns:** `apps/manufacturing` (BoM, Work Centers, MO, Work Orders) and `apps/purchase` (vendors, POs, receiving).

**Say this:**
> "I own fulfillment — how a shortage actually becomes stock. A **Bill of Materials** defines what goes into a product (4 legs + 1 top + 12 screws) and the operations (assembly, painting, packing). When a Manufacturing Order is **confirmed**, we **reserve all components**; when it's **done**, we **consume** them and **produce** the finished good — all through the same inventory service. On the buy side, Purchase Orders support **partial receiving**, and receiving stocks the warehouse automatically."

**Key technical points to defend:**
- MO lifecycle: Draft → Confirmed (reserve components) → In Progress → Done (consume + produce). Work Orders auto-generated from BoM operations.
- Component requirement scales by qty: `bom_line.qty × (mo.qty / bom.qty)`.
- Purchase: Draft → Confirmed → Partial/Fully Received; `receive_line()` is the only thing that stocks in.
- Vendor **lead_time_days** feeds the forecast engine (Person B's model uses it).

**Demo bit:** Open the auto-created MO → Confirm (watch legs/screws get reserved) → Done (watch finished good on_hand jump + components drop) → check Stock Ledger shows MFG Consume (−) and MFG Produce (+).

**Likely questions:**
- *"What if components aren't available to build?"* → Smart Alerts flags "MO blocked: low components"; reserve still records the commitment so procurement can cover it.
- *"Dynamic BoM cost?"* → BoM sums component costs live; shown on the BoM detail page.

---

### 👤 Person D — Dashboard, RBAC, Audit & User Management
**Owns:** `apps/dashboard` (KPIs + charts), `apps/users` (roles, RBAC, user CRUD), `apps/audit` (trail).

**Say this:**
> "I own visibility and governance — the control tower. The **executive dashboard** has 8 live KPIs and tabbed analytics: sales trend, top products, inventory distribution, order pipelines, the **demand forecast**, and a **Sankey diagram** of material flow across the whole business. Analytics are **cached in Redis** for speed. Access is **role-based** — a sales user literally can't open the purchase module. And **every** status change, stock move, price edit, and delivery is written to an **audit log** for full traceability."

**Key technical points to defend:**
- RBAC: `Profile.role` → `ROLE_MODULES` map → `@module_required("sales")` decorator + `has_module()` helper; sidebar renders per-role.
- Dashboard analytics endpoint returns one cached JSON payload (Redis, 60s); charts render client-side; tabs render on demand for performance.
- Audit log is written **inside the service layer**, so it can't be bypassed.
- In-app **User Management** (admin only): create users, assign roles, reset passwords — matches the wireframe.
- **Smart Alerts** bell: out-of-stock, overdue orders, blocked MOs — role-aware.

**Demo bit:** Show dashboard tabs + Sankey → click **Refresh** (KPIs/charts update) → logout, login as `sales` → show purchase module is blocked (403) and sidebar is trimmed → open Audit Log showing the full chain of the demo.

**Likely questions:**
- *"Is it real-time?"* → near-real-time: Redis-cached, refresh-on-demand (60s). Honest answer; WebSocket push is the next step.
- *"Field-level permissions?"* → currently module-level RBAC; field-level is on the roadmap.

---

## 6. The golden demo flow (8–10 min, drive it in this order)
1. **Login** `admin / admin123` → land on **Dashboard**. (Person D: tour KPIs + Sankey.)
2. **Sales → New** → 20× *Wooden Table* (stock 2) → Save → **Confirm**. (Person B: "watch the magic.")
3. Show **Free-to-Use = −18** on the product / order.
4. **Procurement** → forecast table + decision log: *shortage 18 → MO auto-created*. (Person B.)
5. **Manufacturing** → open the auto MO → **Confirm** (components reserve) → **Done** (consume + produce). (Person C.)
6. **Stock Ledger** → every movement, signed, with balances. (Person A.)
7. **Sales order → Deliver** → stock out, status → Delivered. (Person B.)
8. **Dashboard → Refresh** → KPIs/charts moved. **Audit Log** → full trail. (Person D.)
9. **RBAC**: login `sales / demo1234` → purchase blocked. (Person D.)
10. Close: "spreadsheet → autonomous business OS."

> Backup if live demo risks: each owner has screenshots of their page. Reset clean data with `python manage.py seed_demo && python manage.py seed_dashboard`.

---

## 7. Why we win (differentiators — say these explicitly)
1. **Inventory-driven architecture** — one ledger, one service layer, not scattered CRUD.
2. **Automated procurement engine** — event-driven, *and* predictive (forecast + lead time), *and* idempotent.
3. **Manufacturing + BoM integration** — reserve → consume → produce, fully traceable.
4. **Insight-heavy dashboards** — KPIs, forecast, **Sankey** flow.
5. **Real RBAC + audit** — governance, not just features.
6. **Runs anywhere** — graceful fallback (SQLite/locmem/signals); also live on Supabase + Upstash.

---

## 8. Honest limitations (shows maturity — don't hide them)
- Near-real-time (Redis cache), not WebSocket push — *roadmap*.
- Module-level RBAC, not field-level — *roadmap*.
- BoM components edited via Django admin (UI editor next).
- Forecast is moving-average (intentionally explainable; ML-ready).
- No automated test suite yet.

Framing: *"We prioritized a working end-to-end inventory loop over breadth. These are scoped next steps, not unknowns."*

---

## 9. General Q&A bank
- **"How is this different from a to-do/CRUD app?"** → the inventory-movement core; nothing changes stock outside the ledger service.
- **"Scalability?"** → stateless Django behind gunicorn, Postgres, Redis cache, Celery for async — standard horizontal scale. Dockerfile + Procfile included.
- **"Data integrity?"** → atomic transactions + row locks on every stock op.
- **"Security?"** → Django auth, CSRF, RBAC decorators, secure-cookie/HSTS settings when DEBUG off.
- **"Could a real shop use this?"** → yes for the core loop; it's deploy-ready (Supabase + Upstash today).
- **"What was hardest?"** → keeping stock correct across concurrent sales/builds and making procurement idempotent (no duplicate orders).

---

## 10. Suggested timing (10-min review)
- 0:30 — Pitch + problem (anyone)
- 1:30 — Architecture & inventory core (A)
- 2:30 — Sales → procurement engine + forecast (B) ← spend the most here
- 2:00 — Manufacturing/BoM + purchase (C)
- 2:00 — Dashboard + RBAC + audit (D)
- 1:30 — Q&A

**Everyone knows:** the one core idea, the golden demo, and their own Q&A answers. Good luck. 🚀
