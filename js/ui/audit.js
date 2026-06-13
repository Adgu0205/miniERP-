import { state } from '../state.js';

export function renderAudit() {
  const container = document.createElement("div");
  container.className = "audit-panel card-panel";

  const logs = state.getAuditLogs();

  container.innerHTML = `
    <div class="panel-header">
      <h3 class="panel-title">Audit Log Trail & Tracking</h3>
      <div style="display:flex; gap:12px;">
        <input type="text" id="search-audit-input" placeholder="Search logs..." class="form-control" style="width:280px; padding: 6px 12px; font-size:13px;">
        <select id="filter-audit-module" class="form-control" style="width:160px; padding: 6px 12px; font-size:13px;">
          <option value="">All Modules</option>
          <option value="System">System/Security</option>
          <option value="Sales">Sales Module</option>
          <option value="Purchase">Purchase Module</option>
          <option value="Manufacturing">Manufacturing</option>
          <option value="Inventory">Inventory</option>
          <option value="Product">Product Catalog</option>
        </select>
      </div>
    </div>

    <div class="table-responsive">
      <table class="erp-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Module</th>
            <th>Event Action</th>
            <th>Description / Details</th>
            <th>User/Employee</th>
          </tr>
        </thead>
        <tbody id="audit-table-body">
          ${logs.map(log => `
            <tr data-search="${log.module.toLowerCase()} ${log.action.toLowerCase()} ${log.details.toLowerCase()}">
              <td style="color:var(--text-muted); font-size:12px; width:180px;">${new Date(log.timestamp).toLocaleString()}</td>
              <td style="width:130px;">
                <span class="badge" style="background-color:var(--bg-tertiary); color:var(--text-primary); border-radius:4px; font-size:11px;">
                  ${log.module}
                </span>
              </td>
              <td style="font-weight:700; width:150px;">${log.action}</td>
              <td style="color:var(--text-secondary);">${log.details}</td>
              <td style="font-size:13px; font-weight:600; width:140px;">${log.user}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${logs.length === 0 ? '<p style="text-align:center; color:var(--text-muted); margin-top:20px;">No audit trace captured yet.</p>' : ''}
    </div>
  `;

  // Bind Actions
  setTimeout(() => {
    const searchInput = container.querySelector("#search-audit-input");
    const moduleSelect = container.querySelector("#filter-audit-module");

    const filterLogs = () => {
      const query = searchInput.value.toLowerCase();
      const modFilter = moduleSelect.value.toLowerCase();

      container.querySelectorAll("#audit-table-body tr").forEach(row => {
        const textMatch = row.dataset.search.includes(query);
        const modMatch = !modFilter || row.dataset.search.includes(modFilter);

        if (textMatch && modMatch) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    };

    searchInput.addEventListener("input", filterLogs);
    moduleSelect.addEventListener("change", filterLogs);
  }, 30);

  return container;
}
