/**
 * Service Breakdown Component
 * ============================
 * Generates a collapsible accordion showing per-service pricing
 * for each provider, sorted by cost (highest first).
 * 
 * @version 1.0.0
 */

"use strict";

// =============================================================================
// Service Name Mapping
// =============================================================================

/**
 * Maps internal component keys to human-readable service names.
 * Falls back to formatted key if not found.
 */
const COMPONENT_NAMES = {
    // L1 - Data Acquisition
    "iot_core": "AWS IoT Core",
    "dispatcher_lambda": "Dispatcher Lambda",
    "iot_hub": "Azure IoT Hub",
    "dispatcher_function": "Dispatcher Function",
    "event_grid_subscription": "Event Grid Subscription",
    "pubsub": "Google Pub/Sub",
    "dispatcher_cloud_function": "Dispatcher Cloud Function",

    // L2 - Data Processing
    "persister_lambda": "Persister Lambda",
    "persister_function": "Persister Function",
    "processor_lambdas": "Processor Lambdas",
    "processor_functions": "Processor Functions",
    "event_checker": "Event Checker",
    "event_feedback": "Event Feedback",
    "step_functions": "AWS Step Functions",
    "logic_apps": "Azure Logic Apps",
    "cloud_workflows": "Google Workflows",
    "eventbridge": "AWS EventBridge",
    "event_grid": "Azure Event Grid",
    "event_action_functions": "Event Action Functions",

    // L3 Hot - Hot Storage
    "dynamodb": "Amazon DynamoDB",
    "cosmos_db": "Azure Cosmos DB",
    "firestore": "Google Firestore",
    "hot_reader_lambda": "Hot Reader Lambda",
    "hot_reader_function": "Hot Reader Function",

    // L3 Cool - Cool Storage
    "s3_ia": "S3 Infrequent Access",
    "blob_cool": "Blob Storage (Cool)",
    "gcs_nearline": "GCS Nearline",
    "hot_cold_mover_lambda": "Data Mover Lambda",
    "hot_cold_mover_function": "Data Mover Function",
    "eventbridge_scheduler": "EventBridge Scheduler",

    // L3 Archive - Archive Storage
    "s3_glacier": "S3 Glacier Deep Archive",
    "blob_archive": "Blob Storage (Archive)",
    "gcs_coldline": "GCS Coldline",
    "cold_archive_mover_lambda": "Archive Mover Lambda",
    "cold_archive_mover_function": "Archive Mover Function",

    // L4 - Twin Management
    "twinmaker": "AWS TwinMaker",
    "digital_twins": "Azure Digital Twins",

    // L5 - Visualization
    "managed_grafana": "AWS Managed Grafana",
    "grafana_workspace": "Azure Grafana Workspace",
};

/**
 * Layer display configuration
 */
const LAYER_CONFIG = [
    { key: "L1", title: "Layer 1: Data Acquisition" },
    { key: "L2", title: "Layer 2: Data Processing" },
    { key: "L3_hot", title: "Layer 3: Hot Storage" },
    { key: "L3_cool", title: "Layer 3: Cool Storage" },
    { key: "L3_archive", title: "Layer 3: Archive Storage" },
    { key: "L4", title: "Layer 4: Twin Management" },
    { key: "L5", title: "Layer 5: Visualization" },
];

// =============================================================================
// Main Generator Function
// =============================================================================

/**
 * Generate Service Breakdown Accordion
 * 
 * @param {object} awsCosts - Full AWS costs object with components
 * @param {object} azureCosts - Full Azure costs object with components  
 * @param {object} gcpCosts - Full GCP costs object with components
 * @param {string} currency - Currency code (USD/EUR)
 * @param {object} transferCosts - Cross-cloud transfer costs
 * @param {Array} cheapestPath - Cheapest path array for determining transfers
 * @returns {string} HTML for accordion
 */
function generateServiceBreakdown(awsCosts, azureCosts, gcpCosts, currency = "USD", transferCosts = {}, cheapestPath = []) {
    const currencySymbol = currency === "EUR" ? "€" : "$";

    const accordionItems = LAYER_CONFIG.map((layer, index) => {
        const awsLayer = awsCosts?.[layer.key] || {};
        const azureLayer = azureCosts?.[layer.key] || {};
        const gcpLayer = gcpCosts?.[layer.key] || {};

        const awsComponents = awsLayer.components || {};
        const azureComponents = azureLayer.components || {};
        const gcpComponents = gcpLayer.components || {};

        // Check if GCP is applicable for this layer
        const gcpAvailable = layer.key !== "L4" && layer.key !== "L5";

        return generateAccordionItem(
            layer.key,
            layer.title,
            awsComponents,
            azureComponents,
            gcpComponents,
            gcpAvailable,
            currencySymbol,
            index === 0 // First item expanded by default
        );
    }).join("");

    // Generate transfer costs section if any exist
    const transferSection = generateTransferSection(transferCosts, cheapestPath, currencySymbol);

    return `
        <h3 class="text-secondary mt-5 mb-3">Service Cost Breakdown</h3>
        <div class="accordion mb-5" id="serviceBreakdownAccordion">
            ${accordionItems}
            ${transferSection}
        </div>
    `;
}

