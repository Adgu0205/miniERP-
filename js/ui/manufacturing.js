import { state } from '../state.js';
import { getRolePermissions } from './auth.js';
import { showToastNotification } from '../app.js';

// Timer Registry to handle live tick updates for running work orders
const activeTimers = {};

export function renderManufacturing() {
  const container = document.createElement("div");
  container.className = "manufacturing-workspace";

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const manufacturingOrders = state.getManufacturingOrders();

  // Create side-by-side grid split
  container.style.display = "grid";
  container.style.gridTemplateColumns = "1.2fr 1.8fr";
  container.style.gap = "24px";
  container.style.alignItems = "start";

  // HTML Structure
  container.innerHTML = `
    <!-- Left Panel: MO List -->
    <div class="card-panel" style="margin-bottom: 0;">
      <div class="panel-header">
        <h3 class="panel-title">Manufacturing Queue</h3>
        ${permissions.canEditManufacturing && !permissions.isReadOnly ? `
          <button class="btn btn-primary btn-sm" id="btn-open-create-mo-modal">+ Create MO</button>
        ` : ''}
      </div>
      <div class="table-responsive">
        <table class="erp-table">
          <thead>
            <tr>
              <th>MO Ref</th>
              <th>Product</th>
              <th style="text-align:center;">Qty</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="mo-list-tbody">
            ${manufacturingOrders.map(mo => `
              <tr class="mo-row" data-id="${mo.id}" style="cursor:pointer;">
                <td style="font-weight:700;">${mo.id}</td>
                <td style="font-weight:600;">${mo.productName}</td>
                <td style="text-align:center;">${mo.quantity}</td>
                <td>
                  <span class="badge badge-${mo.status === 'completed' ? 'received' : mo.status === 'confirmed' ? 'confirmed' : mo.status === 'in_progress' ? 'progress' : mo.status === 'quality_check' ? 'partial' : 'draft'}">
                    ${mo.status.replace('_', ' ')}
                  </span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Right Panel: MO Details / Live Cockpit -->
    <div class="card-panel" id="mo-details-panel" style="margin-bottom: 0; min-height: 500px;">
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--text-secondary); text-align:center; padding: 100px 20px;">
        <svg fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="width:48px; height:48px; color:var(--text-muted); margin-bottom:12px;">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
        </svg>
        <h3 style="font-weight:600; font-size:16px;">MO Detail Cockpit</h3>
        <p style="font-size:13px; max-width:280px; margin-top:4px;">Select a manufacturing order from the queue to view operations, raw material reservations, and complete steps.</p>
      </div>
    </div>
  `;

  // Bind side-by-side click triggers
  setTimeout(() => {
    if (permissions.canEditManufacturing && !permissions.isReadOnly) {
      container.querySelector("#btn-open-create-mo-modal").addEventListener("click", () => {
        openManufacturingCreateModal();
      });
    }

    container.querySelectorAll("#mo-list-tbody tr").forEach(row => {
      row.addEventListener("click", () => {
        // Clear active styles
        container.querySelectorAll("#mo-list-tbody tr").forEach(r => r.style.backgroundColor = "");
        row.style.backgroundColor = "var(--bg-secondary)";
        
        loadMoDetailsCockpit(row.dataset.id, container.querySelector("#mo-details-panel"));
      });
    });

    // Automatically load first MO if list is not empty
    const firstRow = container.querySelector("#mo-list-tbody tr");
    if (firstRow) {
      firstRow.click();
    }
  }, 30);

  return container;
}

// Cockpit Detail Loader
function loadMoDetailsCockpit(moId, detailPanelEl) {
  const mo = state.getManufacturingOrders().find(m => m.id === moId);
  if (!mo) return;

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const bom = state.getBoms().find(b => b.id === mo.bomId);
  const products = state.getProducts();

  // Components Reservation Status
  let reservationRows = '';
  let allComponentsAvailable = true;

  if (bom) {
    reservationRows = bom.components.map(comp => {
      const compProd = products.find(p => p.id === comp.productId);
      if (!compProd) return '';

      const totalNeeded = comp.quantity * mo.quantity;
      const isReserved = mo.status !== 'draft';
      // If reserved, show what was locked. If draft, check what can be locked.
      const currentReservedForMo = isReserved ? Math.min(totalNeeded, compProd.reserved) : 0;
      
      const deficit = totalNeeded - compProd.freeToUse;
      const shortageState = deficit > 0;
      if (shortageState) allComponentsAvailable = false;

      return `
        <tr style="font-size:13px;">
          <td style="font-weight:600; padding:10px 12px;">${comp.name}</td>
          <td style="text-align:center; padding:10px 12px;">${comp.quantity} unit</td>
          <td style="text-align:center; font-weight:700; padding:10px 12px;">${totalNeeded}</td>
          <td style="text-align:center; padding:10px 12px; font-weight:600; color:${shortageState ? '#d97706' : 'var(--accent-hover)'};">
            ${isReserved ? `${totalNeeded} / ${totalNeeded}` : `${Math.min(totalNeeded, compProd.freeToUse)} / ${totalNeeded}`}
          </td>
          <td style="text-align:center; padding:10px 12px; font-weight:700; color:${compProd.onHand < totalNeeded ? '#ef4444' : 'var(--text-primary)'}">
            ${compProd.onHand}
          </td>
          <td style="padding:10px 12px;">
            <span class="badge ${shortageState ? 'badge-cancelled' : 'badge-completed'}" style="padding: 2px 6px; font-size:10px;">
              ${shortageState ? 'Shortage' : 'Available'}
            </span>
          </td>
        </tr>
      `;
    }).join('');
  }

  detailPanelEl.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:16px; margin-bottom:20px;">
      <div>
        <h3 class="panel-title" style="display:flex; align-items:center; gap:8px;">
          <span>${mo.id} Cockpit</span>
          <span class="badge badge-${mo.status === 'completed' ? 'received' : mo.status === 'confirmed' ? 'confirmed' : mo.status === 'in_progress' ? 'progress' : mo.status === 'quality_check' ? 'partial' : 'draft'}">
            ${mo.status.replace('_', ' ')}
          </span>
        </h3>
        <span style="font-size:12px; color:var(--text-muted);">Assigned to: <strong>${mo.assignee}</strong> | Created: ${new Date(mo.date).toLocaleDateString()}</span>
      </div>
      
      <div>
        ${mo.status === 'draft' && permissions.canEditManufacturing && !permissions.isReadOnly ? `
          <button class="btn btn-primary btn-sm" id="btn-cockpit-confirm-mo">Confirm Production</button>
        ` : ''}

        ${mo.status === 'quality_check' && permissions.canEditManufacturing && !permissions.isReadOnly ? `
          <button class="btn btn-primary btn-sm" id="btn-cockpit-complete-mo">Pass QC & Finish MO</button>
        ` : ''}

        ${['confirmed', 'in_progress'].includes(mo.status) && permissions.canEditManufacturing && !permissions.isReadOnly ? `
          <button class="btn btn-danger btn-sm" id="btn-cockpit-force-finish-mo" style="padding:4px 8px; font-size:11px;">Force Complete</button>
        ` : ''}
      </div>
    </div>

    <!-- Components stock section -->
    <div style="margin-bottom:24px;">
      <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">Components Reservation Logs</h4>
      <div class="table-responsive" style="border: 1px solid var(--border-color); border-radius: var(--border-radius-md); overflow:hidden;">
        <table class="erp-table" style="background-color: var(--bg-secondary);">
          <thead>
            <tr style="font-size:11px; text-transform:uppercase; background-color:var(--bg-tertiary);">
              <th style="padding:8px 12px;">Component</th>
              <th style="text-align:center; padding:8px 12px;">Unit/Unit</th>
              <th style="text-align:center; padding:8px 12px;">Total Req</th>
              <th style="text-align:center; padding:8px 12px;">Reserved</th>
              <th style="text-align:center; padding:8px 12px;">On Hand</th>
              <th style="padding:8px 12px;">Stock Status</th>
            </tr>
          </thead>
          <tbody>
            ${reservationRows || '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No BOM linked.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Interactive Work Orders list -->
    <div>
      <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">Work Centers & Operational Tasks</h4>
      <div class="wo-card-grid">
        ${mo.workOrders.map((wo, index) => {
          const formattedTime = formatTimerValue(wo.elapsedSeconds);
          const isPlayable = ['confirmed', 'in_progress'].includes(mo.status) && 
            (index === 0 || mo.workOrders[index - 1].status === 'completed');

          return `
            <div class="wo-card ${wo.status === 'completed' ? 'completed' : wo.status === 'active' ? 'active' : ''}" data-wo-id="${wo.id}">
              <div class="wo-header">
                <span class="badge" style="font-size:9px; font-weight:700; padding:2px 6px; background-color:rgba(0,0,0,0.05);">${wo.workCenter}</span>
                <span class="badge badge-${wo.status === 'completed' ? 'received' : wo.status === 'active' ? 'progress' : 'draft'}" style="font-size:9px;">
                  ${wo.status}
                </span>
              </div>
              <div class="wo-title" style="margin-top:4px;">${wo.name}</div>
              <div class="wo-timer" id="timer-${wo.id}">${formattedTime}</div>
              
              <div style="margin-top:8px; display:flex; gap:6px;">
                ${permissions.canEditManufacturing && !permissions.isReadOnly && isPlayable && wo.status === 'pending' ? `
                  <button class="btn btn-secondary btn-sm start-wo-btn" data-mo="${mo.id}" data-wo="${wo.id}" style="width:100%; padding:4px 8px; font-size:11px;">Start</button>
                ` : ''}

                ${permissions.canEditManufacturing && !permissions.isReadOnly && isPlayable && wo.status === 'active' ? `
                  <button class="btn btn-primary btn-sm complete-wo-btn" data-mo="${mo.id}" data-wo="${wo.id}" style="width:100%; padding:4px 8px; font-size:11px;">Complete</button>
                ` : ''}
              </div>
            </div>
          `;
        }).join('')}
      </div>
      <div style="font-size:11px; color:var(--text-muted); text-align:center; margin-top:8px;">
        <em>Operators must complete Assembly prior to commencing Paint and final Packing workflows.</em>
      </div>
    </div>
  `;

  // Bind Actions
  if (permissions.canEditManufacturing && !permissions.isReadOnly) {
    // Confirm MO
    const confirmBtn = detailPanelEl.querySelector("#btn-cockpit-confirm-mo");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", () => {
        state.confirmManufacturingOrder(mo.id);
        showToastNotification(`Manufacturing Order ${mo.id} confirmed. Materials reserved.`, "success");
      });
    }

    // Force Complete MO
    const forceBtn = detailPanelEl.querySelector("#btn-cockpit-force-finish-mo");
    if (forceBtn) {
      forceBtn.addEventListener("click", () => {
        state.completeManufacturingOrder(mo.id);
        showToastNotification(`Manufacturing completed manually. Finished goods added to stock.`, "success");
      });
    }

    // Finalize MO from QC
    const completeBtn = detailPanelEl.querySelector("#btn-cockpit-complete-mo");
    if (completeBtn) {
      completeBtn.addEventListener("click", () => {
        state.completeManufacturingOrder(mo.id);
        showToastNotification(`QC Completed: items placed in stock.`, "success");
      });
    }

    // Start Work Order Timer
    detailPanelEl.querySelectorAll(".start-wo-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const woId = e.target.dataset.wo;
        state.updateWorkOrderStatus(mo.id, woId, "active");
        
        // Initialize local counter
        if (!activeTimers[woId]) {
          activeTimers[woId] = setInterval(() => {
            const woObject = mo.workOrders.find(w => w.id === woId);
            if (woObject && woObject.status === "active") {
              woObject.elapsedSeconds++;
              const el = document.getElementById(`timer-${woId}`);
              if (el) {
                el.innerText = formatTimerValue(woObject.elapsedSeconds);
              }
            }
          }, 1000);
        }
      });
    });

    // Complete Work Order Timer
    detailPanelEl.querySelectorAll(".complete-wo-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const woId = e.target.dataset.wo;
        
        // Stop timer registry
        if (activeTimers[woId]) {
          clearInterval(activeTimers[woId]);
          delete activeTimers[woId];
        }

        state.updateWorkOrderStatus(mo.id, woId, "completed");
        showToastNotification(`Work Order completed successfully.`, "success");
      });
    });
  }
}

