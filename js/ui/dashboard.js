import { state } from '../state.js';
import { runMTSReorderingRules } from '../procurement.js';
import { showToastNotification } from '../app.js';

export function renderDashboard() {
  const container = document.createElement("div");
  container.className = "dashboard-container";

  // Gather stats
  const products = state.getProducts();
  const salesOrders = state.getSalesOrders();
  const purchaseOrders = state.getPurchaseOrders();
  const manufacturingOrders = state.getManufacturingOrders();
  const auditLogs = state.getAuditLogs();

  // Metrics calculations
  const totalSalesVal = salesOrders
    .filter(s => s.status !== 'cancelled')
    .reduce((sum, s) => sum + s.totalAmount, 0);

  const pendingDeliveries = salesOrders.filter(s => ['confirmed', 'partially_delivered'].includes(s.status)).length;
  const activeMfgOrders = manufacturingOrders.filter(m => ['confirmed', 'in_progress', 'quality_check'].includes(m.status)).length;
  const activePurchaseOrders = purchaseOrders.filter(p => ['confirmed', 'partially_received'].includes(p.status)).length;

  const totalInventoryValue = products.reduce((sum, p) => sum + (p.onHand * p.costPrice), 0);
  
  // Shortage items count
  const shortageItems = products.filter(p => p.freeToUse < p.reorderThreshold).length;

  // AI insights generator based on actual DB status
  const insights = [];
  if (shortageItems > 0) {
    const lowItems = products.filter(p => p.freeToUse < p.reorderThreshold).map(p => p.name).slice(0, 2).join(', ');
    insights.push(`⚠️ Stock levels are low for **${lowItems}**. Reordering is recommended.`);
  } else {
    insights.push(`✅ All inventory lines are above the safety thresholds. Material coverage looks stable.`);
  }
  
  const pendingMTOs = manufacturingOrders.filter(mo => mo.sourceDocument && mo.sourceDocument.startsWith('SO-')).length;
  if (pendingMTOs > 0) {
    insights.push(`⚡ MTO engine reports **${pendingMTOs} active custom manufacturing orders** waiting for operations.`);
  }
  
  const rawMatCoverage = products.find(p => p.sku === 'COMP-TOP')?.freeToUse || 0;
  if (rawMatCoverage < 5) {
    insights.push(`🏭 Raw wood tops are critical (${rawMatCoverage} left). Purchase Lead times suggest starting supplier RFQ now.`);
  } else {
    insights.push(`📈 Manufacturing lead time is optimized at **72 mins avg** per operation chain.`);
  }

  container.innerHTML = `
    <!-- Top KPI Grid -->
    <div class="dashboard-grid">
      <div class="kpi-card">
        <div class="kpi-header">
          <span>Gross Revenue</span>
          <div class="kpi-icon-container green-accent">
            <svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="width:16px; height:16px;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
        </div>
        <div class="kpi-val">$${totalSalesVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        <div class="kpi-trend positive">
          <span>↑ 14.8%</span>
          <span style="color:var(--text-muted); font-weight:normal;">vs last month</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <span>Pending Deliveries</span>
          <div class="kpi-icon-container">
            <svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="width:16px; height:16px;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
            </svg>
          </div>
        </div>
        <div class="kpi-val">${pendingDeliveries} Orders</div>
        <div class="kpi-trend ${pendingDeliveries > 2 ? 'negative' : 'positive'}">
          <span>${pendingDeliveries > 2 ? '⚠️ High Queue' : '✓ Normal'}</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <span>Active Production</span>
          <div class="kpi-icon-container">
            <svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="width:16px; height:16px;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>
            </svg>
          </div>
        </div>
        <div class="kpi-val">${activeMfgOrders} MOs</div>
        <div class="kpi-trend positive">
          <span>94.2% efficiency</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <span>Inventory Value</span>
          <div class="kpi-icon-container green-accent">
            <svg fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="width:16px; height:16px;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path>
            </svg>
          </div>
        </div>
        <div class="kpi-val">$${totalInventoryValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        <div class="kpi-trend positive">
          <span>${products.length} product lines</span>
        </div>
      </div>
    </div>

    <!-- Secondary KPI Row (Shortages, Procurement, Logistics alerts) -->
    <div class="dashboard-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 24px;">
      <div class="kpi-card" style="min-height: 100px; padding: 16px 20px;">
        <div class="kpi-header">
          <span>Stock Shortages</span>
        </div>
        <div style="display:flex; align-items:baseline; gap:8px;">
          <div class="kpi-val" style="font-size: 24px; margin-top:4px; color:${shortageItems > 0 ? '#ef4444' : 'var(--text-primary)'}">${shortageItems}</div>
          <span style="font-size:12px; color:var(--text-muted);">products low</span>
        </div>
      </div>
      <div class="kpi-card" style="min-height: 100px; padding: 16px 20px;">
        <div class="kpi-header">
          <span>Replenishment Requests</span>
        </div>
        <div style="display:flex; align-items:baseline; gap:8px;">
          <div class="kpi-val" style="font-size: 24px; margin-top:4px;">${activePurchaseOrders} POs</div>
          <span style="font-size:12px; color:var(--text-muted);">in supplier queue</span>
        </div>
      </div>
      <div class="kpi-card" style="min-height: 100px; padding: 16px 20px;">
        <div class="kpi-header">
          <span>Delayed Deliveries</span>
        </div>
        <div style="display:flex; align-items:baseline; gap:8px;">
          <div class="kpi-val" style="font-size: 24px; margin-top:4px; color:${salesOrders.some(s => s.status === 'confirmed') ? '#f59e0b' : 'var(--text-primary)'}">0</div>
          <span style="font-size:12px; color:var(--text-muted);">critical warnings</span>
        </div>
      </div>
      <div class="kpi-card" style="min-height: 100px; padding: 16px 20px;">
        <div class="kpi-header">
          <span>Operation Efficiency</span>
        </div>
        <div style="display:flex; align-items:baseline; gap:8px;">
          <div class="kpi-val" style="font-size: 24px; margin-top:4px; color:var(--accent-hover);">96.8%</div>
          <span style="font-size:12px; color:var(--text-muted);">uptime</span>
        </div>
      </div>
    </div>

    <!-- Charts Section -->
    <div class="panels-grid">
      <div class="card-panel">
        <div class="panel-header">
          <h3 class="panel-title">Revenue Trends & Inventory Movements</h3>
        </div>
        <div class="chart-wrapper">
          <canvas id="revenueTrendsChart"></canvas>
        </div>
      </div>

      <div class="card-panel">
        <div class="panel-header">
          <h3 class="panel-title">Stock Valuation Breakdowns</h3>
        </div>
        <div class="chart-wrapper">
          <canvas id="stockBreakdownChart"></canvas>
        </div>
      </div>
    </div>

    <!-- AI and Actions Panel -->
    <div class="panels-grid" style="grid-template-columns: 1fr 1fr;">
      <div class="card-panel ai-panel">
        <div class="ai-header">
          <svg fill="currentColor" viewBox="0 0 24 24" style="width:20px; height:20px;">
            <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"></path>
          </svg>
          <span>AI Smart Recommendations Panel</span>
        </div>
        <ul class="ai-insights-list">
          ${insights.map(i => `
            <li>
              <span>✦</span>
              <div>${i.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</div>
            </li>
          `).join('')}
        </ul>
      </div>

      <div class="card-panel">
        <div class="panel-header">
          <h3 class="panel-title">Quick Actions Panel</h3>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:12px; height: 100%; align-content:center;">
          <button class="btn btn-primary" id="btn-create-so">
            <span>+</span> Create Sales Order
          </button>
          <button class="btn btn-secondary" id="btn-trigger-mts">
            <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="width:14px; height:14px; margin-right:4px;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89H18"></path>
            </svg>
            Run MTS Reorder Rules
          </button>
          <button class="btn btn-secondary" id="btn-view-ledger-quick">
            View Ledger logs
          </button>
        </div>
      </div>
    </div>

    <!-- Recent Activities list -->
    <div class="card-panel" style="margin-bottom: 0;">
      <div class="panel-header">
        <h3 class="panel-title">Recent System Activities</h3>
      </div>
      <div class="table-responsive">
        <table class="erp-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Module</th>
              <th>Action</th>
              <th>Description Details</th>
              <th>Employee</th>
            </tr>
          </thead>
          <tbody>
            ${auditLogs.slice(0, 5).map(log => `
              <tr>
                <td style="color:var(--text-muted); font-size:12px;">${new Date(log.timestamp).toLocaleString()}</td>
                <td><span class="badge" style="background-color:var(--bg-tertiary); color:var(--text-primary); border-radius:4px; font-size:11px;">${log.module}</span></td>
                <td style="font-weight:600;">${log.action}</td>
                <td style="color:var(--text-secondary);">${log.details}</td>
                <td style="font-size:13px; font-weight:500;">${log.user}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Bind Quick Actions handlers
  setTimeout(() => {
    // Canvas dimensions might need adjustments, initialize Chart.js graphs
    initDashboardCharts(products, salesOrders);

    container.querySelector("#btn-create-so").addEventListener("click", () => {
      window.location.hash = "#sales";
      // trigger modal show after redirect by setting a flag in sessionStorage or simple delay
      sessionStorage.setItem("trigger_create_so_modal", "true");
    });

    container.querySelector("#btn-trigger-mts").addEventListener("click", () => {
      const triggers = runMTSReorderingRules();
      if (triggers > 0) {
        showToastNotification(`MTS rules scanned: triggered ${triggers} replenishment orders!`, "success");
      } else {
        showToastNotification("MTS rules scanned: all stock levels are safe.", "info");
      }
    });

    container.querySelector("#btn-view-ledger-quick").addEventListener("click", () => {
      window.location.hash = "#ledger";
    });

  }, 50);

  return container;
}

// Chart.js Setup
function initDashboardCharts(products, salesOrders) {
  // Chart 1: Revenue Trends
  const ctxTrends = document.getElementById('revenueTrendsChart');
  if (ctxTrends) {
    // Generate mock revenue points for previous 6 months
    new Chart(ctxTrends, {
      type: 'line',
      data: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
          label: 'Revenue ($)',
          data: [650, 900, 1400, 1100, 1550, 2200],
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.05)',
          tension: 0.4,
          fill: true,
          borderWidth: 3,
          pointBackgroundColor: '#111111',
          pointBorderColor: '#10b981',
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: { grid: { display: false } },
          y: { 
            grid: { borderDash: [5, 5] },
            ticks: { callback: value => '$' + value }
          }
        }
      }
    });
  }

  // Chart 2: Product Stock Level Breakdown
  const ctxStock = document.getElementById('stockBreakdownChart');
  if (ctxStock) {
    // Take top 5 products for visibility
    const displayProducts = products.filter(p => p.salesPrice > 0).slice(0, 5);
    
    new Chart(ctxStock, {
      type: 'bar',
      data: {
        labels: displayProducts.map(p => p.sku),
        datasets: [
          {
            label: 'Free To Use',
            data: displayProducts.map(p => p.freeToUse),
            backgroundColor: '#10b981',
            borderRadius: 6
          },
          {
            label: 'Reserved',
            data: displayProducts.map(p => p.reserved),
            backgroundColor: '#111111',
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { 
            position: 'top',
            labels: { boxWidth: 12, font: { family: 'Outfit' } }
          }
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, grid: { borderDash: [5, 5] } }
        }
      }
    });
  }
}
