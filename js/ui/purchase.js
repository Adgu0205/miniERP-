import { state } from '../state.js';
import { getRolePermissions } from './auth.js';
import { showToastNotification } from '../app.js';

export function renderPurchase() {
  const container = document.createElement("div");
  container.className = "purchase-panel card-panel";

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const purchaseOrders = state.getPurchaseOrders();

  container.innerHTML = `
    <div class="panel-header">
      <h3 class="panel-title">Purchase Orders & RFQs</h3>
      <div style="display:flex; gap:12px;">
        ${permissions.canEditPurchases && !permissions.isReadOnly ? `
          <button class="btn btn-primary btn-sm" id="btn-open-create-po-modal">+ Create RFQ</button>
        ` : ''}
      </div>
    </div>

    <div class="table-responsive">
      <table class="erp-table">
        <thead>
          <tr>
            <th>Order Ref</th>
            <th>Date</th>
            <th>Vendor Name</th>
            <th style="text-align:right;">Total Cost</th>
            <th style="text-align:center;">Items count</th>
            <th>Source Document</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${purchaseOrders.map(po => {
            const itemsCount = po.items.reduce((sum, i) => sum + i.quantity, 0);
            return `
              <tr>
                <td style="font-weight:700;">${po.id}</td>
                <td style="color:var(--text-muted); font-size:13px;">${new Date(po.date).toLocaleDateString()}</td>
                <td style="font-weight:600;">${po.vendorName}</td>
                <td style="text-align:right; font-weight:700;">$${po.totalAmount.toFixed(2)}</td>
                <td style="text-align:center;">${itemsCount}</td>
                <td style="font-size:12px; color:var(--text-secondary); font-weight:600;">${po.sourceDocument || '-'}</td>
                <td>
                  <span class="badge badge-${po.status === 'fully_received' ? 'received' : po.status === 'confirmed' ? 'confirmed' : po.status === 'partially_received' ? 'partial' : 'draft'}">
                    ${po.status.replace('_', ' ')}
                  </span>
                </td>
                <td>
                  <button class="btn btn-secondary btn-sm view-po-details-btn" data-id="${po.id}" style="padding:4px 8px; font-size:11px;">View</button>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  // Bind Actions
  setTimeout(() => {
    if (permissions.canEditPurchases && !permissions.isReadOnly) {
      container.querySelector("#btn-open-create-po-modal").addEventListener("click", () => {
        openPurchaseOrderCreateModal();
      });
    }

    container.querySelectorAll(".view-po-details-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        openPurchaseOrderDetailDrawer(e.target.dataset.id);
      });
    });
  }, 30);

  return container;
}

