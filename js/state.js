import { loadDatabase, saveDatabase } from './db.js';

class StateManager {
  constructor() {
    this.db = loadDatabase();
    this.listeners = [];
    this.recalculateQuantities();
  }

  // Pub/Sub pattern for reactive rendering
  subscribe(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  }

  notify() {
    saveDatabase(this.db);
    this.listeners.forEach(cb => cb(this.db));
  }

  // Recalculates all product Free To Use values
  recalculateQuantities() {
    this.db.products.forEach(p => {
      p.freeToUse = p.onHand - p.reserved;
      if (p.freeToUse < 0) p.freeToUse = 0;
      
      // Update low stock status based on threshold
      if (p.freeToUse < p.reorderThreshold) {
        p.status = "Low Stock";
      } else {
        p.status = "Active";
      }
    });
  }

  // Get current active role
  getRole() {
    return this.db.currentRole;
  }

  // Change current role
  setRole(role) {
    const roleDetailsMap = {
      admin: { name: "Admin User", role: "admin", letters: "AD" },
      sales_user: { name: "Sales Representative", role: "sales_user", letters: "SR" },
      purchase_user: { name: "Procurement Manager", role: "purchase_user", letters: "PM" },
      manufacturing_user: { name: "Shop Floor Operator", role: "manufacturing_user", letters: "SO" },
      inventory_manager: { name: "Stockroom Controller", role: "inventory_manager", letters: "SC" },
      business_owner: { name: "Shiv (CEO)", role: "business_owner", letters: "SV" }
    };
    
    this.db.currentRole = role;
    this.db.currentUser = roleDetailsMap[role] || roleDetailsMap.admin;
    this.notify();
    
    this.addAuditLog("System", "User Login", `Switched active role to ${this.db.currentUser.name} (${role})`);
  }

  // Fetch lists
  getProducts() { return this.db.products; }
  getBoms() { return this.db.boms; }
  getSalesOrders() { return this.db.salesOrders; }
  getPurchaseOrders() { return this.db.purchaseOrders; }
  getManufacturingOrders() { return this.db.manufacturingOrders; }
  getStockLedger() { return this.db.stockLedger; }
  getAuditLogs() { return this.db.auditLogs; }
  getNotifications() { return this.db.notifications; }

  // Generic adders
  addProduct(product) {
    const newProduct = {
      id: "prod-" + Date.now(),
      onHand: 0,
      reserved: 0,
      freeToUse: 0,
      status: "Active",
      ...product
    };
    this.db.products.push(newProduct);
    this.recalculateQuantities();
    
    this.addAuditLog("Product", "Product Creation", `Created product ${product.name} (SKU: ${product.sku})`);
    this.addNotification("low_stock", `New product cataloged: ${product.name}`);
    this.notify();
    return newProduct;
  }

  addBom(bom) {
    const newBom = {
      id: "bom-" + Date.now(),
      ...bom
    };
    this.db.boms.push(newBom);
    
    // Link product to BoM
    const prod = this.db.products.find(p => p.id === bom.productId);
    if (prod) {
      prod.bomId = newBom.id;
    }
    
    this.addAuditLog("Manufacturing", "BoM Creation", `Created Bill of Materials for ${bom.productName}`);
    this.notify();
    return newBom;
  }

  // Create Sales Order
  addSalesOrder(soData) {
    const newSO = {
      id: "SO-" + String(this.db.salesOrders.length + 1).padStart(3, '0'),
      date: new Date().toISOString(),
      status: "draft",
      deliveredQtyMap: {},
      procurementGroupId: "proc-grp-" + Date.now(),
      ...soData
    };
    
    // Initialize delivery mappings
    newSO.items.forEach(item => {
      newSO.deliveredQtyMap[item.productId] = 0;
    });

    this.db.salesOrders.push(newSO);
    this.addAuditLog("Sales", "Order Creation", `Sales Order ${newSO.id} created for ${newSO.customerName}`);
    this.notify();
    return newSO;
  }

