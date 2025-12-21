/**
 * UI Components - Main Orchestrator
 * ===================================
 * 
 * This is the slim orchestrator that coordinates all UI modules:
 * - config/layers.js, providers.js, services.js
 * - utils/path-parser.js, formatters.js
 * - components/layer-card.js, comparison-table.js, warning-box.js
 * 
 * @version 2.0.0 (Modular Architecture)
 */

"use strict";

// =============================================================================
// NOTE: In a browser without ES6 modules, all scripts must be included in HTML
// in the correct order. This file assumes the following are loaded:
//   1. config/layers.js
//   2. config/providers.js
//   3. config/services.js
//   4. utils/path-parser.js
//   5. utils/formatters.js
//   6. components/layer-card.js
//   7. components/comparison-table.js
//   8. components/warning-box.js
//   9. calculation/ui.js
//  10. ui-components.js (this file)
// =============================================================================


/**
 * Main update function - called after API response
 * 
 * This is the primary entry point called by api-client.js after receiving
 * cost data from the optimizer backend. It orchestrates the entire UI update.
 * 
 * @param {object} awsCosts - AWS cost breakdown
 * @param {object} azureCosts - Azure cost breakdown
 * @param {object} gcpCosts - GCP cost breakdown
 * @param {Array<string>} cheapestPath - Array of path segments (e.g., ['L1_AWS', 'L2_Azure'])
 * @param {string} currency - Currency code ('USD' or 'EUR')
 * @param {object} params - User input parameters from the form
 * @param {object} l2Override - L3 Hot storage override info (when L3 != cheapest for L3)
 * @param {object} l3Override - L2 Processing override info
 * @param {object} l2CoolOverride - L3 Cool storage override info
 * @param {Array} l2_l3_combinations - L2/L3 combination table data
 * @param {object} l2ArchiveOverride - L3 Archive override info
 * @param {Array} l2_cool_combinations - Cool combinations
 * @param {Array} l2_archive_combinations - Archive combinations
 * @param {object} l1OptimizationOverride - L1 override info (glue code consideration)
 * @param {object} l4OptimizationOverride - L4 override info (glue code consideration)
 * @param {object} transferCosts - Cross-cloud transfer costs (egress + glue)
 */
async function updateHtml(
    awsCosts, azureCosts, gcpCosts, cheapestPath, currency, params,
    l2Override, l3Override, l2CoolOverride, l2_l3_combinations,
    l2ArchiveOverride, l2_cool_combinations, l2_archive_combinations,
    l1OptimizationOverride, l4OptimizationOverride, transferCosts
) {
    // 1. Parse selected providers from cheapest path
    const selectedProviders = parseSelectedProviders(cheapestPath);

    // 2. Display optimization warnings (explains why certain providers were chosen)
    displayWarnings(
        {
            l1: l1OptimizationOverride,
            l2: l2Override,
            l3: l3Override,
            l2Cool: l2CoolOverride,
            l2Archive: l2ArchiveOverride,
            l4: l4OptimizationOverride,
        },
        {
            l2_l3: l2_l3_combinations,
            cool: l2_cool_combinations,
            archive: l2_archive_combinations,
        }
    );

    // 3. Build comparison object from provider costs
    const comparison = buildComparisonObject(awsCosts, azureCosts, gcpCosts);

    // 4. Generate result HTML (pass raw costs for service breakdown)
    const resultHTML = generateResultHTML(comparison, cheapestPath, currency, params, selectedProviders, awsCosts, azureCosts, gcpCosts, transferCosts);

    // 5. Insert into DOM
    const resultContainer = document.getElementById("result");
    if (resultContainer) {
        resultContainer.innerHTML = resultHTML;
    }
}


/**
 * Build comparison object from raw costs
 * 
 * Transforms the API response structure into a layer-keyed object
 * for easier consumption by UI components.
 * 
 * API v2 response format uses keys: L1, L2, L3_hot, L3_cool, L3_archive, L4, L5
 * Each layer contains: { cost, components, dataSizeInGB (optional) }
 * 
 * NOTE: GCP is excluded from L4 and L5 because GCP calculation is disabled
 * (self-hosted Digital Twin / Grafana not implemented).
 * 
 * @param {object} awsCosts - AWS cost breakdown from API
 * @param {object} azureCosts - Azure cost breakdown from API
 * @param {object} gcpCosts - GCP cost breakdown from API
 * @returns {object} Layer-keyed comparison object
 */
function buildComparisonObject(awsCosts, azureCosts, gcpCosts) {
    return {
        layer1: {
            aws: awsCosts.L1?.cost || 0,
            azure: azureCosts.L1?.cost || 0,
            gcp: gcpCosts.L1?.cost || 0,
        },
        layer2: {
            aws: awsCosts.L2?.cost || 0,
            azure: azureCosts.L2?.cost || 0,
            gcp: gcpCosts.L2?.cost || 0,
        },
        layer3a: {
            aws: awsCosts.L3_hot?.cost || 0,
            azure: azureCosts.L3_hot?.cost || 0,
            gcp: gcpCosts.L3_hot?.cost || 0,
        },
        layer3b: {
            aws: awsCosts.L3_cool?.cost || 0,
            azure: azureCosts.L3_cool?.cost || 0,
            gcp: gcpCosts.L3_cool?.cost || 0,
        },
        layer3c: {
            aws: awsCosts.L3_archive?.cost || 0,
            azure: azureCosts.L3_archive?.cost || 0,
            gcp: gcpCosts.L3_archive?.cost || 0,
        },
        layer4: {
            aws: awsCosts.L4?.cost || 0,
            azure: azureCosts.L4?.cost || 0,
            // GCP L4 disabled: Digital Twin not implemented (future work)
            gcp: undefined,
        },
        layer5: {
            aws: awsCosts.L5?.cost || 0,
            azure: azureCosts.L5?.cost || 0,
            // GCP L5 disabled: Managed Grafana not implemented (future work)
            gcp: undefined,
        },
    };
}