// Timer helper: returns MM:SS
function formatTimerValue(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${m}:${s}`;
}

// MO creation Modal Form
function openManufacturingCreateModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";

  const productsWithBoms = state.getProducts().filter(p => p.bomId);
  const boms = state.getBoms();

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 550px;">
      <div class="modal-header">
        <h3 class="modal-title">Create Manufacturing Order</h3>
        <button class="modal-close" id="close-mo-modal">✕</button>
      </div>
      <form id="mo-create-form">
        <div class="modal-body">
          <div class="form-group" style="margin-bottom:16px;">
            <label for="mo-product">Finished Product *</label>
            <select id="mo-product" class="form-control" required>
              <option value="" disabled selected>Select recipe-linked product...</option>
              ${productsWithBoms.map(p => {
                const bom = boms.find(b => b.id === p.bomId);
                return `<option value="${p.id}" data-bom="${p.bomId}">${p.name} (Recipe: ${bom ? bom.name : 'BoM'})</option>`;
              }).join('')}
            </select>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label for="mo-qty">Production Quantity *</label>
              <input type="number" id="mo-qty" class="form-control" min="1" value="5" required>
            </div>
            <div class="form-group">
              <label for="mo-assignee">Assign Floor Operator</label>
              <input type="text" id="mo-assignee" class="form-control" placeholder="Operator name..." value="John Operative">
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-mo-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Save MO Draft</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-mo-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-mo-modal").addEventListener("click", closeForm);

  modal.querySelector("#mo-create-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const productSelect = document.getElementById("mo-product");
    const productId = productSelect.value;
    const productName = productSelect.options[productSelect.selectedIndex].text.split(' (Recipe:')[0];
    const bomId = productSelect.options[productSelect.selectedIndex].dataset.bom;
    const qty = parseInt(document.getElementById("mo-qty").value) || 0;
    const assignee = document.getElementById("mo-assignee").value;

    state.addManufacturingOrder({
      productId,
      productName,
      quantity: qty,
      bomId,
      assignee
    });

    closeForm();
    showToastNotification("Manufacturing order saved as draft.", "success");
  });
}
