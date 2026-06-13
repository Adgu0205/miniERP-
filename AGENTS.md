# AGENTS.md

Agent guide for the Shiv Mini ERP codebase. Read `CLAUDE.md` first for the full picture.

## Golden rules
1. **Never mutate `Product.on_hand` or `Product.reserved` directly.** Use `apps.inventory.services`. This keeps the StockLedger truthful — the ledger IS the source of truth for traceability.
2. **Every state change is auditable.** Status changes, stock moves, price/qty edits, deliveries → write an `AuditLog` (helper: `apps.audit.services.log`).
3. **Business logic lives in `services.py` / `engine.py`, not views or models.** Views orchestrate, services mutate.
4. Money & quantities are `DecimalField`. Never float.

## Where things live
- Stock math → `apps/inventory/services.py`
- Procurement decisions → `apps/procurement/engine.py`
- Order lifecycle (confirm/deliver/receive/produce) → the owning app's `services.py`
- RBAC → `apps/users/permissions.py`
- Dashboard aggregates / chart JSON → `apps/dashboard/views.py`

## Adding a feature
- New stock-affecting action? Route it through `record_move`. Pick/extend a `MovementType`.
- New module page? Add view → url → template under `templates/<app>/`, gate with `@module_required("<app>")`, add a sidebar link in `base.html`.
- New order status? Update the model's `STATUS` choices, the transition method in `services.py`, and the kanban columns.

## Test the happy path before claiming done
```
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Then: create SO for a low-stock MTO product → confirm → verify a draft MO/PO was auto-created and stock got reserved. Check `/audit/` and the StockLedger.

## Don't
- Don't add Celery/Redis as hard deps — automation must run without them (signals path).
- Don't hardcode stock numbers in templates; read from Product properties / ledger.
- Don't bypass `module_required` on module views.
