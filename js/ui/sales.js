import { state } from '../state.js';
import { getRolePermissions } from './auth.js';
import { triggerMTOProcurement, getProcurementRecommendation } from '../procurement.js';
import { showToastNotification } from '../app.js';

export function renderSales() {
  const container = document.createElement("div");
  container.className = "sales-panel";

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const salesOrders = state.getSalesOrders();

  // Kanban Columns
  const columns = {
    draft: { title: "Draft", badge: "badge-draft", items: [] },
    confirmed: { title: "Confirmed / Reserved", badge: "badge-confirmed", items: [] },
    partially_delivered: { title: "Partially Delivered", badge: "badge-partial", items: [] },
    fully_delivered: { title: "Fully Delivered", badge: "badge-completed", items: [] }
  };

  // Populate columns
  salesOrders.forEach(so => {
    if (columns[so.status]) {
      columns[so.status].items.push(so);
    }
  });

  container.innerHTML = `
    <div class="panel-header" style="background-color: var(--bg-primary); border-radius: var(--border-radius-lg); border:1px solid var(--border-color); padding: 20px 24px; margin-bottom: 24px; box-shadow: var(--shadow-sm);">
      <h3 class="panel-title">Sales Order Pipelines</h3>
      <div>
        ${permissions.canEditSales && !permissions.isReadOnly ? `
          <button class="btn btn-primary btn-sm" id="btn-open-create-so-modal">+ Create Sales Order</button>
        ` : ''}
      </div>
    </div>

    <!-- Kanban Workspace -->
    <div class="kanban-board-container">
      ${Object.keys(columns).map(statusKey => {
        const col = columns[statusKey];
        return `
          <div class="kanban-column" data-status="${statusKey}">
            <div class="kanban-column-header">
              <span class="kanban-column-title">
                <span class="badge ${col.badge}" style="border-radius:6px; font-size:11px; padding:3px 8px;">${col.title}</span>
              </span>
              <span class="kanban-card-count">${col.items.length}</span>
            </div>
            
            <div class="kanban-cards-wrapper">
              ${col.items.map(so => `
                <div class="kanban-card sales-so-card" data-id="${so.id}">
                  <div class="kanban-card-header">
                    <span class="kanban-card-id">${so.id}</span>
                    <span style="font-size:11px; color:var(--text-muted);">${new Date(so.date).toLocaleDateString([], {month:'short', day:'numeric'})}</span>
                  </div>
                  <div class="kanban-card-title">${so.customerName}</div>
                  <div class="kanban-card-body">
                    ${so.items.map(item => `
                      <div style="display:flex; justify-content:space-between; margin-top:2px;">
                        <span>${item.name}</span>
                        <strong>x${item.quantity}</strong>
                      </div>
                    `).join('')}
                  </div>
                  <div class="kanban-card-footer">
                    <span class="kanban-card-price">$${so.totalAmount.toFixed(2)}</span>
                    <span style="font-size:10px; text-transform:uppercase; font-weight:700; color:var(--text-muted);">
                      ${so.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;

  // Bind Listeners
  setTimeout(() => {
    // Check if redirect triggered SO modal
    if (sessionStorage.getItem("trigger_create_so_modal") === "true") {
      sessionStorage.removeItem("trigger_create_so_modal");
      if (permissions.canEditSales && !permissions.isReadOnly) {
        openSalesOrderCreateModal();
      }
    }

    if (permissions.canEditSales && !permissions.isReadOnly) {
      container.querySelector("#btn-open-create-so-modal").addEventListener("click", () => {
        openSalesOrderCreateModal();
      });
    }

    // Card click events to load details drawer
    container.querySelectorAll(".sales-so-card").forEach(card => {
      card.addEventListener("click", () => {
        openSalesOrderDetailDrawer(card.dataset.id);
      });
    });

  }, 30);

  return container;
}

// Drawer Component to view SO details, confirm, deliver, and show trace
function openSalesOrderDetailDrawer(soId) {
  const so = state.getSalesOrders().find(s => s.id === soId);
  if (!so) return;

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);

  const drawer = document.createElement("div");
  drawer.className = "drawer-overlay";

  // Find linked documents in procurement chain
  const linkedMOs = state.getManufacturingOrders().filter(m => m.sourceDocument === so.id || m.procurementGroupId === so.procurementGroupId);
  const linkedPOs = state.getPurchaseOrders().filter(p => p.sourceDocument === so.id);
  
  // Also check if component POs are linked to the MOs of this SO
  linkedMOs.forEach(mo => {
    const compPOs = state.getPurchaseOrders().filter(p => p.sourceDocument === mo.id);
    compPOs.forEach(po => {
      if (!linkedPOs.some(p => p.id === po.id)) {
        linkedPOs.push(po);
      }
    });
  });

  const hasProcurementChain = linkedMOs.length > 0 || linkedPOs.length > 0;

  drawer.innerHTML = `
    <div class="drawer-content" style="width: 500px;">
      <div class="drawer-header">
        <div>
          <h2 class="drawer-title" style="display:flex; align-items:center; gap:8px;">
            <span>${so.id}</span>
            <span class="badge badge-${so.status === 'fully_delivered' ? 'completed' : so.status === 'confirmed' ? 'confirmed' : 'draft'}">${so.status.replace('_', ' ')}</span>
          </h2>
          <span style="font-size:12px; color:var(--text-muted);">${new Date(so.date).toLocaleString()}</span>
        </div>
        <button class="modal-close" id="close-so-drawer">✕</button>
      </div>

      <div class="drawer-body">
        <div style="margin-bottom: 24px;">
          <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:4px;">Customer Details</h4>
          <div style="font-size:16px; font-weight:700;">${so.customerName}</div>
        </div>

        <div style="margin-bottom: 24px;">
          <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">Order Lines</h4>
          <div class="lines-list" style="margin-top:0;">
            <div class="line-header" style="grid-template-columns: 2fr 1fr 1fr; border:none;">
              <span>Product</span>
              <span style="text-align:center;">Qty Ordered</span>
              <span style="text-align:center;">Qty Delivered</span>
            </div>
            ${so.items.map(item => `
              <div class="line-item-row" style="grid-template-columns: 2fr 1fr 1fr;">
                <span style="font-weight:600;">${item.name}</span>
                <td style="text-align:center; font-weight:600;">${item.quantity}</td>
                <td style="text-align:center; color:var(--accent-hover); font-weight:700;">
                  ${so.deliveredQtyMap[item.productId] || 0}
                </td>
              </div>
            `).join('')}
          </div>
          <div style="display:flex; justify-content:space-between; margin-top:16px; padding:0 8px;">
            <span style="font-weight:600;">Total Amount:</span>
            <span style="font-weight:700; font-size:18px; color:var(--text-primary);">$${so.totalAmount.toFixed(2)}</span>
          </div>
        </div>

        <!-- Procurement Chain Visualization -->
        ${hasProcurementChain ? `
          <div style="margin-bottom: 24px;">
            <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">Replenishment routes</h4>
            <div class="procurement-chain">
              <div class="chain-step active">
                <span class="chain-step-title">${so.id}</span>
                <span class="chain-step-sub">Sales Order</span>
              </div>
              
              ${linkedMOs.map(mo => `
                <div class="chain-arrow">➔</div>
                <div class="chain-step ${mo.status === 'completed' ? 'active' : ''}">
                  <span class="chain-step-title">${mo.id}</span>
                  <span class="chain-step-sub">${mo.status}</span>
                </div>
              `).join('')}

              ${linkedPOs.map(po => `
                <div class="chain-arrow">➔</div>
                <div class="chain-step ${po.status === 'fully_received' ? 'active' : ''}">
                  <span class="chain-step-title">${po.id}</span>
                  <span class="chain-step-sub">${po.status}</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Actions panel inside Drawer -->
        <div style="margin-top: 32px; display:flex; flex-direction:column; gap:12px;">
          ${so.status === 'draft' && permissions.canEditSales && !permissions.isReadOnly ? `
            <button class="btn btn-primary" id="btn-drawer-confirm-so" style="width:100%;">Confirm Sales Order</button>
            <button class="btn btn-danger" id="btn-drawer-cancel-so" style="width:100%;">Cancel Order</button>
          ` : ''}

          ${['confirmed', 'partially_delivered'].includes(so.status) && permissions.canEditSales && !permissions.isReadOnly ? `
            <button class="btn btn-primary" id="btn-drawer-deliver-so" style="width:100%;">Deliver Products</button>
            <button class="btn btn-secondary" id="btn-drawer-cancel-so" style="width:100%;">Cancel Order</button>
          ` : ''}
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(drawer);

  const closeDrawer = () => {
    document.body.removeChild(drawer);
  };

  drawer.querySelector("#close-so-drawer").addEventListener("click", closeDrawer);
  drawer.addEventListener("click", (e) => {
    if (e.target === drawer) closeDrawer();
  });

  // Action listeners
  if (permissions.canEditSales && !permissions.isReadOnly) {
    const confirmBtn = drawer.querySelector("#btn-drawer-confirm-so");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", () => {
        closeDrawer();
        
        // Confirm SO and run reservations
        state.confirmSalesOrder(so.id, (confirmedSo, shortages) => {
          // Callback triggers if shortages are found
          openProcurementTriggerDialog(confirmedSo, shortages);
        });

        showToastNotification(`Sales Order ${so.id} confirmed!`, "success");
      });
    }

    const cancelBtn = drawer.querySelector("#btn-drawer-cancel-so");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        state.cancelSalesOrder(so.id);
        closeDrawer();
        showToastNotification(`Sales Order ${so.id} cancelled.`, "info");
      });
    }

    const deliverBtn = drawer.querySelector("#btn-drawer-deliver-so");
    if (deliverBtn) {
      deliverBtn.addEventListener("click", () => {
        closeDrawer();
        openDeliveryDialog(so);
      });
    }
  }
}

