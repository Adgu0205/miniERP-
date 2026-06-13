import { state } from '../state.js';
import { getRolePermissions } from './auth.js';
import { showToastNotification } from '../app.js';

export function renderBom() {
  const container = document.createElement("div");
  container.className = "bom-panel";

  const activeRole = state.getRole();
  const permissions = getRolePermissions(activeRole);
  const boms = state.getBoms();

  container.innerHTML = `
    <div class="panel-header" style="background-color:var(--bg-primary); border:1px solid var(--border-color); border-radius:var(--border-radius-lg); padding:20px 24px; margin-bottom:24px; box-shadow:var(--shadow-sm); display:flex; justify-content:space-between; align-items:center;">
      <h3 class="panel-title">Bill of Materials (BoMs)</h3>
      ${permissions.canEditBom && !permissions.isReadOnly ? `
        <button class="btn btn-primary btn-sm" id="btn-open-create-bom-modal">+ Create BoM Recipe</button>
      ` : ''}
    </div>

    <!-- BoMs card grid -->
    <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:24px;">
      ${boms.map(bom => `
        <div class="card-panel" style="margin-bottom:0; height:100%;">
          <div class="panel-header" style="border-bottom:1px solid var(--border-color); padding-bottom:12px; margin-bottom:16px;">
            <h4 class="panel-title" style="font-size:16px; color:var(--text-primary);">${bom.name}</h4>
            <span class="badge badge-mto" style="font-size:11px;">Active Recipe</span>
          </div>

          <div style="margin-bottom:20px;">
            <h5 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">1. Required Components</h5>
            <div class="lines-list" style="margin-top:0;">
              <div class="line-header" style="grid-template-columns: 2fr 1fr; border:none; padding:6px 12px; background-color:var(--bg-secondary);">
                <span>Component Name</span>
                <span style="text-align:right;">Quantity</span>
              </div>
              ${bom.components.map(c => `
                <div class="line-item-row" style="grid-template-columns: 2fr 1fr; padding:8px 12px;">
                  <span style="font-weight:600;">${c.name}</span>
                  <span style="text-align:right; font-weight:700;">${c.quantity} units</span>
                </div>
              `).join('')}
            </div>
          </div>

          <div>
            <h5 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">2. Operation Routing Steps</h5>
            <div class="timeline" style="padding-left:16px;">
              ${bom.operations.map(op => `
                <div class="timeline-item" style="padding-bottom:12px;">
                  <div class="timeline-dot green" style="top:2px; width:8px; height:8px; left:-16px;"></div>
                  <div class="timeline-content" style="font-size:13px;">
                    <strong style="color:var(--text-primary);">${op.name}</strong> at 
                    <span style="color:var(--accent-hover); font-weight:600;">${op.workCenter}</span> 
                    <span style="color:var(--text-muted); font-size:11px;">(${op.duration} mins)</span>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;

  // Bind Actions
  setTimeout(() => {
    if (permissions.canEditBom && !permissions.isReadOnly) {
      container.querySelector("#btn-open-create-bom-modal").addEventListener("click", () => {
        openBomCreateModal();
      });
    }
  }, 30);

  return container;
}

// BoM Recipe Creation Modal Form
function openBomCreateModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";

  const productsWithoutBoms = state.getProducts().filter(p => !p.bomId && p.category === 'Furniture');
  const components = state.getProducts().filter(p => p.category === 'Components');

  modal.innerHTML = `
    <div class="modal-content" style="max-width: 720px;">
      <div class="modal-header">
        <h3 class="modal-title">Create Manufacturing Recipe (BoM)</h3>
        <button class="modal-close" id="close-bom-modal">✕</button>
      </div>
      <form id="bom-create-form">
        <div class="modal-body" style="max-height:60vh; overflow-y:auto;">
          
          <div class="form-group" style="margin-bottom:16px;">
            <label for="bom-product">Finished Product Link *</label>
            <select id="bom-product" class="form-control" required>
              <option value="" disabled selected>Select finished furniture product...</option>
              ${productsWithoutBoms.map(p => `<option value="${p.id}">${p.name} (${p.sku})</option>`).join('')}
              ${productsWithoutBoms.length === 0 ? `<option value="" disabled>No recipe-free finished goods available</option>` : ''}
            </select>
          </div>

          <!-- Ingredients section -->
          <div style="margin-top:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary);">1. Components & Quantities</h4>
              <button type="button" class="btn btn-secondary btn-sm" id="btn-add-bom-component">+ Add Component</button>
            </div>
            <div class="lines-list">
              <div class="line-header" style="grid-template-columns: 2fr 1fr 40px;">
                <span>Component Name</span>
                <span style="text-align:right;">Quantity Per Finished Unit</span>
                <span></span>
              </div>
              <div id="bom-components-container">
                <!-- Rows render dynamically -->
              </div>
            </div>
          </div>

          <!-- Operations section -->
          <div style="margin-top:24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h4 style="font-size:12px; text-transform:uppercase; color:var(--text-secondary);">2. Operation Routing Steps</h4>
              <button type="button" class="btn btn-secondary btn-sm" id="btn-add-bom-operation">+ Add Operation</button>
            </div>
            <div class="lines-list">
              <div class="line-header" style="grid-template-columns: 1.5fr 1.5fr 1fr 40px;">
                <span>Operation</span>
                <span>Work Center</span>
                <span style="text-align:right;">Duration (Mins)</span>
                <span></span>
              </div>
              <div id="bom-operations-container">
                <!-- Rows render dynamically -->
              </div>
            </div>
          </div>

        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" id="cancel-bom-modal">Cancel</button>
          <button type="submit" class="btn btn-primary">Save BoM Recipe</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(modal);

  const closeForm = () => {
    document.body.removeChild(modal);
  };

  modal.querySelector("#close-bom-modal").addEventListener("click", closeForm);
  modal.querySelector("#cancel-bom-modal").addEventListener("click", closeForm);

  const compsContainer = modal.querySelector("#bom-components-container");
  const opsContainer = modal.querySelector("#bom-operations-container");

  // Add Component Row helper
  const addComponentRow = () => {
    const row = document.createElement("div");
    row.className = "line-item-row";
    row.style.gridTemplateColumns = "2fr 1fr 40px";
    row.innerHTML = `
      <select class="form-control comp-select" required>
        <option value="" disabled selected>Select component...</option>
        ${components.map(c => `<option value="${c.id}">${c.name} (${c.sku})</option>`).join('')}
      </select>
      <input type="number" class="form-control comp-qty" required min="1" value="1" style="text-align:right;">
      <button type="button" class="line-remove-btn">✕</button>
    `;
    compsContainer.appendChild(row);
    row.querySelector(".line-remove-btn").addEventListener("click", () => compsContainer.removeChild(row));
  };

  // Add Operation Row helper
  const addOperationRow = () => {
    const row = document.createElement("div");
    row.className = "line-item-row";
    row.style.gridTemplateColumns = "1.5fr 1.5fr 1fr 40px";
    row.innerHTML = `
      <input type="text" class="form-control op-name" placeholder="Assembly, Painting..." required>
      <select class="form-control op-wc" required>
        <option value="Assembly Line">Assembly Line</option>
        <option value="Painting Station">Painting Station</option>
        <option value="Packaging Unit">Packaging Unit</option>
      </select>
      <input type="number" class="form-control op-dur" required min="1" value="30" style="text-align:right;">
      <button type="button" class="line-remove-btn">✕</button>
    `;
    opsContainer.appendChild(row);
    row.querySelector(".line-remove-btn").addEventListener("click", () => opsContainer.removeChild(row));
  };

  // Seed initial values
  addComponentRow();
  addOperationRow();

  modal.querySelector("#btn-add-bom-component").addEventListener("click", addComponentRow);
  modal.querySelector("#btn-add-bom-operation").addEventListener("click", addOperationRow);

  modal.querySelector("#bom-create-form").addEventListener("submit", (e) => {
    e.preventDefault();

    const productSelect = document.getElementById("bom-product");
    const productId = productSelect.value;
    const productName = productSelect.options[productSelect.selectedIndex].text.split(' (')[0];

    const comps = [];
    modal.querySelectorAll("#bom-components-container .line-item-row").forEach(row => {
      const select = row.querySelector(".comp-select");
      const qty = parseInt(row.querySelector(".comp-qty").value) || 0;
      if (select.value && qty > 0) {
        comps.push({
          productId: select.value,
          name: select.options[select.selectedIndex].text.split(' (')[0],
          quantity: qty
        });
      }
    });

    const ops = [];
    modal.querySelectorAll("#bom-operations-container .line-item-row").forEach(row => {
      const name = row.querySelector(".op-name").value;
      const wc = row.querySelector(".op-wc").value;
      const dur = parseInt(row.querySelector(".op-dur").value) || 0;
      if (name && dur > 0) {
        ops.push({ name, workCenter: wc, duration: dur });
      }
    });

    if (comps.length === 0 || ops.length === 0) {
      alert("Please add at least one component and one operation step.");
      return;
    }

    state.addBom({
      name: `Bill of Materials - ${productName}`,
      productId,
      productName,
      components: comps,
      operations: ops
    });

    closeForm();
    showToastNotification("New Bill of Materials recipe created.", "success");
  });
}
