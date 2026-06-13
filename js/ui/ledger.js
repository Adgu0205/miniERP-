import { state } from '../state.js';

export function renderLedger() {
  const container = document.createElement("div");
  container.className = "ledger-panel card-panel";

  const ledger = state.getStockLedger();

  container.innerHTML = `
    <div class="panel-header">
      <h3 class="panel-title">Stock Movement Journal Logs</h3>
      <div style="display:flex; gap:12px;">
        <input type="text" id="search-ledger-input" placeholder="Search by SKU, product or ref..." class="form-control" style="width:280px; padding: 6px 12px; font-size:13px;">
        <select id="filter-ledger-type" class="form-control" style="width:180px; padding: 6px 12px; font-size:13px;">
          <option value="">All Movements</option>
          <option value="Sales Delivery">Sales Delivery</option>
          <option value="Purchase Receipt">Purchase Receipt</option>
          <option value="Manufacturing Consumption">Manufacturing Consumption</option>
          <option value="Manufacturing Production">Manufacturing Production</option>
          <option value="Manual Adjustment">Manual Adjustment</option>
        </select>
      </div>
    </div>

    <div class="table-responsive">
      <table class="erp-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Product Name</th>
            <th>Movement Route</th>
            <th style="text-align:center;">Quantity Shift</th>
            <th>Source Document</th>
            <th>Operator</th>
          </tr>
        </thead>
        <tbody id="ledger-table-body">
          ${ledger.map(entry => {
            const isNegative = entry.quantityChange < 0;
            const formattedQty = `${isNegative ? '' : '+'}${entry.quantityChange}`;
            const color = isNegative ? '#ef4444' : 'var(--accent-hover)';
            const bg = isNegative ? '#fee2e2' : 'var(--accent-light)';

            return `
              <tr data-search="${entry.productName.toLowerCase()} ${entry.movementType.toLowerCase()} ${entry.sourceDocument.toLowerCase()}">
                <td style="color:var(--text-muted); font-size:13px;">${new Date(entry.timestamp).toLocaleString()}</td>
                <td style="font-weight:600;">${entry.productName}</td>
                <td>
                  <span class="badge" style="background-color:var(--bg-tertiary); color:var(--text-primary); border-radius:4px; font-size:11px;">
                    ${entry.movementType}
                  </span>
                </td>
                <td style="text-align:center;">
                  <span style="font-weight:700; color:${color}; background-color:${bg}; padding:4px 10px; border-radius:12px; font-size:13px; display:inline-block; min-width:50px;">
                    ${formattedQty}
                  </span>
                </td>
                <td style="font-weight:600; font-size:13px; color:var(--text-secondary);">${entry.sourceDocument}</td>
                <td style="font-size:13px; font-weight:500;">${entry.user}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
      ${ledger.length === 0 ? '<p style="text-align:center; color:var(--text-muted); margin-top:20px;">No stock ledger entries registered.</p>' : ''}
    </div>
  `;

  // Bind Actions
  setTimeout(() => {
    const searchInput = container.querySelector("#search-ledger-input");
    const filterSelect = container.querySelector("#filter-ledger-type");

    const filterRows = () => {
      const query = searchInput.value.toLowerCase();
      const typeFilter = filterSelect.value.toLowerCase();

      container.querySelectorAll("#ledger-table-body tr").forEach(row => {
        const textMatch = row.dataset.search.includes(query);
        const typeMatch = !typeFilter || row.dataset.search.includes(typeFilter);

        if (textMatch && typeMatch) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    };

    searchInput.addEventListener("input", filterRows);
    filterSelect.addEventListener("change", filterRows);
  }, 30);

  return container;
}