  // Create Purchase Order
  addPurchaseOrder(poData) {
    const newPO = {
      id: "PO-" + String(this.db.purchaseOrders.length + 1).padStart(3, '0'),
      date: new Date().toISOString(),
      status: "draft",
      receivedQtyMap: {},
      ...poData
    };
    
    newPO.items.forEach(item => {
      newPO.receivedQtyMap[item.productId] = 0;
    });

    this.db.purchaseOrders.push(newPO);
    this.addAuditLog("Purchase", "Order Creation", `Purchase Order ${newPO.id} generated for vendor ${newPO.vendorName}`);
    this.addNotification("procurement_created", `RFQ ${newPO.id} generated for ${newPO.vendorName}`);
    this.notify();
    return newPO;
  }

  // Create Manufacturing Order
  addManufacturingOrder(moData) {
    const bom = this.db.boms.find(b => b.id === moData.bomId);
    const workOrders = bom ? bom.operations.map((op, idx) => ({
      id: `WO-${moData.id || Date.now()}-${String.fromCharCode(65 + idx)}`,
      name: op.name,
      status: "pending", // pending, active, completed
      duration: op.duration,
      workCenter: op.workCenter,
      elapsedSeconds: 0
    })) : [];

    const newMO = {
      id: moData.id || "MO-" + String(this.db.manufacturingOrders.length + 1).padStart(3, '0'),
      date: new Date().toISOString(),
      status: "draft",
      assignee: moData.assignee || "Unassigned",
      workOrders,
      ...moData
    };

    this.db.manufacturingOrders.push(newMO);
    this.addAuditLog("Manufacturing", "Order Creation", `Manufacturing Order ${newMO.id} created for ${newMO.productName}`);
    this.addNotification("procurement_created", `Manufacturing Order ${newMO.id} generated for ${newMO.productName}`);
    this.notify();
    return newMO;
  }

  // Core Stock Movement Journalizer
  addStockLedgerEntry(productId, movementType, quantityChange, sourceDocument) {
    const product = this.db.products.find(p => p.id === productId);
    if (!product) return;

    const entry = {
      id: "ledger-" + Date.now() + Math.random().toString(36).substr(2, 5),
      timestamp: new Date().toISOString(),
      productId,
      productName: product.name,
      movementType,
      quantityChange,
      sourceDocument,
      user: this.db.currentUser.name
    };

    this.db.stockLedger.unshift(entry); // Newest first
    this.addAuditLog("Inventory", "Stock Movement", `${movementType}: ${quantityChange > 0 ? '+' : ''}${quantityChange} units of ${product.name} (Source: ${sourceDocument})`);
  }

  // Core Audit Logging
  addAuditLog(module, action, details) {
    const entry = {
      id: "audit-" + Date.now() + Math.random().toString(36).substr(2, 5),
      timestamp: new Date().toISOString(),
      module,
      action,
      details,
      user: this.db.currentUser.name
    };
    this.db.auditLogs.unshift(entry);
  }

  // Notifications manager
  addNotification(type, message) {
    const item = {
      id: "notif-" + Date.now(),
      timestamp: new Date().toISOString(),
      type,
      message,
      read: false
    };
    this.db.notifications.unshift(item);
  }

  markNotificationsAsRead() {
    this.db.notifications.forEach(n => n.read = true);
    this.notify();
  }

  // Cancel Sales Order
  cancelSalesOrder(soId) {
    const so = this.db.salesOrders.find(s => s.id === soId);
    if (!so || so.status === "cancelled" || so.status === "fully_delivered") return;

    // Release reservations if it was confirmed
    if (so.status === "confirmed" || so.status === "partially_delivered") {
      so.items.forEach(item => {
        const product = this.db.products.find(p => p.id === item.productId);
        if (product) {
          const reservedForThisItem = item.quantity - (so.deliveredQtyMap[item.productId] || 0);
          product.reserved = Math.max(0, product.reserved - reservedForThisItem);
        }
      });
    }

    so.status = "cancelled";
    this.recalculateQuantities();
    this.addAuditLog("Sales", "Status Change", `Sales Order ${soId} has been cancelled`);
    this.notify();
  }

