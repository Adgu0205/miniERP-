// Mock DB Seed Data and Storage helpers for local persistence

const DEFAULT_PRODUCTS = [
  {
    id: "prod-wt",
    name: "Wooden Table",
    sku: "W-TBL-01",
    category: "Furniture",
    costPrice: 80.00,
    salesPrice: 150.00,
    onHand: 8,
    reserved: 0,
    freeToUse: 8,
    procureStrategy: "MTO", // Make To Order
    procureType: "Manufacturing",
    vendor: "Timber Supplier Co",
    bomId: "bom-wt",
    reorderThreshold: 2,
    status: "Active"
  },
  {
    id: "prod-dt",
    name: "Dining Table",
    sku: "D-TBL-02",
    category: "Furniture",
    costPrice: 180.00,
    salesPrice: 350.00,
    onHand: 3,
    reserved: 0,
    freeToUse: 3,
    procureStrategy: "MTO", // Make To Order
    procureType: "Manufacturing",
    vendor: "Timber Supplier Co",
    bomId: "bom-dt",
    reorderThreshold: 1,
    status: "Active"
  },
  {
    id: "prod-oc",
    name: "Office Chair",
    sku: "O-CHR-03",
    category: "Furniture",
    costPrice: 50.00,
    salesPrice: 120.00,
    onHand: 15,
    reserved: 0,
    freeToUse: 15,
    procureStrategy: "MTS", // Make To Stock
    procureType: "Purchase",
    vendor: "Office World",
    bomId: "",
    reorderThreshold: 5,
    status: "Active"
  },
  {
    id: "prod-leg",
    name: "Wooden Legs",
    sku: "COMP-LEG",
    category: "Components",
    costPrice: 10.00,
    salesPrice: 0.00,
    onHand: 40,
    reserved: 0,
    freeToUse: 40,
    procureStrategy: "MTS",
    procureType: "Purchase",
    vendor: "Timber Supplier Co",
    bomId: "",
    reorderThreshold: 15,
    status: "Active"
  },
  {
    id: "prod-top",
    name: "Wooden Top",
    sku: "COMP-TOP",
    category: "Components",
    costPrice: 25.00,
    salesPrice: 0.00,
    onHand: 12,
    reserved: 0,
    freeToUse: 12,
    procureStrategy: "MTS",
    procureType: "Purchase",
    vendor: "Timber Supplier Co",
    bomId: "",
    reorderThreshold: 5,
    status: "Active"
  },
  {
    id: "prod-scr",
    name: "Screws",
    sku: "COMP-SCR",
    category: "Components",
    costPrice: 0.10,
    salesPrice: 0.00,
    onHand: 280,
    reserved: 0,
    freeToUse: 280,
    procureStrategy: "MTS",
    procureType: "Purchase",
    vendor: "Hardware Goods LLC",
    bomId: "",
    reorderThreshold: 100,
    status: "Active"
  },
  {
    id: "prod-pnt",
    name: "Paint Can",
    sku: "COMP-PNT",
    category: "Components",
    costPrice: 8.00,
    salesPrice: 0.00,
    onHand: 15,
    reserved: 0,
    freeToUse: 15,
    procureStrategy: "MTS",
    procureType: "Purchase",
    vendor: "Sherwin Paints",
    bomId: "",
    reorderThreshold: 4,
    status: "Active"
  }
];

const DEFAULT_BOMS = [
  {
    id: "bom-wt",
    name: "Bill of Materials - Wooden Table",
    productId: "prod-wt",
    productName: "Wooden Table",
    components: [
      { productId: "prod-leg", name: "Wooden Legs", quantity: 4 },
      { productId: "prod-top", name: "Wooden Top", quantity: 1 },
      { productId: "prod-scr", name: "Screws", quantity: 12 }
    ],
    operations: [
      { name: "Assembly", duration: 60, workCenter: "Assembly Line" },
      { name: "Painting", duration: 30, workCenter: "Painting Station" },
      { name: "Packing", duration: 20, workCenter: "Packaging Unit" }
    ]
  },
  {
    id: "bom-dt",
    name: "Bill of Materials - Dining Table",
    productId: "prod-dt",
    productName: "Dining Table",
    components: [
      { productId: "prod-leg", name: "Wooden Legs", quantity: 4 },
      { productId: "prod-top", name: "Wooden Top", quantity: 1 },
      { productId: "prod-scr", name: "Screws", quantity: 16 }
    ],
    operations: [
      { name: "Assembly", duration: 80, workCenter: "Assembly Line" },
      { name: "Painting", duration: 40, workCenter: "Painting Station" },
      { name: "Packing", duration: 30, workCenter: "Packaging Unit" }
    ]
  }
];

