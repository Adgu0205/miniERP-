import { state } from './state.js';

/**
 * Smart Procurement Recommendation Engine
 * Analyzes material shortages and suggests optimal replenishment strategies.
 */
export function getProcurementRecommendation(productId, quantityNeeded) {
  const products = state.getProducts();
  const boms = state.getBoms();
  const product = products.find(p => p.id === productId);

  if (!product) return null;

  // Case 1: Product has a Bill of Materials (BoM) - manufacturing is possible
  if (product.bomId) {
    const bom = boms.find(b => b.id === product.bomId);
    if (bom) {
      let missingComponents = [];
      let canManufacture = true;

      bom.components.forEach(comp => {
        const compProduct = products.find(p => p.id === comp.productId);
        if (compProduct) {
          const totalCompNeeded = comp.quantity * quantityNeeded;
          if (compProduct.freeToUse < totalCompNeeded) {
            canManufacture = false;
            missingComponents.push({
              name: compProduct.name,
              sku: compProduct.sku,
              needed: totalCompNeeded,
              available: compProduct.freeToUse,
              deficit: totalCompNeeded - compProduct.freeToUse,
              vendor: compProduct.vendor
            });
          }
        } else {
          canManufacture = false;
        }
      });

      if (canManufacture) {
        return {
          recommendation: "Manufacture",
          reason: `Recommended to **Manufacture** ${quantityNeeded} units of ${product.name}. All required raw materials (${bom.components.map(c => c.name).join(', ')}) are available in free inventory. Operations can begin immediately.`,
          actionCode: "mfg",
          missingComponents: []
        };
      } else {
        // Build reason string for missing components
        const missingDetails = missingComponents.map(c => `${c.name} (Short by ${c.deficit} units)`).join(', ');
        return {
          recommendation: "Purchase Components & Manufacture",
          reason: `Shortage of raw materials detected: ${missingDetails}. Recommended action: **Purchase components** from their respective vendors, then proceed with Manufacturing.`,
          actionCode: "purchase_components",
          missingComponents: missingComponents
        };
      }
    }
  }

  // Case 2: Product has no BoM (raw materials, components, or pure resale items)
  return {
    recommendation: "Purchase",
    reason: `Recommended to **Purchase** ${quantityNeeded} units of ${product.name} from preferred vendor **${product.vendor || 'Unknown Vendor'}**. This is a non-manufactured product with direct vendor procurement routes.`,
    actionCode: "buy",
    missingComponents: []
  };
}

/**
 * Executes Make-To-Order (MTO) procurement chains.
 * Generates purchase or manufacturing orders instantly upon Sales Order confirmation shortages.
 */
export function triggerMTOProcurement(salesOrder, shortages) {
  shortages.forEach(short => {
    const rec = getProcurementRecommendation(short.productId, short.shortage);
    
    state.addAuditLog("Procurement", "MTO Trigger", `MTO triggered for ${short.productName} due to shortage of ${short.shortage} units on ${salesOrder.id}`);

    if (short.procureType === "Manufacturing") {
      // Create MO
      const mo = state.addManufacturingOrder({
        productId: short.productId,
        productName: short.productName,
        quantity: short.shortage,
        bomId: short.bomId,
        assignee: "Auto Procurement",
        sourceDocument: salesOrder.id,
        procurementGroupId: salesOrder.procurementGroupId
      });

      state.addAuditLog("Procurement", "Auto Replenish", `Automatically created Manufacturing Order ${mo.id} for ${short.shortage} units to satisfy ${salesOrder.id}`);
      state.addNotification("procurement_created", `MTO Automation: Created ${mo.id} for ${short.shortage}x ${short.productName} linked to ${salesOrder.id}`);
      
      // Auto-confirm the MO so components are reserved
      state.confirmManufacturingOrder(mo.id);

      // If components are missing, recursively trigger purchase orders for components!
      if (rec && rec.actionCode === "purchase_components") {
        rec.missingComponents.forEach(comp => {
          // Group by vendor to prevent multiple small POs, but for simplicity of hackathon, create a direct PO
          const po = state.addPurchaseOrder({
            vendorName: comp.vendor || "Default Supplier",
            items: [
              { productId: short.productId, name: comp.name, quantity: comp.deficit, unitPrice: 0 } // cost lookup is done dynamically or left as seed
            ],
            totalAmount: 0, // dynamic calculation can be done, or set dynamically
            sourceDocument: mo.id
          });
          
          // Look up component unit price
          const compProd = state.getProducts().find(p => p.id === comp.productId);
          if (compProd) {
            po.items[0].productId = compProd.id;
            po.items[0].unitPrice = compProd.costPrice;
            po.totalAmount = compProd.costPrice * comp.deficit;
          }

          state.addAuditLog("Procurement", "Component Auto PO", `Automatically created Purchase Order ${po.id} for component ${comp.name} to satisfy component shortage in ${mo.id}`);
          state.addNotification("procurement_created", `MTO Automation: Created ${po.id} for raw material ${comp.name} linked to manufacturing queue.`);
        });
      }

    } else if (short.procureType === "Purchase") {
      // Create PO
      const unitPrice = state.getProducts().find(p => p.id === short.productId)?.costPrice || 0;
      const po = state.addPurchaseOrder({
        vendorName: short.vendor || "Default Supplier",
        items: [
          { productId: short.productId, name: short.productName, quantity: short.shortage, unitPrice }
        ],
        totalAmount: unitPrice * short.shortage,
        sourceDocument: salesOrder.id
      });

      state.addAuditLog("Procurement", "Auto Replenish", `Automatically created Purchase Order ${po.id} for ${short.shortage} units to satisfy ${salesOrder.id}`);
      state.addNotification("procurement_created", `MTO Automation: Created ${po.id} for ${short.shortage}x ${short.productName} linked to ${salesOrder.id}`);
    }
  });
}