  // Confirm Sales Order Business Logic
  confirmSalesOrder(soId, triggerProcurementCallback) {
    const so = this.db.salesOrders.find(s => s.id === soId);
    if (!so || so.status !== "draft") return;

    so.status = "confirmed";
    this.addAuditLog("Sales", "Status Change", `Sales Order ${so.id} confirmed`);

    const shortages = [];

    // Reserve stock and detect shortages
    so.items.forEach(item => {
      const product = this.db.products.find(p => p.id === item.productId);
      if (product) {
        const needed = item.quantity;
        const availableNow = product.freeToUse;

        if (availableNow >= needed) {
          // Full stock available -> reserve full amount
          product.reserved += needed;
        } else {
          // Stock shortage -> reserve whatever is free
          if (availableNow > 0) {
            product.reserved += availableNow;
          }
          
          const shortageQty = needed - availableNow;
          shortages.push({
            productId: product.id,
            productName: product.name,
            sku: product.sku,
            needed: needed,
            available: availableNow,
            shortage: shortageQty,
            procureStrategy: product.procureStrategy,
            procureType: product.procureType,
            bomId: product.bomId,
            vendor: product.vendor
          });
        }
      }
    });

    this.recalculateQuantities();
    this.notify();

    // Trigger procurement callback if shortages are found
    if (shortages.length > 0 && triggerProcurementCallback) {
      triggerProcurementCallback(so, shortages);
    }
  }

  // Deliver Sales Order Line Items
  deliverSalesOrder(soId, deliveryQuantities) {
    const so = this.db.salesOrders.find(s => s.id === soId);
    if (!so || (so.status !== "confirmed" && so.status !== "partially_delivered")) return;

    let allFullyDelivered = true;

    so.items.forEach(item => {
      const product = this.db.products.find(p => p.id === item.productId);
      if (!product) return;

      const qtyToDeliver = parseInt(deliveryQuantities[item.productId]) || 0;
      if (qtyToDeliver <= 0) {
        // If not delivering everything and remaining is > 0, not fully delivered
        const delivered = so.deliveredQtyMap[item.productId] || 0;
        if (delivered < item.quantity) allFullyDelivered = false;
        return;
      }

      // Check reservation logic: we cannot deliver more than is currently On-Hand
      const actualDelivery = Math.min(qtyToDeliver, product.onHand);

      // Decrement inventory balances
      product.onHand -= actualDelivery;
      
      // Decrease reservation pool by the amount we reserved for this delivery
      const alreadyDelivered = so.deliveredQtyMap[item.productId] || 0;
      const totalRemaining = item.quantity - alreadyDelivered;
      const reservationDeduction = Math.min(actualDelivery, totalRemaining);
      product.reserved = Math.max(0, product.reserved - reservationDeduction);

      so.deliveredQtyMap[item.productId] = alreadyDelivered + actualDelivery;

      // Journal stock moves
      this.addStockLedgerEntry(product.id, "Sales Delivery", -actualDelivery, so.id);

      if (so.deliveredQtyMap[item.productId] < item.quantity) {
        allFullyDelivered = false;
      }
    });

    so.status = allFullyDelivered ? "fully_delivered" : "partially_delivered";
    this.recalculateQuantities();
    
    this.addAuditLog("Sales", "Order Delivery", `Sales Order ${so.id} delivery processed. Status is now ${so.status}`);
    this.addNotification("sales_delivered", `SO ${so.id} has been processed: ${so.status.replace('_', ' ')}`);
    this.notify();
  }

  // Receive Purchase Order items
  receivePurchaseOrder(poId, receiveQuantities) {
    const po = this.db.purchaseOrders.find(p => p.id === poId);
    if (!po || (po.status !== "confirmed" && po.status !== "partially_received")) return;

    let allFullyReceived = true;

    po.items.forEach(item => {
      const product = this.db.products.find(p => p.id === item.productId);
      if (!product) return;

      const qtyToReceive = parseInt(receiveQuantities[item.productId]) || 0;
      if (qtyToReceive <= 0) {
        const received = po.receivedQtyMap[item.productId] || 0;
        if (received < item.quantity) allFullyReceived = false;
        return;
      }

      const alreadyReceived = po.receivedQtyMap[item.productId] || 0;
      product.onHand += qtyToReceive;
      po.receivedQtyMap[item.productId] = alreadyReceived + qtyToReceive;

      // Journal receipt
      this.addStockLedgerEntry(product.id, "Purchase Receipt", qtyToReceive, po.id);

      if (po.receivedQtyMap[item.productId] < item.quantity) {
        allFullyReceived = false;
      }
    });

    po.status = allFullyReceived ? "fully_received" : "partially_received";
    this.recalculateQuantities();
    
    this.addAuditLog("Purchase", "Receipt Validation", `PO ${po.id} receipt processed. Status is now ${po.status}`);
    this.addNotification("purchase_received", `PO ${po.id} items received: status is now ${po.status.replace('_', ' ')}`);
    this.notify();
  }