const DEFAULT_SALES_ORDERS = [
  {
    id: "SO-001",
    customerName: "John Doe Furniture Store",
    date: "2026-06-11T14:32:00.000Z",
    items: [
      { productId: "prod-wt", name: "Wooden Table", quantity: 3, unitPrice: 150.00 }
    ],
    totalAmount: 450.00,
    status: "draft", // draft, confirmed, partially_delivered, fully_delivered, cancelled
    deliveredQtyMap: { "prod-wt": 0 },
    procurementGroupId: ""
  },
  {
    id: "SO-002",
    customerName: "Acme Corp Office Replenishment",
    date: "2026-06-12T09:15:00.000Z",
    items: [
      { productId: "prod-oc", name: "Office Chair", quantity: 10, unitPrice: 120.00 }
    ],
    totalAmount: 1200.00,
    status: "confirmed",
    deliveredQtyMap: { "prod-oc": 0 },
    procurementGroupId: ""
  },
  {
    id: "SO-003",
    customerName: "Luxury Home Designs",
    date: "2026-06-10T10:00:00.000Z",
    items: [
      { productId: "prod-dt", name: "Dining Table", quantity: 1, unitPrice: 350.00 }
    ],
    totalAmount: 350.00,
    status: "fully_delivered",
    deliveredQtyMap: { "prod-dt": 1 },
    procurementGroupId: ""
  }
];

const DEFAULT_PURCHASE_ORDERS = [
  {
    id: "PO-001",
    vendorName: "Timber Supplier Co",
    date: "2026-06-11T16:00:00.000Z",
    items: [
      { productId: "prod-top", name: "Wooden Top", quantity: 20, unitPrice: 25.00 }
    ],
    totalAmount: 500.00,
    status: "draft", // draft, confirmed, partially_received, fully_received, cancelled
    receivedQtyMap: { "prod-top": 0 }
  },
  {
    id: "PO-002",
    vendorName: "Hardware Goods LLC",
    date: "2026-06-12T11:45:00.000Z",
    items: [
      { productId: "prod-scr", name: "Screws", quantity: 200, unitPrice: 0.10 }
    ],
    totalAmount: 20.00,
    status: "fully_received",
    receivedQtyMap: { "prod-scr": 200 }
  }
];

const DEFAULT_MANUFACTURING_ORDERS = [
  {
    id: "MO-001",
    productId: "prod-wt",
    productName: "Wooden Table",
    quantity: 4,
    bomId: "bom-wt",
    status: "completed", // draft, confirmed, in_progress, quality_check, completed
    assignee: "John Operative",
    date: "2026-06-10T08:30:00.000Z",
    workOrders: [
      { id: "WO-001-A", name: "Assembly", status: "completed", duration: 60, workCenter: "Assembly Line", elapsedSeconds: 3600 },
      { id: "WO-001-P", name: "Painting", status: "completed", duration: 30, workCenter: "Painting Station", elapsedSeconds: 1800 },
      { id: "WO-001-K", name: "Packing", status: "completed", duration: 20, workCenter: "Packaging Unit", elapsedSeconds: 1200 }
    ]
  },
  {
    id: "MO-002",
    productId: "prod-dt",
    productName: "Dining Table",
    quantity: 2,
    bomId: "bom-dt",
    status: "confirmed",
    assignee: "Mark Builder",
    date: "2026-06-13T09:00:00.000Z",
    workOrders: [
      { id: "WO-002-A", name: "Assembly", status: "pending", duration: 80, workCenter: "Assembly Line", elapsedSeconds: 0 },
      { id: "WO-002-P", name: "Painting", status: "pending", duration: 40, workCenter: "Painting Station", elapsedSeconds: 0 },
      { id: "WO-002-K", name: "Packing", status: "pending", duration: 30, workCenter: "Packaging Unit", elapsedSeconds: 0 }
    ]
  }
];

const DEFAULT_STOCK_LEDGER = [
  {
    id: "ledger-1",
    timestamp: "2026-06-10T09:00:00.000Z",
    productId: "prod-wt",
    productName: "Wooden Table",
    movementType: "Manufacturing Production", // Sales Delivery, Purchase Receipt, Manufacturing Consumption, Manufacturing Production, Manual Adjustment
    quantityChange: 4,
    sourceDocument: "MO-001",
    user: "John Operative"
  },
  {
    id: "ledger-2",
    timestamp: "2026-06-10T09:00:00.000Z",
    productId: "prod-leg",
    productName: "Wooden Legs",
    movementType: "Manufacturing Consumption",
    quantityChange: -16,
    sourceDocument: "MO-001",
    user: "John Operative"
  },
  {
    id: "ledger-3",
    timestamp: "2026-06-10T09:00:00.000Z",
    productId: "prod-top",
    productName: "Wooden Top",
    movementType: "Manufacturing Consumption",
    quantityChange: -4,
    sourceDocument: "MO-001",
    user: "John Operative"
  },
  {
    id: "ledger-4",
    timestamp: "2026-06-10T09:00:00.000Z",
    productId: "prod-scr",
    productName: "Screws",
    movementType: "Manufacturing Consumption",
    quantityChange: -48,
    sourceDocument: "MO-001",
    user: "John Operative"
  },
  {
    id: "ledger-5",
    timestamp: "2026-06-10T11:30:00.000Z",
    productId: "prod-dt",
    productName: "Dining Table",
    movementType: "Sales Delivery",
    quantityChange: -1,
    sourceDocument: "SO-003",
    user: "Sarah Sales"
  },
  {
    id: "ledger-6",
    timestamp: "2026-06-12T12:00:00.000Z",
    productId: "prod-scr",
    productName: "Screws",
    movementType: "Purchase Receipt",
    quantityChange: 200,
    sourceDocument: "PO-002",
    user: "Paul Purchase"
  }
];