/**
 * Generate a single accordion item for a layer
 */
function generateAccordionItem(layerKey, title, awsComponents, azureComponents, gcpComponents, gcpAvailable, symbol, expanded) {
    const itemId = `breakdown-${layerKey}`;
    const collapseId = `collapse-${layerKey}`;

    const awsColumn = generateProviderColumn("AWS", awsComponents, symbol, "badge-aws");
    const azureColumn = generateProviderColumn("Azure", azureComponents, symbol, "badge-azure");
    const gcpColumn = gcpAvailable
        ? generateProviderColumn("GCP", gcpComponents, symbol, "badge-gcp")
        : generateNotAvailableColumn("GCP", "Not Implemented");

    return `
        <div class="accordion-item">
            <h2 class="accordion-header" id="${itemId}">
                <button class="accordion-button ${expanded ? '' : 'collapsed'}" type="button" 
                        data-bs-toggle="collapse" data-bs-target="#${collapseId}" 
                        aria-expanded="${expanded}" aria-controls="${collapseId}">
                    ${title}
                </button>
            </h2>
            <div id="${collapseId}" class="accordion-collapse collapse ${expanded ? 'show' : ''}" 
                 aria-labelledby="${itemId}" data-bs-parent="#serviceBreakdownAccordion">
                <div class="accordion-body">
                    <div class="row g-3">
                        <div class="col-md-4">${awsColumn}</div>
                        <div class="col-md-4">${azureColumn}</div>
                        <div class="col-md-4">${gcpColumn}</div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Generate a provider column with sorted service list
 */
function generateProviderColumn(providerName, components, symbol, badgeClass) {
    // Convert components object to sorted array
    const entries = Object.entries(components)
        .map(([key, cost]) => ({
            key,
            name: getComponentName(key),
            cost: typeof cost === 'number' ? cost : 0
        }))
        .sort((a, b) => b.cost - a.cost); // Sort by cost descending

    if (entries.length === 0) {
        return `
            <div class="card h-100 border-0 bg-light">
                <div class="card-header py-2 ${badgeClass} text-white">
                    <strong>${providerName}</strong>
                </div>
                <div class="card-body p-2">
                    <p class="text-muted small mb-0">No components</p>
                </div>
            </div>
        `;
    }

    const total = entries.reduce((sum, e) => sum + e.cost, 0);

    const rows = entries.map((entry, idx) => {
        const isBiggest = idx === 0 && entry.cost > 0;
        const rowClass = isBiggest ? 'fw-bold' : '';
        return `
            <tr class="${rowClass}">
                <td class="small">${entry.name}</td>
                <td class="text-end small">${formatBreakdownCost(entry.cost, symbol)}</td>
            </tr>
        `;
    }).join("");

    return `
        <div class="card h-100 border-0 shadow-sm">
            <div class="card-header py-2 ${badgeClass} text-white">
                <strong>${providerName}</strong>
            </div>
            <div class="card-body p-0">
                <table class="table table-sm table-borderless mb-0">
                    <tbody>
                        ${rows}
                    </tbody>
                    <tfoot class="table-light">
                        <tr class="fw-bold">
                            <td class="small">Total</td>
                            <td class="text-end small">${formatBreakdownCost(total, symbol)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    `;
}

/**
 * Generate a "Not Available" column for unsupported providers
 */
function generateNotAvailableColumn(providerName, reason) {
    return `
        <div class="card h-100 border-0 bg-light">
            <div class="card-header py-2 bg-secondary text-white">
                <strong>${providerName}</strong>
            </div>
            <div class="card-body p-3 text-center">
                <p class="text-muted small mb-0">
                    <i class="bi bi-slash-circle me-1"></i>${reason}
                </p>
            </div>
        </div>`
}

/**
 * Generate transfer costs section
 * @param {object} transferCosts - Transfer costs object from API
 * @param {Array} cheapestPath - Cheapest path array
 * @param {string} symbol - Currency symbol
 * @returns {string} HTML for transfer section or empty string
 */
function generateTransferSection(transferCosts, cheapestPath, symbol) {
    if (!transferCosts || Object.keys(transferCosts).length === 0) {
        return '';
    }

    const transfers = [];

    // L1 → L2
    if (transferCosts.L1_to_L2 && transferCosts.L1_to_L2 > 0) {
        const l1Provider = parseProviderFromPath(cheapestPath, 0);
        const l2Provider = parseProviderFromPath(cheapestPath, 1);
        transfers.push({
            title: `L1 -> L2(${l1Provider} -> ${l2Provider})`,
            cost: transferCosts.L1_to_L2
        });
    }

    // L2 → L3_hot
    if (transferCosts.L2_to_L3_hot && transferCosts.L2_to_L3_hot > 0) {
        const l2Provider = parseProviderFromPath(cheapestPath, 1);
        const l3Provider = parseProviderFromPath(cheapestPath, 2);
        transfers.push({
            title: `L2 -> L3 Hot(${l2Provider} -> ${l3Provider})`,
            cost: transferCosts.L2_to_L3_hot
        });
    }

    // L3_hot → L3_cool
    if (transferCosts.L3_hot_to_L3_cool && transferCosts.L3_hot_to_L3_cool > 0) {
        const hotProvider = parseProviderFromPath(cheapestPath, 2);
        const coolProvider = parseProviderFromPath(cheapestPath, 3);
        transfers.push({
            title: `L3 Hot -> Cool(${hotProvider} -> ${coolProvider})`,
            cost: transferCosts.L3_hot_to_L3_cool
        });
    }

    // L3_cool → L3_archive
    if (transferCosts.L3_cool_to_L3_archive && transferCosts.L3_cool_to_L3_archive > 0) {
        const coolProvider = parseProviderFromPath(cheapestPath, 3);
        const archiveProvider = parseProviderFromPath(cheapestPath, 4);
        transfers.push({
            title: `L3 Cool -> Archive(${coolProvider} -> ${archiveProvider})`,
            cost: transferCosts.L3_cool_to_L3_archive
        });
    }

    // L3_hot → L4
    if (transferCosts.L3_hot_to_L4 && transferCosts.L3_hot_to_L4 > 0) {
        const hotProvider = parseProviderFromPath(cheapestPath, 2);
        const l4Provider = parseProviderFromPath(cheapestPath, 5);
        transfers.push({
            title: `L3 Hot -> L4(${hotProvider} -> ${l4Provider})`,
            cost: transferCosts.L3_hot_to_L4
        });
    }

    if (transfers.length === 0) {
        return '';
    }

    const rows = transfers.map(t => `
        <tr>
            <td class="small">${t.title}</td>
            <td class="text-end small">${formatBreakdownCost(t.cost, symbol)}</td>
        </tr>
    `).join('');

    const total = transfers.reduce((sum, t) => sum + t.cost, 0);

    return `
        <div class="accordion-item">
            <h2 class="accordion-header" id="breakdown-transfers">
                <button class="accordion-button collapsed" type="button" 
                        data-bs-toggle="collapse" data-bs-target="#collapse-transfers" 
                        aria-expanded="false" aria-controls="collapse-transfers">
                    Cross-Cloud Transfer Costs
                </button>
            </h2>
            <div id="collapse-transfers" class="accordion-collapse collapse" 
                 aria-labelledby="breakdown-transfers" data-bs-parent="#serviceBreakdownAccordion">
                <div class="accordion-body">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header py-2 bg-warning text-dark">
                            <strong><i class="bi bi-arrow-left-right me-2"></i>Data Transfer Costs</strong>
                        </div>
                        <div class="card-body p-0">
                            <table class="table table-sm table-borderless mb-0">
                                <tbody>
                                    ${rows}
                                </tbody>
                                <tfoot class="table-light">
                                    <tr class="fw-bold">
                                        <td class="small">Total Transfer Costs</td>
                                        <td class="text-end small">${formatBreakdownCost(total, symbol)}</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>
                    <small class="text-muted d-block mt-2">
                        <i class="bi bi-info-circle me-1"></i>
                        Transfer costs include egress fees and glue function costs for cross-cloud data movement.
                    </small>
                </div>
            </div>
        </div>
    `;
}

/**
 * Parse provider from cheapest path array
 * @param {Array} path - Cheapest path array (e.g., ['L1_AWS', 'L2_Azure', ...])
 * @param {number} index - Index in path
 * @returns {string} Provider name
 */
function parseProviderFromPath(path, index) {
    if (!path || !path[index]) return 'Unknown';
    const segment = path[index];
    const parts = segment.split('_');
    return parts[parts.length - 1]; // Last part is provider (e.g., 'AWS' from 'L1_AWS')
}



// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get human-readable component name from key
 */
function getComponentName(key) {
    if (COMPONENT_NAMES[key]) {
        return COMPONENT_NAMES[key];
    }
    // Fallback: format key as Title Case
    return key
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

/**
 * Format cost for breakdown display
 * @param {number} cost - Cost value
 * @param {string} symbol - Currency symbol
 */
function formatBreakdownCost(cost, symbol = "$") {
    if (cost > 0 && cost < 0.01) {
        return `< ${symbol} 0.01`;
    }
    return `${symbol}${cost.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })
        } `;
}