  // Confirm MO (Reservations check)
  confirmManufacturingOrder(moId) {
    const mo = this.db.manufacturingOrders.find(m => m.id === moId);
    if (!mo || mo.status !== "draft") return;

    mo.status = "confirmed";
    this.addAuditLog("Manufacturing", "Status Change", `MO ${mo.id} confirmed`);

    // Fetch Bill of Materials component recipes
    const bom = this.db.boms.find(b => b.id === mo.bomId);
    if (bom) {
      bom.components.forEach(comp => {
        const product = this.db.products.find(p => p.id === comp.productId);
        if (product) {
          const needed = comp.quantity * mo.quantity;
          // Reserve components needed
          product.reserved += needed;
        }
      });
    }

    this.recalculateQuantities();
    this.notify();
  }

  // Update MO Work Order Status
  updateWorkOrderStatus(moId, workOrderId, nextStatus) {
    const mo = this.db.manufacturingOrders.find(m => m.id === moId);
    if (!mo) return;

    const wo = mo.workOrders.find(w => w.id === workOrderId);
    if (!wo) return;

    wo.status = nextStatus; // pending, active, completed
    
    // Manage MO Overall State: if work orders are executing, MO is in_progress
    if (mo.status === "confirmed") {
      mo.status = "in_progress";
    }

    // Check if all WOs are completed
    const allCompleted = mo.workOrders.every(w => w.status === "completed");
    if (allCompleted) {
      mo.status = "quality_check"; // Move to QC
      this.addNotification("manufacturing_completion", `MO ${mo.id} completed assembly. Pending quality check.`);
    }

    this.notify();
  }

  // Finalize MO completion (Stock updates)
  completeManufacturingOrder(moId) {
    const mo = this.db.manufacturingOrders.find(m => m.id === moId);
    if (!mo || (mo.status !== "quality_check" && mo.status !== "in_progress" && mo.status !== "confirmed")) return;

    const bom = this.db.boms.find(b => b.id === mo.bomId);
    if (bom) {
      // 1. Consume raw materials
      bom.components.forEach(comp => {
        const product = this.db.products.find(p => p.id === comp.productId);
        if (product) {
          const consumedQty = comp.quantity * mo.quantity;
          product.onHand -= consumedQty;
          // release reserved component stock
          product.reserved = Math.max(0, product.reserved - consumedQty);
          
          this.addStockLedgerEntry(product.id, "Manufacturing Consumption", -consumedQty, mo.id);
        }
      });
    }

    // 2. Add finished goods
    const finishedProduct = this.db.products.find(p => p.id === mo.productId);
    if (finishedProduct) {
      finishedProduct.onHand += mo.quantity;
      this.addStockLedgerEntry(finishedProduct.id, "Manufacturing Production", mo.quantity, mo.id);
    }

    mo.status = "completed";
    
    // Complete all work orders if they weren't already
    mo.workOrders.forEach(w => w.status = "completed");

    this.recalculateQuantities();
    
    this.addAuditLog("Manufacturing", "Status Change", `MO ${mo.id} status changed to completed. Produced ${mo.quantity}x ${mo.productName}`);
    this.addNotification("manufacturing_completion", `MO ${mo.id} fully manufactured and verified. Added ${mo.quantity}x ${mo.productName} to finished stock.`);
    this.notify();
  }

  // Adjust stock manually (Inventory audits)
  adjustStockManually(productId, newQty, reason) {
    const product = this.db.products.find(p => p.id === productId);
    if (!product) return;

    const oldOnHand = product.onHand;
    const diff = newQty - oldOnHand;
    product.onHand = newQty;

    this.recalculateQuantities();
    this.addStockLedgerEntry(product.id, "Manual Adjustment", diff, "Manual Adjustment");
    this.addAuditLog("Inventory", "Price Changes", `Manual stock adjustment for ${product.name}: ${oldOnHand} -> ${newQty} (Reason: ${reason})`);
    this.notify();
  }
}

export const state = new StateManager();
window.stateEngine = state; // expose for console access