/**
 * Generate the complete result HTML
 * 
 * Assembles the full results section including:
 * - Layer comparison cards (7 cards)
 * - Cheapest path visualization
 * - Service breakdown accordion (NEW)
 * - Total monthly cost display
 * 
 * @param {object} comparison - Layer-keyed cost comparison object
 * @param {Array} cheapestPath - Cheapest path segments
 * @param {string} currency - Currency code
 * @param {object} params - User parameters
 * @param {object} selectedProviders - Selected provider per layer
 * @param {object} awsCosts - Full AWS costs with components
 * @param {object} azureCosts - Full Azure costs with components
 * @param {object} gcpCosts - Full GCP costs with components
 * @param {object} transferCosts - Cross-cloud transfer costs
 * @returns {string} Complete HTML string
 */
function generateResultHTML(comparison, cheapestPath, currency, params, selectedProviders, awsCosts, azureCosts, gcpCosts, transferCosts) {
    const currencySymbol = getCurrencySymbol(currency);

    return `
    
    <h3 class="text-secondary mt-5 mb-3">Cheapest Path</h3>
    <div class="d-flex flex-wrap justify-content-center align-items-center gap-2 mt-3 mb-4 px-3">
        ${formatPathAsBadges(cheapestPath)}
    </div>
    
    <h3 class="text-secondary mb-4">Layer Results</h3>
    
    <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4 mb-5">
        ${generateLayerCard(comparison.layer1, 'Layer 1: Data Acquisition', 'l1', params, selectedProviders, currency)}
        ${generateLayerCard(comparison.layer2, 'Layer 2: Data Processing', 'l2', params, selectedProviders, currency)}
        ${generateLayerCard(comparison.layer3a, 'Layer 3: Hot Storage', 'l3_hot', params, selectedProviders, currency)}
        ${generateLayerCard(comparison.layer3b, 'Layer 3: Cool Storage', 'l3_cool', params, selectedProviders, currency)}
        ${generateLayerCard(comparison.layer3c, 'Layer 3: Archive Storage', 'l3_archive', params, selectedProviders, currency)}
        ${generateLayerCard(comparison.layer4, 'Layer 4: Twin Management', 'l4', params, selectedProviders, currency)}
        ${generateLayerCard(comparison.layer5, 'Layer 5: Visualization', 'l5', params, selectedProviders, currency)}
    </div>

    ${generateServiceBreakdown(awsCosts, azureCosts, gcpCosts, currency, transferCosts, cheapestPath)}

    <h3 class="text-secondary mt-5 mb-3">Total Monthly Cost</h3>
    <div class="d-flex justify-content-center align-items-center gap-2 mt-3 mb-2 flex-wrap">
        ${generateTotalCostDisplay(comparison, cheapestPath, selectedProviders, currencySymbol)}
    </div>
    `;
}


/**
 * Generate total cost display with breakdown
 * 
 * @param {object} comparison - Layer-keyed costs
 * @param {Array} cheapestPath - Path segments (unused but kept for API consistency)
 * @param {object} selectedProviders - Selected provider per layer
 * @param {string} symbol - Currency symbol
 * @returns {string} HTML for total cost display
 */
function generateTotalCostDisplay(comparison, cheapestPath, selectedProviders, symbol) {
    // Calculate total from selected providers
    const costs = [
        getCostForProvider(comparison.layer1, selectedProviders.l1),
        getCostForProvider(comparison.layer2, selectedProviders.l2),
        getCostForProvider(comparison.layer3a, selectedProviders.l3_hot),
        getCostForProvider(comparison.layer3b, selectedProviders.l3_cool),
        getCostForProvider(comparison.layer3c, selectedProviders.l3_archive),
        getCostForProvider(comparison.layer4, selectedProviders.l4),
        getCostForProvider(comparison.layer5, selectedProviders.l5),
    ];

    const total = costs.reduce((sum, c) => sum + c, 0);

    return `
        <div class="text-center p-4 bg-light rounded shadow-sm" style="min-width: 280px;">
            <h2 class="text-primary display-5 fw-bold">${symbol}${formatCost(total)}</h2>
            <small class="text-muted">Optimized Multi-Cloud Monthly Cost</small>
        </div>
    `;
}


/**
 * Get cost for a specific provider from layer costs
 * 
 * @param {object} layerCosts - Cost object { aws, azure, gcp }
 * @param {string} providerId - Provider ID to get cost for
 * @returns {number} Cost value or 0
 */
function getCostForProvider(layerCosts, providerId) {
    if (!layerCosts) return 0;
    const provider = providerId?.toLowerCase() || 'aws';
    return layerCosts[provider] || 0;
}