// Dialog that prompts when stock shortage is detected on confirm
function openProcurementTriggerDialog(salesOrder, shortages) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  
  // Run recommendations for each shortage item
  const shortageData = shortages.map(s => {
    const rec = getProcurementRecommendation(s.productId, s.shortage);
    return { ...s, rec };
  });

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 600px;">
      <div class="modal-header">
        <h3 class="modal-title">Inventory Shortage Detected</h3>
        <button class="modal-close" id="close-proc-modal">✕</button>
      </div>
      <div class="modal-body">
        <div class="alert-box warning">
          <div>⚠️</div>
          <div>
            <strong>Sales Order ${salesOrder.id}</strong> requires items currently not available in stock. The system has analyzed the shortages and computed replenishment routing rules.
          </div>
        </div>

        <h4 style="font-size:13px; font-weight:700; margin-bottom:12px;">Shortage & Procurement Routing Advice:</h4>
        <div style="display:flex; flex-direction:column; gap:16px;">
          ${shortageData.map(s => `
            <div style="border:1px solid var(--border-color); padding:16px; border-radius:var(--border-radius-md); background-color:var(--bg-secondary);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <strong style="font-size:14px;">${s.productName}</strong>
                <span class="badge badge-mto">Short by ${s.shortage} units</span>
              </div>
              <div class="rec-box" style="margin:4px 0 0 0; padding:10px 14px;">
                <div class="rec-title">
                  <span>✦ Recommendation:</span> ${s.rec.recommendation}
                </div>
                <div class="rec-reason" style="font-size:12px; margin-top:4px;">
                  ${s.rec.reason}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="btn-cancel-proc">Review Order</button>
        <button class="btn btn-primary" id="btn-trigger-proc-confirm">Auto-replenish (Execute Routing)</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-proc-modal").addEventListener("click", closeForm);
  modal.querySelector("#btn-cancel-proc").addEventListener("click", closeForm);

  modal.querySelector("#btn-trigger-proc-confirm").addEventListener("click", () => {
    triggerMTOProcurement(salesOrder, shortages);
    closeForm();
    showToastNotification(`Procurement routes executed: check Manufacturing/Purchases logs.`, "success");
  });
}

// Delivery Form Dialog
function openDeliveryDialog(so) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  
  const products = state.getProducts();

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 500px;">
      <div class="modal-header">
        <h3 class="modal-title">Shipment Delivery Validation</h3>
        <button class="modal-close" id="close-deliv-modal">✕</button>
      </div>
      <form id="delivery-validation-form">
        <div class="modal-body">
          <div style="margin-bottom:16px; font-size:13px; color:var(--text-secondary);">
            Verify and input the quantities of products shipped for delivery validation.
          </div>
          
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${so.items.map(item => {
              const product = products.find(p => p.id === item.productId);
              const alreadyDelivered = so.deliveredQtyMap[item.productId] || 0;
              const remaining = item.quantity - alreadyDelivered;
              const maxAvailableToShip = Math.min(remaining, product ? product.onHand : 0);

              return `
                <div style="border:1px solid var(--border-color); padding:12px; border-radius:var(--border-radius-md);">
                  <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span style="font-weight:700;">${item.name}</span>
                    <span style="font-size:12px; color:var(--text-secondary);">Ordered: ${item.quantity} (Pending: ${remaining})</span>
                  </div>
                  <div class="form-grid" style="grid-template-columns: 2fr 1fr; margin-bottom:0; align-items:center;">
                    <div style="font-size:12px; color:var(--text-secondary);">
                      On Hand Stock: <strong style="color:var(--text-primary);">${product ? product.onHand : 0}</strong>
                    </div>
                    <div class="form-group" style="gap:2px;">
                      <label style="font-size:10px;">Ship Quantity</label>
                      <input type="number" class="form-control ship-qty-input" data-prod-id="${item.productId}" min="0" max="${maxAvailableToShip}" value="${maxAvailableToShip}" style="padding:6px; font-weight:700; text-align:center;">
                    </div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-deliv-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Validate Delivery</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-deliv-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-deliv-modal").addEventListener("click", closeForm);

  modal.querySelector("#delivery-validation-form").addEventListener("submit", (e) => {
    e.preventDefault();
    
    const deliveryQuantities = {};
    modal.querySelectorAll(".ship-qty-input").forEach(input => {
      deliveryQuantities[input.dataset.prodId] = parseInt(input.value) || 0;
    });

    state.deliverSalesOrder(so.id, deliveryQuantities);
    closeForm();
    showToastNotification(`Shipment delivery processed.`, "success");
  });
}

// Sales Order Creation Form Modal
function openSalesOrderCreateModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";

  const products = state.getProducts().filter(p => p.salesPrice > 0);

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 650px;">
      <div class="modal-header">
        <h3 class="modal-title">Create Sales Order</h3>
        <button class="modal-close" id="close-so-modal">✕</button>
      </div>
      <form id="so-create-form">
        <div class="modal-body">
          <div class="form-group" style="margin-bottom:16px;">
            <label for="so-customer">Customer Name *</label>
            <input type="text" id="so-customer" class="form-control" required placeholder="Enter customer company name...">
          </div>

          <div style="margin-top:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary);">Order Lines</h4>
              <button type="button" class="btn btn-secondary btn-sm" id="btn-add-so-line">+ Add Line</button>
            </div>
            
            <div class="lines-list">
              <div class="line-header">
                <span>Product</span>
                <span style="text-align:right;">Quantity</span>
                <span style="text-align:right;">Unit Price</span>
                <span></span>
              </div>
              <div id="so-lines-container">
                <!-- Lines render dynamically -->
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-so-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Save Draft</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-so-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-so-modal").addEventListener("click", closeForm);

  const linesContainer = modal.querySelector("#so-lines-container");
  
  // Add a order line
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line-item-row";
    row.innerHTML = `
      <select class="form-control line-product-select" required>
        <option value="" disabled selected>Select product...</option>
        ${products.map(p => `<option value="${p.id}" data-price="${p.salesPrice}">${p.name} (${p.sku})</option>`).join('')}
      </select>
      <input type="number" class="form-control line-qty-input" required min="1" value="1" style="text-align:right;">
      <input type="number" class="form-control line-price-input" required min="0" step="0.01" value="0.00" style="text-align:right;">
      <button type="button" class="line-remove-btn">✕</button>
    `;

    linesContainer.appendChild(row);

    // Bind price lookup
    row.querySelector(".line-product-select").addEventListener("change", (e) => {
      const selectedOption = e.target.options[e.target.selectedIndex];
      const price = parseFloat(selectedOption.dataset.price) || 0;
      row.querySelector(".line-price-input").value = price.toFixed(2);
    });

    row.querySelector(".line-remove-btn").addEventListener("click", () => {
      linesContainer.removeChild(row);
    });
  };

  // Add initial line
  addLine();

  modal.querySelector("#btn-add-so-line").addEventListener("click", addLine);

  modal.querySelector("#so-create-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const customerName = document.getElementById("so-customer").value;
    const items = [];
    let totalAmount = 0;

    modal.querySelectorAll(".line-item-row").forEach(row => {
      const select = row.querySelector(".line-product-select");
      const qty = parseInt(row.querySelector(".line-qty-input").value) || 0;
      const price = parseFloat(row.querySelector(".line-price-input").value) || 0;

      if (select.value && qty > 0) {
        items.push({
          productId: select.value,
          name: select.options[select.selectedIndex].text.split(' (')[0],
          quantity: qty,
          unitPrice: price
        });
        totalAmount += qty * price;
      }
    });

    if (items.length === 0) {
      alert("Please add at least one order line.");
      return;
    }

    state.addSalesOrder({
      customerName,
      items,
      totalAmount
    });

    closeForm();
    showToastNotification("Sales Order Draft saved.", "success");
  });
}
