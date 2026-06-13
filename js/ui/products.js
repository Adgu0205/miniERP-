import { state } from '../state.js';
import { getRolePermissions } from './auth.js';
import { showToastNotification } from '../app.js';

export function renderProducts() {
  const container = document.createElement("div");
  container.className = "products-panel card-panel";

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const products = state.getProducts();
  const boms = state.getBoms();

  // Draw Header Actions
  container.innerHTML = `
    <div class="panel-header">
      <h3 class="panel-title">Product Catalog & Master Inventory</h3>
      <div style="display:flex; gap:12px;">
        <input type="text" id="search-products-input" placeholder="Search by SKU or name..." class="form-control" style="width:240px; padding: 6px 12px; font-size:13px;">
        ${permissions.canEditProducts && !permissions.isReadOnly ? `
          <button class="btn btn-primary btn-sm" id="btn-open-create-prod-modal">+ New Product</button>
        ` : ''}
      </div>
    </div>
    
    <div class="table-responsive">
      <table class="erp-table" id="products-list-table">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Name</th>
            <th>Category</th>
            <th style="text-align:right;">Cost Price</th>
            <th style="text-align:right;">Sales Price</th>
            <th style="text-align:center;">On Hand</th>
            <th style="text-align:center;">Reserved</th>
            <th style="text-align:center;">Free To Use</th>
            <th>Replenishment Rule</th>
            <th>Preferred Vendor</th>
            <th>BoM Recipe</th>
            <th>Status</th>
            ${permissions.canEditProducts && !permissions.isReadOnly ? `<th>Actions</th>` : ''}
          </tr>
        </thead>
        <tbody id="products-table-body">
          ${products.map(p => {
            const hasBom = boms.some(b => b.productId === p.id);
            return `
              <tr data-id="${p.id}" data-search="${p.sku.toLowerCase()} ${p.name.toLowerCase()}">
                <td style="font-weight:700;">${p.sku}</td>
                <td style="font-weight:600; color:var(--text-primary);">${p.name}</td>
                <td><span style="font-size:12px; color:var(--text-secondary);">${p.category}</span></td>
                <td style="text-align:right;">$${p.costPrice.toFixed(2)}</td>
                <td style="text-align:right;">$${p.salesPrice.toFixed(2)}</td>
                <td style="text-align:center; font-weight:700; color: #111111;">${p.onHand}</td>
                <td style="text-align:center; color:${p.reserved > 0 ? '#ef4444' : 'var(--text-muted)'}; font-weight:600;">
                  ${p.reserved}
                </td>
                <td style="text-align:center; font-weight:700; color:var(--accent-hover);">${p.freeToUse}</td>
                <td>
                  <span class="badge ${p.procureStrategy === 'MTO' ? 'badge-mto' : 'badge-mts'}">
                    ${p.procureStrategy} - ${p.procureType}
                  </span>
                  <div style="font-size:10px; color:var(--text-muted); margin-top:2px;">
                    Min limit: ${p.reorderThreshold}
                  </div>
                </td>
                <td style="font-size:13px; color:var(--text-secondary);">${p.vendor || '-'}</td>
                <td>
                  ${hasBom ? `<span style="font-size:12px; color:var(--accent-hover); font-weight:600;">Linked Recipe</span>` : `<span style="font-size:12px; color:var(--text-muted);">No Recipe</span>`}
                </td>
                <td>
                  <span class="badge" style="background-color:${p.status === 'Low Stock' ? '#fef3c7' : 'var(--accent-light)'}; color:${p.status === 'Low Stock' ? '#b45309' : 'var(--accent-hover)'};">
                    ${p.status}
                  </span>
                </td>
                ${permissions.canEditProducts && !permissions.isReadOnly ? `
                  <td>
                    <button class="btn btn-secondary btn-sm edit-prod-btn" data-id="${p.id}" style="padding:4px 8px; font-size:11px;">Edit</button>
                  </td>
                ` : ''}
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  // Bind Actions
  setTimeout(() => {
    // Search filter
    const searchInput = container.querySelector("#search-products-input");
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase();
      container.querySelectorAll("#products-table-body tr").forEach(row => {
        if (row.dataset.search.includes(query)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });

    // Modal creation button
    if (permissions.canEditProducts && !permissions.isReadOnly) {
      container.querySelector("#btn-open-create-prod-modal").addEventListener("click", () => {
        openProductFormModal(null);
      });

      // Edit row buttons
      container.querySelectorAll(".edit-prod-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          const prodId = e.target.dataset.id;
          openProductFormModal(prodId);
        });
      });
    }
  }, 30);

  return container;
}

