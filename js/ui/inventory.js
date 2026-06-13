import { state } from '../state.js';
import { getRolePermissions } from './auth.js';
import { showToastNotification } from '../app.js';

export function renderInventory() {
  const container = document.createElement("div");
  container.className = "inventory-workspace-panel";

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const products = state.getProducts();

  // 1. Valuation Calculations
  const totalValuation = products.reduce((sum, p) => sum + (p.onHand * p.costPrice), 0);
  
  // 2. Classifications
  const lowStock = products.filter(p => p.freeToUse < p.reorderThreshold);
  const reservedStock = products.filter(p => p.reserved > 0);
  // Overstocked: freeToUse exceeds three times the threshold
  const overstocked = products.filter(p => p.reorderThreshold > 0 && p.freeToUse > (p.reorderThreshold * 4));

  container.innerHTML = `
    <!-- Top summary widget panels -->
    <div class="dashboard-grid" style="margin-bottom: 24px;">
      
      <div class="kpi-card" style="min-height: 120px;">
        <div class="kpi-header">
          <span>Total Valuation (Cost Basis)</span>
          <div class="kpi-icon-container green-accent"><strong>$</strong></div>
        </div>
        <div class="kpi-val" style="font-size: 28px; margin-top: 8px;">
          $${totalValuation.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
        </div>
      </div>

      <div class="kpi-card" style="min-height: 120px;">
        <div class="kpi-header">
          <span>Low Stock Alerts</span>
          <span class="badge badge-cancelled" style="font-size: 10px;">${lowStock.length} Warning</span>
        </div>
        <div style="font-size:13px; color:var(--text-secondary); margin-top:12px; max-height:45px; overflow-y:auto;">
          ${lowStock.length === 0 ? 'All levels safe.' : lowStock.map(p => `${p.sku} (${p.freeToUse}/${p.reorderThreshold})`).join(', ')}
        </div>
      </div>

      <div class="kpi-card" style="min-height: 120px;">
        <div class="kpi-header">
          <span>Committed/Reserved Stock</span>
          <span class="badge badge-confirmed" style="font-size: 10px;">${reservedStock.length} Items</span>
        </div>
        <div style="font-size:13px; color:var(--text-secondary); margin-top:12px; max-height:45px; overflow-y:auto;">
          ${reservedStock.length === 0 ? 'No reserved stock.' : reservedStock.map(p => `${p.sku} (x${p.reserved})`).join(', ')}
        </div>
      </div>

      <div class="kpi-card" style="min-height: 120px;">
        <div class="kpi-header">
          <span>Overstock Risks</span>
          <span class="badge badge-progress" style="font-size: 10px;">${overstocked.length} Lines</span>
        </div>
        <div style="font-size:13px; color:var(--text-secondary); margin-top:12px; max-height:45px; overflow-y:auto;">
          ${overstocked.length === 0 ? 'No overstocks.' : overstocked.map(p => `${p.sku} (${p.onHand} units)`).join(', ')}
        </div>
      </div>

    </div>

    <!-- Main Stock Valuation Table -->
    <div class="card-panel">
      <div class="panel-header">
        <h3 class="panel-title">Inventory Valuation & Auditing</h3>
        <div>
          ${permissions.canAdjustInventory && !permissions.isReadOnly ? `
            <button class="btn btn-primary btn-sm" id="btn-master-adjust-inventory">Post Stock Adjustment</button>
          ` : ''}
        </div>
      </div>

      <div class="table-responsive">
        <table class="erp-table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product Name</th>
              <th>Category</th>
              <th style="text-align:right;">Unit Cost</th>
              <th style="text-align:center;">On Hand</th>
              <th style="text-align:center;">Reserved</th>
              <th style="text-align:center;">Free Stock</th>
              <th style="text-align:right;">Total Value</th>
              <th style="text-align:center;">Average Age</th>
              ${permissions.canAdjustInventory && !permissions.isReadOnly ? `<th>Actions</th>` : ''}
            </tr>
          </thead>
          <tbody>
            ${products.map(p => {
              const value = p.onHand * p.costPrice;
              // Mock aging days
              const age = p.category === 'Components' ? '8 Days' : '14 Days';
              return `
                <tr>
                  <td style="font-weight:700;">${p.sku}</td>
                  <td style="font-weight:600;">${p.name}</td>
                  <td><span style="font-size:12px; color:var(--text-secondary);">${p.category}</span></td>
                  <td style="text-align:right;">$${p.costPrice.toFixed(2)}</td>
                  <td style="text-align:center; font-weight:600;">${p.onHand}</td>
                  <td style="text-align:center; color:${p.reserved > 0 ? '#ef4444' : 'var(--text-muted)'}; font-weight:600;">${p.reserved}</td>
                  <td style="text-align:center; font-weight:700; color:var(--accent-hover);">${p.freeToUse}</td>
                  <td style="text-align:right; font-weight:700; color:var(--text-primary);">$${value.toFixed(2)}</td>
                  <td style="text-align:center; font-size:12px; color:var(--text-muted);">${age}</td>
                  ${permissions.canAdjustInventory && !permissions.isReadOnly ? `
                    <td>
                      <button class="btn btn-secondary btn-sm adjust-row-btn" data-id="${p.id}" style="padding:4px 8px; font-size:11px;">Adjust</button>
                    </td>
                  ` : ''}
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Bind Actions
  setTimeout(() => {
    if (permissions.canAdjustInventory && !permissions.isReadOnly) {
      container.querySelector("#btn-master-adjust-inventory").addEventListener("click", () => {
        openManualAdjustmentModal(null);
      });

      container.querySelectorAll(".adjust-row-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          openManualAdjustmentModal(e.target.dataset.id);
        });
      });
    }
  }, 30);

  return container;
}