const DEFAULT_AUDIT_LOGS = [
  {
    id: "audit-1",
    timestamp: "2026-06-10T08:30:00.000Z",
    module: "Manufacturing",
    action: "Order Creation",
    details: "Manufacturing Order MO-001 created for 4x Wooden Table",
    user: "John Operative"
  },
  {
    id: "audit-2",
    timestamp: "2026-06-10T09:00:00.000Z",
    module: "Manufacturing",
    action: "Status Change",
    details: "MO-001 status changed from in_progress to completed",
    user: "John Operative"
  },
  {
    id: "audit-3",
    timestamp: "2026-06-10T10:00:00.000Z",
    module: "Sales",
    action: "Order Delivery",
    details: "Sales Order SO-003 fully delivered to Luxury Home Designs",
    user: "Sarah Sales"
  },
  {
    id: "audit-4",
    timestamp: "2026-06-12T12:00:00.000Z",
    module: "Purchase",
    action: "Receipt Validation",
    details: "Purchase Order PO-002 received 200 Screws",
    user: "Paul Purchase"
  }
];

const DEFAULT_NOTIFICATIONS = [
  {
    id: "notif-1",
    timestamp: "2026-06-12T12:00:00.000Z",
    type: "purchase_received",
    message: "Purchase Order PO-002 has been fully received. 200x Screws added to stock.",
    read: false
  },
  {
    id: "notif-2",
    timestamp: "2026-06-13T09:00:00.000Z",
    type: "low_stock",
    message: "Low stock alert: Wooden Top (COMP-TOP) is at 12 units (reorder threshold is 5, but on reservations check, free stock is low).",
    read: false
  }
];

// Helper functions for storage
export function getDbItem(key, defaultValue) {
  try {
    const val = localStorage.getItem(`odoo_mini_erp_${key}`);
    if (val === null) {
      localStorage.setItem(`odoo_mini_erp_${key}`, JSON.stringify(defaultValue));
      return defaultValue;
    }
    return JSON.parse(val);
  } catch (e) {
    console.error("Local storage error reading " + key, e);
    return defaultValue;
  }
}

export function setDbItem(key, value) {
  try {
    localStorage.setItem(`odoo_mini_erp_${key}`, JSON.stringify(value));
  } catch (e) {
    console.error("Local storage error writing " + key, e);
  }
}

// Main initial database check and retrieval
export function loadDatabase() {
  return {
    products: getDbItem("products", DEFAULT_PRODUCTS),
    boms: getDbItem("boms", DEFAULT_BOMS),
    salesOrders: getDbItem("salesOrders", DEFAULT_SALES_ORDERS),
    purchaseOrders: getDbItem("purchaseOrders", DEFAULT_PURCHASE_ORDERS),
    manufacturingOrders: getDbItem("manufacturingOrders", DEFAULT_MANUFACTURING_ORDERS),
    stockLedger: getDbItem("stockLedger", DEFAULT_STOCK_LEDGER),
    auditLogs: getDbItem("auditLogs", DEFAULT_AUDIT_LOGS),
    notifications: getDbItem("notifications", DEFAULT_NOTIFICATIONS),
    currentRole: getDbItem("currentRole", "admin"),
    currentUser: getDbItem("currentUser", { name: "Admin User", role: "admin", letters: "AD" })
  };
}

export function saveDatabase(db) {
  setDbItem("products", db.products);
  setDbItem("boms", db.boms);
  setDbItem("salesOrders", db.salesOrders);
  setDbItem("purchaseOrders", db.purchaseOrders);
  setDbItem("manufacturingOrders", db.manufacturingOrders);
  setDbItem("stockLedger", db.stockLedger);
  setDbItem("auditLogs", db.auditLogs);
  setDbItem("notifications", db.notifications);
  setDbItem("currentRole", db.currentRole);
  setDbItem("currentUser", db.currentUser);
}

export function clearDatabase() {
  localStorage.removeItem("odoo_mini_erp_products");
  localStorage.removeItem("odoo_mini_erp_boms");
  localStorage.removeItem("odoo_mini_erp_salesOrders");
  localStorage.removeItem("odoo_mini_erp_purchaseOrders");
  localStorage.removeItem("odoo_mini_erp_manufacturingOrders");
  localStorage.removeItem("odoo_mini_erp_stockLedger");
  localStorage.removeItem("odoo_mini_erp_auditLogs");
  localStorage.removeItem("odoo_mini_erp_notifications");
  localStorage.removeItem("odoo_mini_erp_currentRole");
  localStorage.removeItem("odoo_mini_erp_currentUser");
}