// Drawer Component to view details
function openPurchaseOrderDetailDrawer(poId) {
  const po = state.getPurchaseOrders().find(p => p.id === poId);
  if (!po) return;

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);

  const drawer = document.createElement("div");
  drawer.className = "drawer-overlay";

  drawer.innerHTML = `
    <div class="drawer-content" style="width: 500px;">
      <div class="drawer-header">
        <div>
          <h2 class="drawer-title" style="display:flex; align-items:center; gap:8px;">
            <span>${po.id}</span>
            <span class="badge badge-${po.status === 'fully_received' ? 'received' : po.status === 'confirmed' ? 'confirmed' : 'draft'}">${po.status.replace('_', ' ')}</span>
          </h2>
          <span style="font-size:12px; color:var(--text-muted);">${new Date(po.date).toLocaleString()}</span>
        </div>
        <button class="modal-close" id="close-po-drawer">✕</button>
      </div>

      <div class="drawer-body">
        <div style="margin-bottom: 24px;">
          <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:4px;">Vendor Details</h4>
          <div style="font-size:16px; font-weight:700;">${po.vendorName}</div>
        </div>

        <div style="margin-bottom: 24px;">
          <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">Purchase Items</h4>
          <div class="lines-list" style="margin-top:0;">
            <div class="line-header" style="grid-template-columns: 2fr 1fr 1fr; border:none;">
              <span>Product</span>
              <span style="text-align:center;">Qty Ordered</span>
              <span style="text-align:center;">Qty Received</span>
            </div>
            ${po.items.map(item => `
              <div class="line-item-row" style="grid-template-columns: 2fr 1fr 1fr;">
                <span style="font-weight:600;">${item.name}</span>
                <td style="text-align:center; font-weight:600;">${item.quantity}</td>
                <td style="text-align:center; color:var(--accent-hover); font-weight:700;">
                  ${po.receivedQtyMap[item.productId] || 0}
                </td>
              </div>
            `).join('')}
          </div>
          <div style="display:flex; justify-content:space-between; margin-top:16px; padding:0 8px;">
            <span style="font-weight:600;">Total Purchase Amount:</span>
            <span style="font-weight:700; font-size:18px; color:var(--text-primary);">$${po.totalAmount.toFixed(2)}</span>
          </div>
        </div>

        <div style="margin-bottom: 24px;">
          <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:4px;">Source Reference</h4>
          <div style="font-size:14px; font-weight:600; color:var(--text-primary);">${po.sourceDocument || 'None (Direct RFQ)'}</div>
        </div>

        <div style="margin-top: 32px; display:flex; flex-direction:column; gap:12px;">
          ${po.status === 'draft' && permissions.canEditPurchases && !permissions.isReadOnly ? `
            <button class="btn btn-primary" id="btn-drawer-confirm-po" style="width:100%;">Confirm Purchase Order</button>
          ` : ''}

          ${['confirmed', 'partially_received'].includes(po.status) && permissions.canEditPurchases && !permissions.isReadOnly ? `
            <button class="btn btn-primary" id="btn-drawer-receive-po" style="width:100%;">Receive Products</button>
          ` : ''}
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(drawer);

  const closeDrawer = () => {
    document.body.removeChild(drawer);
  };

  drawer.querySelector("#close-po-drawer").addEventListener("click", closeDrawer);
  drawer.addEventListener("click", (e) => {
    if (e.target === drawer) closeDrawer();
  });

  if (permissions.canEditPurchases && !permissions.isReadOnly) {
    const confirmBtn = drawer.querySelector("#btn-drawer-confirm-po");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", () => {
        po.status = "confirmed";
        state.addAuditLog("Purchase", "Status Change", `Purchase Order ${po.id} confirmed`);
        state.notify();
        closeDrawer();
        showToastNotification(`Purchase Order ${po.id} confirmed!`, "success");
      });
    }

    const receiveBtn = drawer.querySelector("#btn-drawer-receive-po");
    if (receiveBtn) {
      receiveBtn.addEventListener("click", () => {
        closeDrawer();
        openReceiptDialog(po);
      });
    }
  }
}

// Receipt Validation Dialog
function openReceiptDialog(po) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 500px;">
      <div class="modal-header">
        <h3 class="modal-title">Material Receipt Validation</h3>
        <button class="modal-close" id="close-rec-modal">✕</button>
      </div>
      <form id="receipt-validation-form">
        <div class="modal-body">
          <div style="margin-bottom:16px; font-size:13px; color:var(--text-secondary);">
            Verify and input the quantities of materials received into physical inventory.
          </div>
          
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${po.items.map(item => {
              const alreadyReceived = po.receivedQtyMap[item.productId] || 0;
              const remaining = item.quantity - alreadyReceived;

              return `
                <div style="border:1px solid var(--border-color); padding:12px; border-radius:var(--border-radius-md); background-color:var(--bg-secondary);">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700;">${item.name}</span>
                    <span style="font-size:12px; color:var(--text-secondary);">Ordered: ${item.quantity} (Pending: ${remaining})</span>
                  </div>
                  <div class="form-grid" style="grid-template-columns: 2fr 1fr; margin-bottom:0; align-items:center; margin-top:10px;">
                    <div style="font-size:12px; color:var(--text-secondary);">
                      Validate physical count:
                    </div>
                    <div class="form-group" style="gap:2px;">
                      <label style="font-size:10px;">Receive Quantity</label>
                      <input type="number" class="form-control receive-qty-input" data-prod-id="${item.productId}" min="0" max="${remaining}" value="${remaining}" style="padding:6px; font-weight:700; text-align:center;">
                    </div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-rec-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Validate Receipt</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-rec-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-rec-modal").addEventListener("click", closeForm);

  modal.querySelector("#receipt-validation-form").addEventListener("submit", (e) => {
    e.preventDefault();
    
    const receiveQuantities = {};
    modal.querySelectorAll(".receive-qty-input").forEach(input => {
      receiveQuantities[input.dataset.prodId] = parseInt(input.value) || 0;
    });

    state.receivePurchaseOrder(po.id, receiveQuantities);
    closeForm();
    showToastNotification(`Materials successfully received and cataloged.`, "success");
  });
}

