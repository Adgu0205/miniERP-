import { state } from '../state.js';

// Defines the pages each user role is permitted to view.
const ROLE_ACCESS_MAP = {
  admin: ["dashboard", "products", "sales", "purchase", "manufacturing", "bom", "inventory", "ledger", "audit"],
  sales_user: ["dashboard", "products", "sales"],
  purchase_user: ["dashboard", "products", "purchase"],
  manufacturing_user: ["dashboard", "manufacturing", "bom"],
  inventory_manager: ["dashboard", "products", "inventory", "ledger"],
  business_owner: ["dashboard", "products", "sales", "purchase", "manufacturing", "bom", "inventory", "ledger"]
};

// Check if a role can access a page
export function hasPageAccess(role, page) {
  const allowed = ROLE_ACCESS_MAP[role];
  if (!allowed) return false;
  return allowed.includes(page);
}

// Get warning screen if no access
export function renderNoAccessScreen(pageName) {
  const container = document.createElement("div");
  container.className = "no-access-container";
  
  // Format page display name
  const pageDisplay = pageName.charAt(0).toUpperCase() + pageName.slice(1).replace('_', ' ');

  container.innerHTML = `
    <div class="no-access-icon">✕</div>
    <h2 class="no-access-title">Access Restricted</h2>
    <p class="no-access-desc">
      Your current active role (<strong>${state.db.currentUser.name}</strong>) does not have authorization to view the <strong>${pageDisplay}</strong> module.
    </p>
    <p class="no-access-desc" style="margin-top: 12px; font-size: 13px;">
      <em>Use the "Active Role" selector in the top-right header to switch roles for testing.</em>
    </p>
  `;
  
  return container;
}

// Helper to determine edit capabilities based on role
export function getRolePermissions(role) {
  return {
    canEditProducts: ["admin", "inventory_manager"].includes(role),
    canEditSales: ["admin", "sales_user"].includes(role),
    canEditPurchases: ["admin", "purchase_user"].includes(role),
    canEditManufacturing: ["admin", "manufacturing_user"].includes(role),
    canEditBom: ["admin", "manufacturing_user"].includes(role),
    canAdjustInventory: ["admin", "inventory_manager"].includes(role),
    canViewAuditLogs: ["admin"].includes(role),
    isReadOnly: role === "business_owner"
  };
}