// Manual Adjustment Dialog Form
function openManualAdjustmentModal(productId = null) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";

  const products = state.getProducts();
  const selectedProd = productId ? products.find(p => p.id === productId) : null;

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 500px;">
      <div class="modal-header">
        <h3 class="modal-title">Physical Inventory Stock Correction</h3>
        <button class="modal-close" id="close-adj-modal">✕</button>
      </div>
      <form id="adjustment-form">
        <div class="modal-body">
          <div class="form-group" style="margin-bottom:16px;">
            <label for="adj-product">Select Product *</label>
            <select id="adj-product" class="form-control" required ${selectedProd ? 'disabled' : ''}>
              <option value="" disabled selected>Choose product...</option>
              ${products.map(p => `<option value="${p.id}" ${selectedProd && selectedProd.id === p.id ? 'selected' : ''} data-onhand="${p.onHand}">${p.name} (SKU: ${p.sku} | Current: ${p.onHand})</option>`).join('')}
            </select>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label for="adj-qty">New Physical On-Hand Count *</label>
              <input type="number" id="adj-qty" class="form-control" min="0" required value="${selectedProd ? selectedProd.onHand : '0'}">
            </div>
            <div class="form-group">
              <label style="opacity:0.6;">Current Count</label>
              <input type="text" id="adj-current" class="form-control" disabled style="background-color:var(--bg-secondary);" value="${selectedProd ? selectedProd.onHand : '-'}">
            </div>
          </div>

          <div class="form-group" style="margin-top:16px;">
            <label for="adj-reason">Correction Reason *</label>
            <input type="text" id="adj-reason" class="form-control" required placeholder="Cycle count, scrap correction, damaged goods...">
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-adj-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Submit Correction</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-adj-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-adj-modal").addEventListener("click", closeForm);

  const productSelect = modal.querySelector("#adj-product");
  const currentInput = modal.querySelector("#adj-current");
  const qtyInput = modal.querySelector("#adj-qty");

  // Dynamic current count update on select
  productSelect.addEventListener("change", (e) => {
    const selectedOption = e.target.options[e.target.selectedIndex];
    const onhand = selectedOption.dataset.onhand;
    currentInput.value = onhand;
    qtyInput.value = onhand;
  });

  modal.querySelector("#adjustment-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const finalProductId = selectedProd ? selectedProd.id : productSelect.value;
    const newQty = parseInt(qtyInput.value) || 0;
    const reason = document.getElementById("adj-reason").value;

    state.adjustStockManually(finalProductId, newQty, reason);
    closeForm();
    showToastNotification(`Posted inventory correction adjustment.`, "success");
  });
}