/**
 * Periodic MTS (Make-To-Stock) Reordering Rules check.
 * If free-to-use stock drops below threshold, generate RFQ/MO to replenish stock.
 */
export function runMTSReorderingRules() {
  const products = state.getProducts();
  let triggerCount = 0;

  products.forEach(product => {
    // Only apply if reorder threshold is set (>0) and procure strategy is MTS
    if (product.procureStrategy === "MTS" && product.reorderThreshold > 0) {
      if (product.freeToUse < product.reorderThreshold) {
        
        // Calculate standard replenishment amount: replenish to twice the threshold to hold buffer stock
        const currentDeficit = product.reorderThreshold - product.freeToUse;
        const replenishQty = Math.max(product.reorderThreshold * 2, currentDeficit + product.reorderThreshold);

        // Check if there is already an open PO or MO for this product to prevent duplicate triggers
        const hasOpenMO = state.getManufacturingOrders().some(
          mo => mo.productId === product.id && (mo.status === "draft" || mo.status === "confirmed" || mo.status === "in_progress")
        );
        const hasOpenPO = state.getPurchaseOrders().some(
          po => po.items.some(i => i.productId === product.id) && (po.status === "draft" || po.status === "confirmed")
        );

        if (hasOpenMO || hasOpenPO) {
          // Already replenishing
          return;
        }

        triggerCount++;
        state.addAuditLog("Procurement", "MTS Trigger", `MTS Reordering Rule triggered for ${product.name} (Free Stock: ${product.freeToUse} < Threshold: ${product.reorderThreshold})`);

        if (product.procureType === "Manufacturing" && product.bomId) {
          const mo = state.addManufacturingOrder({
            productId: product.id,
            productName: product.name,
            quantity: replenishQty,
            bomId: product.bomId,
            assignee: "MTS Reordering Engine",
            sourceDocument: "Reordering Rule (MTS)"
          });
          state.addAuditLog("Procurement", "Auto Replenish", `MTS: Created MO ${mo.id} for ${replenishQty} units`);
          state.addNotification("low_stock", `MTS Reordering: Created MO ${mo.id} for ${replenishQty}x ${product.name}`);
        } else if (product.procureType === "Purchase") {
          const po = state.addPurchaseOrder({
            vendorName: product.vendor || "Default Supplier",
            items: [
              { productId: product.id, name: product.name, quantity: replenishQty, unitPrice: product.costPrice }
            ],
            totalAmount: product.costPrice * replenishQty,
            sourceDocument: "Reordering Rule (MTS)"
          });
          state.addAuditLog("Procurement", "Auto Replenish", `MTS: Created PO ${po.id} for ${replenishQty} units`);
          state.addNotification("low_stock", `MTS Reordering: Created PO ${po.id} for ${replenishQty}x ${product.name}`);
        }
      }
    }
  });

  return triggerCount;
}
