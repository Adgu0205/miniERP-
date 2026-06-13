import { state } from './state.js';
import { runMTSReorderingRules } from './procurement.js';
import { hasPageAccess, renderNoAccessScreen } from './ui/auth.js';

// Import UI module renderers
import { renderDashboard } from './ui/dashboard.js';
import { renderProducts } from './ui/products.js';
import { renderSales } from './ui/sales.js';
import { renderPurchase } from './ui/purchase.js';
import { renderManufacturing } from './ui/manufacturing.js';
import { renderBom } from './ui/bom.js';
import { renderInventory } from './ui/inventory.js';
import { renderLedger } from './ui/ledger.js';
import { renderAudit } from './ui/audit.js';

// Route dictionary matching hash strings to render functions
const ROUTES = {
  dashboard: { render: renderDashboard, title: "Executive Dashboard" },
  products: { render: renderProducts, title: "Product Catalog" },
  sales: { render: renderSales, title: "Sales Orders" },
  purchase: { render: renderPurchase, title: "Purchase Orders" },
  manufacturing: { render: renderManufacturing, title: "Manufacturing Desk" },
  bom: { render: renderBom, title: "Bills of Material" },
  inventory: { render: renderInventory, title: "Inventory Control" },
  ledger: { render: renderLedger, title: "Stock Valuation Ledger" },
  audit: { render: renderAudit, title: "Audit Trail Center" }
};

class AppController {
  constructor() {
    this.appRoot = document.getElementById("app-root");
    this.pageTitle = document.getElementById("page-main-title");
    this.roleSelect = document.getElementById("role-select");
    this.notificationBell = document.getElementById("notification-bell-btn");
    this.unreadDot = document.getElementById("notification-unread-dot");
    this.currentPage = "dashboard";

    this.init();
  }

  init() {
    // 1. Initial State Sync
    this.updateUserInterfaceDetails();

    // 2. Bind Hash Navigation listener
    window.addEventListener("hashchange", () => this.handleNavigation());

    // 3. Bind Role Selector listener
    this.roleSelect.value = state.getRole();
    this.roleSelect.addEventListener("change", (e) => {
      state.setRole(e.target.value);
    });

    // 4. Bind Notification center click
    this.notificationBell.addEventListener("click", () => this.openNotificationsDrawer());

    // 5. Subscribe to State Changes (re-render current page reactively)
    state.subscribe(() => {
      this.updateUserInterfaceDetails();
      this.refreshCurrentPage();
    });

    // 6. Navigate to initial page
    this.handleNavigation();

    // 7. Initial check of MTS rules on startup
    runMTSReorderingRules();

    this.showToast("Mini ERP System Initialized", "success");
  }

  updateUserInterfaceDetails() {
    // Update user profile letters and display name in sidebar
    const currentUser = state.db.currentUser;
    document.getElementById("avatar-letters").innerText = currentUser.letters;
    document.getElementById("user-display-name").innerText = currentUser.name;
    
    // Beautify display role
    const formattedRole = currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1).replace('_', ' ');
    document.getElementById("user-display-role").innerText = formattedRole;

    // Check notification badge dot
    const unreadCount = state.getNotifications().filter(n => !n.read).length;
    if (unreadCount > 0) {
      this.unreadDot.style.display = "block";
    } else {
      this.unreadDot.style.display = "none";
    }
  }

  handleNavigation() {
    const hash = window.location.hash.substring(1) || "dashboard";
    this.currentPage = ROUTES[hash] ? hash : "dashboard";

    // Update active state in sidebar menu lists
    document.querySelectorAll(".sidebar-menu-item").forEach(item => {
      if (item.dataset.page === this.currentPage) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    this.refreshCurrentPage();
  }

  refreshCurrentPage() {
    const route = ROUTES[this.currentPage];
    if (!route) return;

    // Set page header title
    this.pageTitle.innerText = route.title;

    // Check Role-Based Access Control
    const activeRole = state.getRole();
    if (!hasPageAccess(activeRole, this.currentPage)) {
      this.appRoot.innerHTML = "";
      this.appRoot.appendChild(renderNoAccessScreen(this.currentPage));
      return;
    }

    // Render page content
    this.appRoot.innerHTML = "";
    const content = route.render();
    if (content) {
      this.appRoot.appendChild(content);
    }
  }

  // Visual Drawer displaying Notification feeds
  openNotificationsDrawer() {
    state.markNotificationsAsRead();
    
    const drawer = document.createElement("div");
    drawer.className = "drawer-overlay";
    drawer.innerHTML = `
      <div class="drawer-content" style="width: 420px;">
        <div class="drawer-header">
          <h2 class="drawer-title">Activity Notification Logs</h2>
          <button class="modal-close" id="close-notif-drawer">✕</button>
        </div>
        <div class="drawer-body">
          <div class="timeline" id="notifications-timeline-list">
            ${state.getNotifications().length === 0 ? '<p style="color: var(--text-secondary); text-align: center; margin-top: 40px;">No alerts posted yet.</p>' : ''}
            ${state.getNotifications().map(n => `
              <div class="timeline-item">
                <div class="timeline-dot ${!n.read ? 'green' : ''}"></div>
                <div class="timeline-time">${new Date(n.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                <div class="timeline-content">${n.message}</div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(drawer);

    const closeBtn = drawer.querySelector("#close-notif-drawer");
    const closeDrawer = () => {
      document.body.removeChild(drawer);
    };
    
    closeBtn.addEventListener("click", closeDrawer);
    drawer.addEventListener("click", (e) => {
      if (e.target === drawer) closeDrawer();
    });
  }

  // Toast Notification service
  showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span>${message}</span>
      <button class="toast-close">✕</button>
    `;

    container.appendChild(toast);

    const removeToast = () => {
      if (container.contains(toast)) {
        toast.style.animation = "toastEnter 0.2s reverse ease";
        setTimeout(() => {
          if (container.contains(toast)) container.removeChild(toast);
        }, 180);
      }
    };

    toast.querySelector(".toast-close").addEventListener("click", removeToast);
    
    // Auto-remove after 4 seconds
    setTimeout(removeToast, 4000);
  }
}

// Instantiate App
let appInstance;
document.addEventListener("DOMContentLoaded", () => {
  appInstance = new AppController();
});

// Export a global toast function for pages
export function showToastNotification(message, type) {
  if (appInstance) {
    appInstance.showToast(message, type);
  }
}