// Purchase Order Creation Form Modal
function openPurchaseOrderCreateModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";

  const products = state.getProducts();

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 650px;">
      <div class="modal-header">
        <h3 class="modal-title">Create Purchase Order RFQ</h3>
        <button class="modal-close" id="close-po-modal">✕</button>
      </div>
      <form id="po-create-form">
        <div class="modal-body">
          <div class="form-group" style="margin-bottom:16px;">
            <label for="po-vendor">Vendor Name *</label>
            <input type="text" id="po-vendor" class="form-control" required placeholder="Enter supplier name (e.g. Timber Supplier Co)...">
          </div>

          <div style="margin-top:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary);">Request Lines</h4>
              <button type="button" class="btn btn-secondary btn-sm" id="btn-add-po-line">+ Add Line</button>
            </div>
            
            <div class="lines-list">
              <div class="line-header">
                <span>Material Product</span>
                <span style="text-align:right;">Quantity</span>
                <span style="text-align:right;">Unit Cost</span>
                <span></span>
              </div>
              <div id="po-lines-container">
                <!-- Lines render dynamically -->
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-po-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Save RFQ Draft</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-po-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-po-modal").addEventListener("click", closeForm);

  const linesContainer = modal.querySelector("#po-lines-container");
  
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line-item-row";
    row.innerHTML = `
      <select class="form-control line-product-select" required>
        <option value="" disabled selected>Select component...</option>
        ${products.map(p => `<option value="${p.id}" data-cost="${p.costPrice}">${p.name} (${p.sku})</option>`).join('')}
      </select>
      <input type="number" class="form-control line-qty-input" required min="1" value="10" style="text-align:right;">
      <input type="number" class="form-control line-cost-input" required min="0" step="0.01" value="0.00" style="text-align:right;">
      <button type="button" class="line-remove-btn">✕</button>
    `;

    linesContainer.appendChild(row);

    // Bind cost lookup
    row.querySelector(".line-product-select").addEventListener("change", (e) => {
      const selectedOption = e.target.options[e.target.selectedIndex];
      const cost = parseFloat(selectedOption.dataset.cost) || 0;
      row.querySelector(".line-cost-input").value = cost.toFixed(2);
    });

    row.querySelector(".line-remove-btn").addEventListener("click", () => {
      linesContainer.removeChild(row);
    });
  };

  // Add initial line
  addLine();

  modal.querySelector("#btn-add-po-line").addEventListener("click", addLine);

  modal.querySelector("#po-create-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const vendorName = document.getElementById("po-vendor").value;
    const items = [];
    let totalAmount = 0;

    modal.querySelectorAll(".line-item-row").forEach(row => {
      const select = row.querySelector(".line-product-select");
      const qty = parseInt(row.querySelector(".line-qty-input").value) || 0;
      const cost = parseFloat(row.querySelector(".line-cost-input").value) || 0;

      if (select.value && qty > 0) {
        items.push({
          productId: select.value,
          name: select.options[select.selectedIndex].text.split(' (')[0],
          quantity: qty,
          unitPrice: cost
        });
        totalAmount += qty * cost;
      }
    });

    if (items.length === 0) {
      alert("Please add at least one line item.");
      return;
    }

    state.addPurchaseOrder({
      vendorName,
      items,
      totalAmount
    });

    closeForm();
    showToastNotification("Purchase RFQ Draft saved.", "success");
  });
}
