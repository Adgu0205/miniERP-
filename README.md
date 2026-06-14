<div align="center">

# 🪑 ProcurERP

### Mini ERP — *From Demand to Delivery*

An Odoo-inspired, **inventory-driven** ERP for a furniture manufacturer — *Shiv Furniture Works*.
Sales · Purchase · Manufacturing · BoM · Live Stock Ledger · **Automated Procurement** · Audit Trail · Executive Dashboard — wired together as **one system**.

![Django](https://img.shields.io/badge/Django-5-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Upstash-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-CDN-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)

</div>

---

> ### 🧭 The One Rule
> **Everything is inventory movement.** No model ever touches `Product.on_hand` directly.
> Every stock change flows through a single service layer that writes an immutable ledger row.
>
> `Sales` decrease stock · `Purchase` increases stock · `Manufacturing` consumes + produces · `Procurement` replenishes.

---

## 📑 Table of Contents

- [Why it's different](#-why-its-different)
- [System at a glance](#-system-at-a-glance)
- [The big picture: Demand → Delivery](#-the-big-picture-demand--delivery)
- [Module workflows](#-module-workflows)
  - [Sales](#sales-order-lifecycle) · [Purchase](#purchase-order-lifecycle) · [Manufacturing](#manufacturing-order-lifecycle)
- [⭐ The Procurement Automation (USP)](#-the-procurement-automation-the-usp)
- [Inventory engine](#-inventory-engine-the-single-source-of-truth)
- [Data model (ERD)](#-data-model-erd)
- [Role-based access](#-role-based-access-rbac)
- [Dashboard & analytics](#-dashboard--analytics)
- [Quick start](#-quick-start)
- [Tech stack](#-tech-stack)
- [Project structure](#-project-structure)

---

## ✨ Why it's different

| Most student ERPs | **ProcurERP** |
|---|---|
| CRUD forms that edit numbers | Every number is the **result of a movement**, fully traceable |
| Stock updated in 6 places | Stock updated in **one** service — impossible to corrupt |
| Manual reordering | **Auto-procurement**: an order shortage *creates its own* PO / MO |
| Static charts | **Live KPIs** with period-over-period deltas + drill-down |
| No history | **Immutable audit log** + stock ledger for every change |

---

## 🗺 System at a glance

```mermaid
graph TD
    subgraph Frontend["🖥️ Frontend — Django Templates + HTMX + Alpine + Tailwind"]
        UI[Dashboard · Lists · Kanban · Forms · Detail docs]
    end

    subgraph Core["⚙️ Business Modules"]
        SALES[🛒 Sales]
        PUR[📦 Purchase]
        MFG[🏭 Manufacturing]
        PROC[🤖 Procurement Engine]
        PROD[🪑 Products]
    end

    subgraph Backbone["🔩 The Backbone"]
        INV[(📊 Inventory Service<br/>record_move / reserve)]
        LEDGER[(📒 Stock Ledger)]
        AUDIT[(🧾 Audit Log)]
    end

    UI --> SALES & PUR & MFG & PROD & PROC
    SALES -->|confirm → shortage signal| PROC
    PROC -->|auto-create| PUR
    PROC -->|auto-create| MFG
    SALES & PUR & MFG --> INV
    INV --> LEDGER
    INV --> AUDIT
    INV --> PROD

    classDef svc fill:#0f766e,stroke:#0b5,color:#fff
    classDef mod fill:#2b5fa6,stroke:#1b3,color:#fff
    class INV,LEDGER,AUDIT svc
    class SALES,PUR,MFG,PROC,PROD mod
```

---

## 🔁 The big picture: Demand → Delivery

```mermaid
flowchart LR
    A([📥 Customer Demand]) --> B[🛒 Sales Order]
    B -->|confirm| C{Enough free stock?}
    C -->|✅ Yes| D[Reserve stock]
    C -->|❌ No| E[🤖 Procurement Engine]
    E -->|buy item| F[📦 Purchase Order]
    E -->|made item| G[🏭 Manufacturing Order]
    F -->|receive| H[(➕ Stock In)]
    G -->|consume + produce| I[(♻️ Stock Move)]
    H --> D
    I --> D
    D --> J[🚚 Deliver]
    J --> K[(➖ Stock Out)]
    K --> L([📤 Delivered])

    style A fill:#2b5fa6,color:#fff
    style L fill:#0f766e,color:#fff
    style E fill:#f59e0b,color:#fff
```

### Stock impact map

| Module | Action | Effect on `on_hand` |
|---|---|:---:|
| 📦 Purchase | Receive goods | **➕ increase** |
| 🛒 Sales | Deliver order | **➖ decrease** |
| 🏭 Manufacturing | Consume components | **➖ decrease** |
| 🏭 Manufacturing | Produce finished good | **➕ increase** |
| 🤖 Procurement | Auto PO / MO | **♻️ replenish** |

---

## 🧩 Module workflows

### Sales order lifecycle

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Confirmed: confirm ✅<br/>(reserve + check shortage)
    Confirmed --> PartiallyDelivered: deliver some 🚚
    Confirmed --> FullyDelivered: deliver all 🚚
    PartiallyDelivered --> FullyDelivered: deliver rest
    Draft --> Cancelled: cancel
    Confirmed --> Cancelled: cancel (unreserve)
    FullyDelivered --> [*]
    Cancelled --> [*]
```

- **Confirm** → reserves available stock and, on shortage, **fires the procurement engine**.
- **Deliver** → moves stock *out* through the inventory service (supports partial deliveries).

### Purchase order lifecycle

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Confirmed: confirm
    Confirmed --> PartiallyReceived: receive some 📦
    Confirmed --> FullyReceived: receive all 📦
    PartiallyReceived --> FullyReceived: receive rest
    Draft --> Cancelled
    FullyReceived --> [*]
```

- **Receive** → moves stock *in*, updating `on_hand` and the ledger automatically.

### Manufacturing order lifecycle

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Confirmed: confirm<br/>(reserve components + gen work orders)
    Confirmed --> InProgress: start work orders 🔧
    InProgress --> Done: complete ✅<br/>(consume components − / produce finished +)
    Draft --> Cancelled
    Done --> [*]
```

- **Confirm** → reserves the BoM components and generates **Work Orders** per operation.
- **Done** → consumes components (`−`) and produces the finished good (`+`) in one transaction.

---

## ⭐ The Procurement Automation (the USP)

The headline feature. When a Sales Order is confirmed and free stock can't cover it, the system **decides and acts on its own** — manufacture it or buy it — with zero manual steps. Decoupled via a Django signal, so Sales doesn't even import Procurement.

```mermaid
sequenceDiagram
    actor U as 👤 Sales User
    participant SO as 🛒 Sales Service
    participant SIG as 📡 sales_order_confirmed (signal)
    participant ENG as 🤖 Procurement Engine
    participant INV as 📊 Inventory
    participant DB as 🗄️ PO / MO

    U->>SO: Confirm SO (10 × Wooden Table)
    SO->>INV: reserve available (2)
    SO->>SIG: emit signal
    SIG-->>ENG: run_for_order(SO)
    loop each line
        ENG->>INV: free_to_use vs required
        Note over ENG: shortage = 8 units
        ENG->>ENG: open_replenishment_qty()<br/>(idempotent — nets in-flight orders)
        alt product = manufacture
            ENG->>DB: 🏭 auto-create MO for 8
        else product = buy
            ENG->>DB: 📦 auto-create draft PO for 8 → vendor
        end
    end
    ENG-->>U: Shortage covered automatically ✅
```

**The four layers of automation:**

1. **🤖 Auto-procurement** — `apps/procurement/engine.py`. Shortage → auto PO (buy) or MO (manufacture). Idempotent via `open_replenishment_qty()` — never double-orders.
2. **📈 Demand forecasting** — `apps/procurement/forecast.py`. Moving average → avg/day, predicted 30-day demand, **days-of-cover**, lead-time-aware reorder suggestion.
3. **⏰ Scheduled scan** — `engine.scan_all()` via `python manage.py run_procurement_scan` (cron) or Celery beat every 6h — replenishes *before* a stockout.
4. **♻️ Automatic stock movement & audit** — every receive/deliver/produce writes the ledger + audit log with no manual entry.

> **Try it:** Create a Sales Order for **10 Wooden Tables** (stock = 2) and confirm → watch a Manufacturing Order for **8** appear automatically, logged in Audit and reflected in the Stock Ledger + dashboard.

---

## 📊 Inventory engine (the single source of truth)

All of `apps/inventory/services.py` — every mutation is atomic and logged:

```python
record_move(product, qty, type, ref, user)   # signed qty → ledger row, updates on_hand, returns balance
reserve(product, qty)  /  unreserve(product, qty)
free_to_use = on_hand − reserved              # Product property
```

```mermaid
flowchart LR
    X[Any module] -->|"record_move(±qty)"| S[🔒 Inventory Service]
    S -->|transaction.atomic| L[(📒 StockLedger row)]
    S --> O[Update on_hand / reserved]
    S --> A[(🧾 AuditLog)]
    L --> BAL[Running balance]
    style S fill:#0f766e,color:#fff
```

`@transaction.atomic` + `select_for_update()` + `F()` updates → concurrency-safe, no lost updates.

---

## 🗃 Data model (ERD)

```mermaid
erDiagram
    PRODUCT ||--o{ STOCKLEDGER : "moves"
    PRODUCT ||--o| BOM : "built by"
    BOM ||--o{ BOMLINE : components
    BOM ||--o{ BOMOPERATION : operations
    BOMLINE }o--|| PRODUCT : component
    BOMOPERATION }o--|| WORKCENTER : at

    CUSTOMER ||--o{ SALESORDER : places
    SALESORDER ||--o{ SALESORDERLINE : has
    SALESORDERLINE }o--|| PRODUCT : of

    VENDOR ||--o{ PURCHASEORDER : supplies
    PURCHASEORDER ||--o{ PURCHASEORDERLINE : has
    PURCHASEORDERLINE }o--|| PRODUCT : of

    PRODUCT ||--o{ MANUFACTURINGORDER : produces
    MANUFACTURINGORDER ||--o{ WORKORDER : steps
    MANUFACTURINGORDER }o--|| BOM : uses

    PROCUREMENTLOG }o--|| PRODUCT : replenishes
    AUDITLOG }o--|| USER : by
    PROFILE ||--|| USER : role
```

---

## 🔐 Role-based access (RBAC)

Role lives on `users.Profile`; `@module_required("sales")` guards each module.

| Role | Sales | Purchase | Manufacturing | Inventory | Audit | Dashboard |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Admin / Owner** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sales | ✅ | — | — | 👁 | — | ✅ |
| Purchase | — | ✅ | — | 👁 | — | ✅ |
| Manufacturing | — | — | ✅ | 👁 | — | ✅ |
| Inventory | — | — | — | ✅ | — | ✅ |

---

## 📈 Dashboard & analytics

Odoo-/Power-BI-style executive view, all driven live from the DB:

- **Interactive KPI tiles** — revenue, orders, pending deliveries, open MOs, inventory value, fulfilment rate — with **period-over-period deltas** and **click-through drill-downs**.
- **Sales trend** (revenue + order count, 30d) · **Inventory distribution** (by value) · **Top products** · **SO / MO status funnels** · **Buy-vs-Make split** · **Revenue by customer** · **Material-flow** across the business.
- **Smart alerts** — out-of-stock, overdue orders, MOs blocked by component shortage.
- Chart payloads cached in Redis (60s TTL) when configured.

---

## 🚀 Quick start

> Runs **fully offline** — no external services needed. Falls back to SQLite + in-memory cache + synchronous procurement.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # demo products, BoMs, users, opening stock
python manage.py seed_dashboard   # ~30 days of history so charts look alive
python manage.py runserver
```

Open **http://127.0.0.1:8000** → login `admin` / `admin123`.

### Demo logins

| User | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin (everything + Audit) |
| `owner` | `demo1234` | Business Owner |
| `sales` | `demo1234` | Sales |
| `purchase` | `demo1234` | Purchase |
| `manufacturing` | `demo1234` | Manufacturing |
| `inventory` | `demo1234` | Inventory Manager |

### Go live with Postgres + Redis (optional)

Copy `.env.example` → `.env`:

```env
DATABASE_URL=postgres://USER:PASS@HOST:5432/postgres   # e.g. Supabase session pooler
REDIS_URL=redis://default:PASS@HOST:6379               # e.g. Upstash
```

No `DATABASE_URL` → SQLite. No `REDIS_URL` → in-memory cache + synchronous procurement.

---

## 🛠 Tech stack

| Layer | Choice |
|---|---|
| **Backend** | Django 5 (MVT) |
| **Database** | PostgreSQL (Supabase) → **SQLite fallback** |
| **Cache / Queue** | Redis (Upstash) + Celery — *optional*, signals work synchronously without it |
| **Frontend** | Django Templates + HTMX + Alpine.js + Tailwind (CDN) |
| **Charts** | Chart.js |
| **Theme** | White / blue (`#2b5fa6`) / teal (`#0f766e`) — flat, ERP-grade |

---

## 📁 Project structure

```
apps/
├── users/          roles + RBAC (Profile, module_required)
├── products/       central inventory product model
├── inventory/      StockLedger + the ONE service layer
├── sales/          customers, sales orders, reserve/deliver, confirm signal
├── purchase/       vendors, purchase orders, receiving
├── manufacturing/  BoM, WorkCenter, MO, WorkOrder
├── procurement/    shortage engine, forecast, scheduled scan  ⭐
├── audit/          immutable audit trail
└── dashboard/      KPIs + chart JSON + smart alerts
config/             settings, celery, urls
templates/          base.html (sidebar/topbar) + per-app screens
```

---

<div align="center">

**ProcurERP** — built for the *Mini ERP: From Demand to Delivery* hackathon.
One rule, one ledger, zero manual reordering. 🪑

</div>