// Modal Form Popup
function openProductFormModal(productId = null) {
  const products = state.getProducts();
  const targetProduct = productId ? products.find(p => p.id === productId) : null;
  const isEdit = !!targetProduct;

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-content" style="max-width: 600px;">
      <div class="modal-header">
        <h3 class="modal-title">${isEdit ? 'Modify Product Specifications' : 'Catalog New Product'}</h3>
        <button class="modal-close" id="close-prod-modal">✕</button>
      </div>
      <form id="product-modal-form">
        <div class="modal-body">
          <div class="form-grid">
            <div class="form-group">
              <label for="prod-name">Product Name *</label>
              <input type="text" id="prod-name" class="form-control" required value="${isEdit ? targetProduct.name : ''}">
            </div>
            <div class="form-group">
              <label for="prod-sku">SKU Code *</label>
              <input type="text" id="prod-sku" class="form-control" required value="${isEdit ? targetProduct.sku : ''}" ${isEdit ? 'disabled' : ''}>
            </div>
          </div>
          
          <div class="form-grid">
            <div class="form-group">
              <label for="prod-category">Category</label>
              <select id="prod-category" class="form-control">
                <option value="Furniture" ${isEdit && targetProduct.category === 'Furniture' ? 'selected' : ''}>Furniture</option>
                <option value="Components" ${isEdit && targetProduct.category === 'Components' ? 'selected' : ''}>Components</option>
              </select>
            </div>
            <div class="form-group">
              <label for="prod-vendor">Preferred Vendor</label>
              <input type="text" id="prod-vendor" class="form-control" placeholder="Supplier name..." value="${isEdit ? targetProduct.vendor : ''}">
            </div>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label for="prod-cost">Cost Price ($) *</label>
              <input type="number" id="prod-cost" class="form-control" step="0.01" min="0" required value="${isEdit ? targetProduct.costPrice : '0.00'}">
            </div>
            <div class="form-group">
              <label for="prod-sales">Sales Price ($) *</label>
              <input type="number" id="prod-sales" class="form-control" step="0.01" min="0" required value="${isEdit ? targetProduct.salesPrice : '0.00'}">
            </div>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label for="prod-strategy">Procurement Route</label>
              <select id="prod-strategy" class="form-control">
                <option value="MTS" ${isEdit && targetProduct.procureStrategy === 'MTS' ? 'selected' : ''}>Make To Stock (MTS)</option>
                <option value="MTO" ${isEdit && targetProduct.procureStrategy === 'MTO' ? 'selected' : ''}>Make To Order (MTO)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="prod-type">Procurement Type</label>
              <select id="prod-type" class="form-control">
                <option value="Manufacturing" ${isEdit && targetProduct.procureType === 'Manufacturing' ? 'selected' : ''}>Manufacturing Replenish</option>
                <option value="Purchase" ${isEdit && targetProduct.procureType === 'Purchase' ? 'selected' : ''}>Purchase Replenish</option>
                <option value="None" ${isEdit && targetProduct.procureType === 'None' ? 'selected' : ''}>None</option>
              </select>
            </div>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label for="prod-threshold">Reorder Threshold Limit *</label>
              <input type="number" id="prod-threshold" class="form-control" min="0" required value="${isEdit ? targetProduct.reorderThreshold : '5'}">
            </div>
            ${isEdit ? `
              <div class="form-group">
                <label style="opacity:0.6;">Current On-Hand Balance</label>
                <input type="text" class="form-control" value="${targetProduct.onHand}" disabled style="background-color:var(--bg-secondary);">
              </div>
            ` : ''}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-prod-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">${isEdit ? 'Save Changes' : 'Catalog Product'}</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  // Bind cancels
  modal.querySelector("#close-prod-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-prod-modal").addEventListener("click", closeForm);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeForm();
  });

  // Form Submit Handler
  modal.querySelector("#product-modal-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const data = {
      name: document.getElementById("prod-name").value,
      category: document.getElementById("prod-category").value,
      costPrice: parseFloat(document.getElementById("prod-cost").value) || 0,
      salesPrice: parseFloat(document.getElementById("prod-sales").value) || 0,
      procureStrategy: document.getElementById("prod-strategy").value,
      procureType: document.getElementById("prod-type").value,
      vendor: document.getElementById("prod-vendor").value,
      reorderThreshold: parseInt(document.getElementById("prod-threshold").value) || 0
    };

    if (isEdit) {
      // Direct update in memory and notify
      Object.assign(targetProduct, data);
      state.recalculateQuantities();
      state.addAuditLog("Product", "Price Changes", `Product ${targetProduct.sku} updated properties.`);
      state.notify();
      showToastNotification("Product modified successfully.", "success");
    } else {
      data.sku = document.getElementById("prod-sku").value.toUpperCase();
      state.addProduct(data);
      showToastNotification("New product cataloged.", "success");
    }

    closeForm();
  });
}
